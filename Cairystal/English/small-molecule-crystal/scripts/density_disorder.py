"""Current-Q-peak guided disorder proposals and staged native screening.

No reference coordinates. Short screens are NOT validated models: AB stays null.
Finalists restart from the same baseline and receive complete native validation.
"""
from pathlib import Path
import argparse,hashlib,itertools,json,math,shutil,time,traceback
import gemmi
import numpy as np
from common_disorder import detect,positions,pos,graph_model,generate
from structure_diagnostics import structure,res_records,digest,newjson,analyse
from crystal_runtime import paired_bundle,run_command,write_json
from candidate_trials import build,execute,run_plan
from refinement_gate import assess

DEFAULT={'min_peak':.35,'match_radius_A':.5,'max_local_peaks':40,'max_raw_poses':512,
         'max_poses_per_site':4,'max_sites':4,'short_cycles':6,'full_cycles':30,
         'finalists_per_site':1,'population_start':.7,'short_adp':'MAJOR_ANI'}

def config(values=None):
    result=dict(DEFAULT);values=values or {}
    if set(values)-set(result):raise ValueError('Unknown screening setting')
    result.update(values)
    if result['short_adp'] not in {'ISO','MAJOR_ANI'}:raise ValueError('Invalid short_adp')
    limits={'max_local_peaks':(3,80),'max_raw_poses':(1,2000),'max_poses_per_site':(1,8),'max_sites':(1,8),
            'short_cycles':(2,12),'full_cycles':(12,100),'finalists_per_site':(1,3)}
    for k,(lo,hi) in limits.items():
        if type(result[k]) is not int or not lo<=result[k]<=hi:raise ValueError('Invalid '+k)
    for k,lo,hi in [('min_peak',.05,5),('match_radius_A',.2,.7),('population_start',.15,.85)]:
        v=result[k]
        if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Invalid '+k)
    return result

def fitted_angle(source,target,axis):
    """Signed rotation from projected source to target, degrees, no fixed angle grid."""
    axis=np.asarray(axis,dtype=float);axis=axis/np.linalg.norm(axis)
    a=np.asarray(source,dtype=float);b=np.asarray(target,dtype=float)
    a=a-np.dot(a,axis)*axis;b=b-np.dot(b,axis)*axis
    if min(np.linalg.norm(a),np.linalg.norm(b))<.15:return None
    return math.degrees(math.atan2(float(np.dot(axis,np.cross(a,b))),float(np.dot(a,b))))

def rigid_fit(source,target):
    """Proper Kabsch rotation only: never fit a reflected stereoisomer."""
    a=np.asarray(source,float);b=np.asarray(target,float)
    if a.shape!=b.shape or a.ndim!=2 or a.shape[1]!=3 or len(a)<3 or not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError('Three finite corresponding positions required')
    ac=a.mean(0);bc=b.mean(0);x=a-ac;y=b-bc
    if np.linalg.matrix_rank(x,tol=.05)<2 or np.linalg.matrix_rank(y,tol=.05)<2:raise ValueError('Collinear anchors cannot establish a pose')
    u,_,vt=np.linalg.svd(x.T@y);adjust=np.eye(3);adjust[2,2]=np.linalg.det(u@vt);rot=u@adjust@vt
    shift=bc-ac@rot;rms=float(np.sqrt(np.mean(np.sum((a@rot+shift-b)**2,axis=1))))
    return rot,shift,rms

def rotation_config(rot,shift,centre):
    # Row-vector rotation -> right-handed column-vector Rodrigues convention.
    m=rot.T;angle=math.acos(float(np.clip((np.trace(m)-1)/2,-1,1)))
    if abs(angle)<1e-7:axis=np.array([1.,0,0])
    elif abs(math.pi-angle)<1e-5:
        vals,vecs=np.linalg.eigh((m+np.eye(3))/2);axis=vecs[:,np.argmax(vals)]
    else:axis=np.array([m[2,1]-m[1,2],m[0,2]-m[2,0],m[1,0]-m[0,1]])/(2*math.sin(angle))
    axis=axis/np.linalg.norm(axis);translation=np.asarray(centre)@rot+shift-np.asarray(centre)
    return {'rigid_axis':axis.tolist(),'angle_deg':math.degrees(angle),'translation_A':translation.tolist()}

def peak_images(cell,ops,peaks,centre,radius,threshold,limit):
    centre=np.asarray(centre);cf=cell.fractionalize(gemmi.Position(*centre));found=[];seen=set()
    for peak in sorted(peaks,key=lambda p:(-p['height'],p['label'])):
        if peak['height']<threshold:continue
        for op in ops:
            base=op.apply_to_xyz(peak['xyz']);off=np.rint(np.array([cf.x,cf.y,cf.z])-np.array(base)).astype(int)
            # Include neighbouring cells for skewed cells; use Cartesian distance to choose.
            for delta in itertools.product((-1,0,1),repeat=3):
                frac=np.array(base)+off+np.array(delta);p=cell.orthogonalize(gemmi.Fractional(*frac));xyz=np.array([p.x,p.y,p.z])
                if np.linalg.norm(xyz-centre)>radius:continue
                key=tuple(np.round(xyz,3))
                if key in seen:continue
                seen.add(key);found.append({'xyz':xyz.tolist(),'height':peak['height'],'peak':peak['label'],'symmetry':op.triplet(),'shift':(off+np.array(delta)).tolist()})
    return sorted(found,key=lambda p:(-p['height'],np.linalg.norm(np.array(p['xyz'])-centre)))[:limit]

def match_score(points,elements,oldpoints,old_elements,peaks,radius):
    """One-to-one atom/peak correspondence; no peak may support two atoms."""
    displaced=[]
    for i,point in enumerate(points):
        same=[np.linalg.norm(np.array(point)-np.array(q)) for e,q in zip(old_elements,oldpoints) if e==elements[i]]
        if min(same,default=99)>=.30:displaced.append(i)
    edges=sorted((float(np.linalg.norm(np.array(points[i])-np.array(p['xyz']))),i,j) for i in displaced for j,p in enumerate(peaks))
    useda=set();usedp=set();matches=[]
    for distance,i,j in edges:
        if distance>radius:break
        # Symmetry images of one native Q are correlated evidence, not new peaks.
        identity=peaks[j]['peak']
        if i in useda or identity in usedp:continue
        useda.add(i);usedp.add(identity);matches.append({'atom_index':i,'peak_index':j,'peak':identity,'distance_A':distance,'height':peaks[j]['height']})
    score=sum(x['height']*math.exp(-.5*(x['distance_A']/.25)**2) for x in matches)
    return float(score),matches,len(displaced)

def clashes(cell,ops,heavy,graph,keys,points):
    bad=[];keyset=set(keys)
    for key,xyz in zip(keys,points):
        f=cell.fractionalize(gemmi.Position(*xyz))
        for other,a in heavy.items():
            for op in ops:
                if op.triplet()=='x,y,z' and (other in keyset or other in graph[key]):continue
                d=cell.find_nearest_pbc_image(f,gemmi.Fractional(*op.apply_to_xyz(a['xyz'])),0).dist()
                cutoff=.65*(gemmi.Element(heavy[key]['element']).covalent_r+gemmi.Element(a['element']).covalent_r)
                if d<cutoff:bad.append([key,other,op.triplet(),d])
    return bad

def propose(directory,site,settings=None):
    cfg=config(settings);base=Path(directory);b,cell,ops,atoms,parsed=structure(base/'case.cif',base/'case.res')
    if site['status']!='screenable':return {'status':'needs_review','poses':[],'reasons':site['review_reasons']}
    keys=site['atoms'];heavy,graph,periodic=graph_model(b,cell,atoms);amap={a['label'].upper():a for a in parsed['atoms']}
    old=np.array([pos(cell,heavy[k]) for k in keys]);centre=old.mean(0);elements=[heavy[k]['element'] for k in keys]
    peaks=peak_images(cell,ops,parsed['peaks'],centre,float(max(np.linalg.norm(old-centre,axis=1))+1.4),cfg['min_peak'],cfg['max_local_peaks'])
    raw=[];axis=site.get('axis')
    if axis:
        origin=np.array(pos(cell,heavy[axis[1]]));vector=origin-np.array(pos(cell,heavy[axis[0]]));unit=vector/np.linalg.norm(vector)
        for point in old:
            a=point-origin;rad=np.linalg.norm(a-np.dot(a,unit)*unit);along=np.dot(a,unit)
            for peak in peaks:
                q=np.array(peak['xyz'])-origin
                if abs(np.dot(q,unit)-along)>.65 or abs(np.linalg.norm(q-np.dot(q,unit)*unit)-rad)>.65:continue
                angle=fitted_angle(a,q,unit)
                if angle is not None:
                    for offset in [-6.,0.,6.]:
                        value=(angle+offset+180)%360-180
                        if abs(value)>=8:raw.append({'axis':axis,'angle_deg':value})
        raw=list({round(x['angle_deg'],1):x for x in raw}.values())[:cfg['max_raw_poses']]
    elif len(old)>=3:
        # Three well-separated existing atoms anchor the current fragment geometry.
        first=0;second=max(range(len(old)),key=lambda i:np.linalg.norm(old[i]-old[first]))
        third=max(range(len(old)),key=lambda i:np.linalg.norm(np.cross(old[second]-old[first],old[i]-old[first])))
        anchors=old[[first,second,third]];pairs=[np.linalg.norm(anchors[i]-anchors[j]) for i,j in [(0,1),(0,2),(1,2)]]
        for p1,p2 in itertools.permutations(range(len(peaks)),2):
            q1=np.array(peaks[p1]['xyz']);q2=np.array(peaks[p2]['xyz'])
            if abs(np.linalg.norm(q1-q2)-pairs[0])>.5:continue
            for p3 in range(len(peaks)):
                if p3 in {p1,p2}:continue
                q3=np.array(peaks[p3]['xyz'])
                if abs(np.linalg.norm(q1-q3)-pairs[1])>.5 or abs(np.linalg.norm(q2-q3)-pairs[2])>.5:continue
                try:rot,shift,rms=rigid_fit(anchors,[q1,q2,q3])
                except ValueError:continue
                if rms>.35:continue
                pose=rotation_config(rot,shift,centre)
                if np.linalg.norm(pose['translation_A'])<=1.25:raw.append(pose)
                if len(raw)>=cfg['max_raw_poses']:break
            if len(raw)>=cfg['max_raw_poses']:break
    # Density-directed translation is also useful for small disconnected fragments.
    if not axis:
        for point in old:
            for peak in peaks:
                shift=np.array(peak['xyz'])-point
                if .30<=np.linalg.norm(shift)<=1.25:raw.append({'rigid_axis':[1,0,0],'angle_deg':0.,'translation_A':shift.tolist()})
    used={abs(a['part']) for a in parsed['atoms']};parts=[i for i in range(1,100) if i not in used][:2];candidates=[]
    for pose in raw[:cfg['max_raw_poses']]:
        setting=dict(pose,atoms=keys,parts=parts,occupancy_start=cfg['population_start'],adp='ISO',basis='Current native difference-Q evidence; diagnostic, phase-biased and truncated')
        try:
            _,mapping,transform=positions(parsed,b,setting);points=[transform(mapping[k],True) for k in keys]
        except ValueError:continue
        score,matches,displaced=match_score(points,elements,old,elements,peaks,cfg['match_radius_A'])
        minimum=3 if len(keys)>5 else 2
        if len(matches)<minimum or displaced<minimum:continue
        if clashes(cell,ops,heavy,graph,keys,points):continue
        candidates.append({'config':setting,'score':score,'peak_support':matches,'points':points})
    chosen=[]
    for item in sorted(candidates,key=lambda v:-v['score']):
        if any(all(min(np.linalg.norm(np.array(p)-np.array(q)) for j,q in enumerate(prior['points']) if elements[i]==elements[j])<.15 for i,p in enumerate(item['points'])) for prior in chosen):continue
        # Expensive bookkeeping only for distinct ranked poses, not every angle.
        try:generate(parsed,b,item['config'])
        except ValueError:continue
        chosen.append(item)
        if len(chosen)>=cfg['max_poses_per_site']:break
    return {'status':'proposed' if chosen else 'insufficient_supported_density','poses':[{k:v for k,v in p.items() if k!='points'} for p in chosen],
            'local_peaks':peaks,'raw_pose_count':len(raw),'density_source':'native FMAP 2 Q list, not a full continuous map','source_hashes':{e:digest(base/('case.'+e)) for e in ['res','cif']}}

def short_trial(base,out,plan,software,resources):
    out=Path(out);out.mkdir();start=time.perf_counter();result={'name':plan['name'],'status':'screen_failed','AB':None,'validation_complete':False,'model_adopted':False,'plan':plan}
    try:
        text,edits=build(base,plan,out);(out/'case.ins').write_text(text,encoding='ascii');shutil.copy2(Path(base)/'case.hkl',out/'case.hkl')
        result['command']=run_command([software['shelxl'],'case',f"-t{resources['threads']}",f"-b{resources['matrix_parameters']}"],out,out/'process.log',600)
        gate=assess(out,'case');result['gate']=gate;result['edits']=edits
        if not gate['execution_complete']:raise ValueError('Incomplete native short refinement: '+str(gate['failures']))
        _,cell,_,atoms,_=structure(out/'case.cif',out/'case.res');amap={a['label'].upper():a for a in atoms};split=next((e['split_fragment'] for e in edits if 'split_fragment' in e),None)
        if split:
            missing=[n for m in split['mapping'].values() for n in m.values() if n.upper() not in amap]
            selected=[amap[n.upper()] for m in split['mapping'].values() for n in m.values() if n.upper() in amap and amap[n.upper()]['element']!='H']
            populations=[a['occupancy'] for a in selected]
            good=not missing and bool(populations) and all(isinstance(p,(float,int)) and math.isfinite(p) and .01<=p<=.99 for p in populations)
            result['missing_split_atoms']=missing
            result['population_range']=[min(populations),max(populations)] if good else None
            if not good:result['screen_reason']='native_split_atoms_missing' if missing else 'population_outside_physical_interior'
            else:result['status']='screen_complete'
        else:result['status']='screen_complete'
        from disorder_bond_review import trial_review
        result['bond_review']=trial_review(out,'case')
        result['metrics']=gate['metrics']
        # Slow convergence by itself is not enough to prune a short-screen model.
        if (gate['metrics'].get('NPD_atoms') or 0)>2:result['status']='screen_rejected';result['screen_reason']='multiple_non_positive_ADPs'
    except Exception as exc:result.update(error=str(exc),traceback=traceback.format_exc())
    result['elapsed_s']=time.perf_counter()-start;write_json(out/'screen.json',result);return result

def choose_screens(screens,limit):
    return screen_decisions(screens,limit)[0]

def screen_decisions(screens,limit):
    """Explain every promotion/pruning decision; missing/nonfinite metrics never rank."""
    eligible=[];decisions=[]
    for s in screens:
        reason=[];metric=s.get('metrics') or {};r=metric.get('R1_observed')
        if s.get('status')!='screen_complete':reason.append(s.get('screen_reason') or s.get('status','missing_status'))
        if isinstance(r,bool) or not isinstance(r,(int,float)) or not math.isfinite(r) or r<0:reason.append('R1_missing_or_nonfinite')
        if reason:decisions.append({'name':s['name'],'decision':'not_eligible','reasons':reason,'AB':None})
        else:eligible.append(s)
    def key(s):
        metric=s.get('metrics') or {};bond=s.get('bond_review') or {}
        # Known chemistry conflicts are considered before numerical fit; unknowns remain visible.
        npd=metric.get('NPD_atoms')
        return (bool(bond.get('findings')),npd is not None and npd>0,
                bond.get('status')=='unavailable',metric['R1_observed'],s['name'])
    ranked=sorted(eligible,key=key);chosen=ranked[:limit]
    for rank,s in enumerate(ranked):
        decisions.append({'name':s['name'],'decision':'promoted' if rank<limit else 'deferred_budget',
            'reasons':['Full comparison scheduled; not model acceptance'] if rank<limit else ['finalists_per_site_budget'],
            'rank':rank+1,'bond_findings':(s.get('bond_review') or {}).get('findings'),
            'NPD_atoms':(s.get('metrics') or {}).get('NPD_atoms'),'AB':None})
    return chosen,decisions


def split_special_sites(cell,ops,atoms,labels):
    """A native refinement may move an initially general atom onto a special site."""
    selected={n.upper() for n in labels};hits=[]
    for a in atoms:
        if a['label'].upper() not in selected or a['element']=='H':continue
        xyz=gemmi.Fractional(*a['xyz'])
        stabilizer=sum(cell.find_nearest_pbc_image(xyz,gemmi.Fractional(*op.apply_to_xyz(a['xyz'])),0).dist()<.001 for op in ops)
        if stabilizer!=1:hits.append({'label':a['label'],'site_stabilizer_order':stabilizer,'physical_occupancy':a.get('occupancy'),'reason':'General-site split moved onto special position; occupancy and symmetry-related connectivity require explicit review.'})
    return hits

def quality_review(control,trial):
    """Population, branch collapse and file pairing must accompany R/AB comparison."""
    from compare_diagnostic_trials import compare
    item=compare(control,trial)
    if trial['status']!='completed':return item
    directory=Path(trial['diagnostic']).parent/'paired'
    try:paired_bundle(directory,'case');item['file_pairing']='passed'
    except Exception as exc:item['file_pairing']='failed';item['pairing_error']=str(exc);item['flags'].append('paired_bundle_requires_review')
    diag=json.loads(Path(trial['diagnostic']).read_text('utf8'));amap={a['label'].upper():a for a in diag['all_atoms']}
    split=next((e['split_fragment'] for e in trial['edits'] if 'split_fragment' in e),None)
    if split:
        mapping=split['mapping'];missing=[n for m in mapping.values() for n in m.values() if n.upper() not in amap]
        try:
            _,cell,ops,atoms,_=structure(directory/'case.cif',directory/'case.res')
            item['special_site_migrations']=split_special_sites(cell,ops,atoms,[n for m in mapping.values() for n in m.values()])
            if item['special_site_migrations']:item['flags'].append('split_atom_moved_to_special_position')
        except Exception as exc:
            item['flags'].append('final_split_symmetry_audit_failed');item['symmetry_audit_error']=str(exc)
        if missing:item['flags'].append('native_atom_or_H_missing_after_trial');item['missing_labels']=missing
        else:
            pops=[amap[n.upper()]['occupancy'] for m in mapping.values() for n in m.values() if amap[n.upper()]['element']!='H']
            good=bool(pops) and all(isinstance(v,(int,float)) and math.isfinite(v) for v in pops)
            item['population_range']=[min(pops),max(pops)] if good else None
            if not good or any(not .05<=v<=.95 for v in pops):item['flags'].append('minor_population_unresolved_or_at_boundary')
            for parent,children in split.get('H_parent_groups',{}).items():
                for suffix in 'AB':
                    pa=amap[mapping[parent][suffix].upper()]
                    for child in children:
                        ha=amap[mapping[child.upper()][suffix].upper()]
                        if ha['part']!=pa['part'] or ha['occupancy']!=pa['occupancy']:item['flags'].append('H_parent_PART_or_population_mismatch')
            cell=gemmi.UnitCell(*diag['cell']);dist=[]
            for m in mapping.values():
                a,b=[amap[m[s].upper()] for s in 'AB']
                if a['element']!='H':dist.append(cell.find_nearest_pbc_image(gemmi.Fractional(*a['xyz']),gemmi.Fractional(*b['xyz']),0).dist())
            item['max_branch_atom_separation_A']=max(dist) if dist else None
            if not dist or max(dist)<.2:item['flags'].append('alternate_components_collapsed')
    item['flags']=sorted(set(item['flags']))
    if item['flags']:item['classification']='not_supported_without_further_review'
    return item

def prepare(base,output,software,possible_solvents=(),settings=None,site_ids=None):
    cfg=config(settings);out=Path(output);base=Path(base);start=time.perf_counter()
    if out.exists():raise FileExistsError(str(out))
    audit=paired_bundle(base,'case');out.mkdir();frozen=out/'baseline';frozen.mkdir()
    for ext,p in audit['files'].items():shutil.copy2(p,frozen/('case.'+ext))
    scan=detect(frozen,possible_solvents=possible_solvents);sites=[];proposals=[];deferred=[];screened_sites=0
    for site in scan['sites']:
        if site_ids is not None and site['id'] not in site_ids:continue
        if site['status']=='screenable':
            if screened_sites>=cfg['max_sites']:
                deferred.append(dict(site,deferred_reason='site_budget_reached',AB=None));continue
            screened_sites+=1
        proposal_start=time.perf_counter()
        generated=propose(frozen,site,cfg);sites.append(dict(site,proposal_result=generated,proposal_seconds=time.perf_counter()-proposal_start))
        for i,pose in enumerate(generated['poses']):
            hypothesis=dict(pose['config'],adp=cfg['short_adp'],basis={'site':site['id'],'current_density_evidence':pose['peak_support'],'source_hashes':generated['source_hashes']})
            proposals.append({'site_id':site['id'],'density_score':pose['score'],'plan':{'name':f's{len(sites)}p{i+1}','kind':'diagnostic_refinement','cycles':cfg['short_cycles'],
                'reason':'Density-guided '+site['family']+' alternate pose','evidence':hypothesis['basis'],'focus':site['atoms'],'common_disorder':hypothesis}})
    from native_resources import effective
    plan={'schema':1,'baseline':str(frozen),'output':str(out),'software':software,'settings':cfg,'sites':sites,'deferred_sites':deferred,'proposals':proposals,
          'native_resources':effective(),'input_hashes':{p.name:digest(p) for p in frozen.iterdir() if p.is_file()},
          'implementation_hashes':{p.name:digest(p) for p in Path(__file__).parent.glob('*.py')},
          'software_hashes':{k:digest(p) for k,p in software.items()},'preparation_seconds':time.perf_counter()-start}
    write_json(out/'plan.json',plan);return plan

def run(path):
    plan=json.loads(Path(path).read_text('utf8'));out=Path(plan['output']);base=Path(plan['baseline']);cfg=config(plan['settings']);start=time.perf_counter()
    if set(plan['software'])!={'shelxl','platon'}:raise ValueError('Both actual native software paths required')
    if any(digest(plan['software'][k])!=h for k,h in plan['software_hashes'].items()):raise ValueError('Native executable changed after preparation')
    if any(digest(base/f)!=h for f,h in plan['input_hashes'].items()):raise ValueError('Frozen input changed')
    if any(digest(Path(__file__).parent/f)!=h for f,h in plan['implementation_hashes'].items()):raise ValueError('Prepared code changed; prepare a new comparison')
    short=out/'screen';short.mkdir(exist_ok=False);screens=[]
    for proposal in plan['proposals']:
        result=short_trial(base,short/proposal['plan']['name'],proposal['plan'],plan['software'],plan['native_resources']);result['site_id']=proposal['site_id'];screens.append(result)
        write_json(out/'screen_progress.json',{'completed':screens,'pending':len(plan['proposals'])-len(screens)})
    finalists=[];promotion_decisions=[]
    for site in plan['sites']:
        selected,decisions=screen_decisions([s for s in screens if s['site_id']==site['id']],cfg['finalists_per_site'])
        finalists.extend(selected)
        promotion_decisions.extend(dict(d,site_id=site['id']) for d in decisions)
    if not finalists:
        report={'status':'no_supported_finalists','screen_count':len(screens),'full_count':0,'promoted':[],
                'not_promoted':[s['name'] for s in screens],'screens':screens,'results':[],'comparisons':[],
                'promotion_decisions':promotion_decisions,'sites':plan['sites'],'deferred_sites':plan.get('deferred_sites',[]),
                'preparation_seconds':plan['preparation_seconds'],'run_seconds':time.perf_counter()-start,
                'model_adopted':False,'AB':None,'source_unchanged':all(digest(base/f)==h for f,h in plan['input_hashes'].items()),
                'next_action':'Inspect site review reasons/density evidence; unchanged baseline retained, no redundant full control run.'}
        write_json(out/'comparison.json',report);return report
    full=[{'name':'control','kind':'baseline','cycles':cfg['full_cycles'],'reason':'Unchanged same-cycle baseline','evidence':'Same HKL, model and refinement controls'}]
    for screen in finalists:
        for adp in ['ISO','ANI','MAJOR_ANI']:
            original=screen['plan'];candidate=dict(original,name=original['name']+'_'+adp.lower(),cycles=cfg['full_cycles'],common_disorder=dict(original['common_disorder'],adp=adp))
            full.append(candidate)
    fullplan={'baseline':str(base),'output':str(out/'full'),'software':plan['software'],'shelxl_resources':plan['native_resources'],'trials':full,'stop_on_control_failure':True}
    write_json(out/'full_plan.json',fullplan);results=run_plan(out/'full_plan.json')
    comparisons=[quality_review(results[0],v) for v in results[1:]] if results and results[0]['status']=='completed' else []
    report={'status':'completed_diagnostic_comparison' if results and results[0]['status']=='completed' else 'control_failed','screen_count':len(screens),'full_count':len(results),'promoted':[x['name'] for x in finalists],
            'not_promoted':[x['name'] for x in screens if x not in finalists],'screens':screens,'results':results,'comparisons':comparisons,
            'promotion_decisions':promotion_decisions,'sites':plan['sites'],
            'stage_seconds':{'proposal':plan['preparation_seconds'],'short_native':sum(x['elapsed_s'] for x in screens),'full_comparison':sum(x.get('elapsed_s',0) for x in results)},
            'preparation_seconds':plan['preparation_seconds'],'run_seconds':time.perf_counter()-start,'model_adopted':False,'deferred_sites':plan.get('deferred_sites',[]),
            'scope':'Short screens have AB=null, not zero. Full finalists restart from identical baseline; no automatic final model acceptance.',
            'source_unchanged':all(digest(base/f)==h for f,h in plan['input_hashes'].items())}
    write_json(out/'comparison.json',report);return report

def main():
    p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(dest='command',required=True)
    a=sp.add_parser('prepare');a.add_argument('--baseline',required=True);a.add_argument('--output',required=True);a.add_argument('--profile',required=True)
    a.add_argument('--possible-solvents',nargs='*',default=[]);a.add_argument('--site-ids',nargs='*');a.add_argument('--settings')
    a=sp.add_parser('run');a.add_argument('--plan',required=True);args=p.parse_args()
    if args.command=='prepare':
        profile=json.loads(Path(args.profile).read_text('utf-8-sig'));settings=json.loads(Path(args.settings).read_text('utf8')) if args.settings else None
        value=prepare(args.baseline,args.output,{k:profile['tools'][k]['path'] for k in ['shelxl','platon']},args.possible_solvents,settings,args.site_ids)
        print(json.dumps({'plan':str(Path(args.output)/'plan.json'),'proposals':len(value['proposals'])},ensure_ascii=False))
    else:
        result=run(args.plan);print(json.dumps({k:result[k] for k in ['status','screen_count','full_count','promoted','run_seconds']},ensure_ascii=False))
if __name__=='__main__':main()
