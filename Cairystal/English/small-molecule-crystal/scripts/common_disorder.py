"""Bounded common-fragment hypotheses from the current model and Q peaks.

No reference models, model adoption, reflection deletion, upload or LLM calls.
Rigid solvent orientations do not cover ring puckering or internal flexibility.
"""
from pathlib import Path
import argparse, collections, hashlib, json, math, re, shutil, time
import gemmi
from structure_diagnostics import res_records, structure, digest, newjson
from split_fragment_seed import rotate

VERSION = 1
CATALOG = Path(__file__).resolve().parents[1] / 'assets/common_disorder_solvents.json'
SUPPORTED_AFIX = {13, 23, 33, 43, 93, 123, 137}

def norm(v): return math.sqrt(sum(x*x for x in v))
def sub(a,b): return [x-y for x,y in zip(a,b)]
def pos(cell,a):
    p=cell.orthogonalize(gemmi.Fractional(*a['xyz']));return [p.x,p.y,p.z]
def finite(x): return isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)
def load_catalog(): return json.loads(CATALOG.read_text('utf-8'))['solvents']
def normalize_solvents(values):
    data=json.loads(CATALOG.read_text('utf-8'));out=set()
    for value in values:
        key=value.strip().casefold();key=data['aliases'].get(key,key)
        if key not in data['solvents']:raise ValueError('Unknown solvent key: '+value)
        out.add(key)
    return out

def h_groups(parsed):
    """Return only explicit riding H groups, never guess a free H parent."""
    groups=collections.defaultdict(list);parent=None;unsupported=[]
    for a in parsed['atoms']:
        if a['element'].upper()!='H': parent=a;continue
        if (parent is None or a['afix'] not in SUPPORTED_AFIX or
            a['part']!=parent['part'] or a['residue']!=parent['residue']):
            unsupported.append(a['label'].upper());continue
        groups[parent['label'].upper()].append(a)
    return groups,unsupported

def graph_model(block,cell,atoms):
    heavy={a['label'].upper():a for a in atoms if a['element'].upper()!='H'}
    graph={k:set() for k in heavy};periodic=set()
    for i,(ka,a) in enumerate(heavy.items()):
        for kb,b in list(heavy.items())[i+1:]:
            cutoff=gemmi.Element(a['element']).covalent_r+gemmi.Element(b['element']).covalent_r+.22
            direct=norm(sub(pos(cell,a),pos(cell,b)))
            distance=cell.find_nearest_pbc_image(gemmi.Fractional(*a['xyz']),gemmi.Fractional(*b['xyz']),0).dist()
            if .65<distance<cutoff:
                graph[ka].add(kb);graph[kb].add(ka)
                if abs(direct-distance)>.01:periodic.update([ka,kb])
    return heavy,graph,periodic

def component(graph,start,cut=None):
    seen=set();todo=[start]
    while todo:
        k=todo.pop()
        if k in seen:continue
        seen.add(k)
        todo.extend(v for v in graph[k] if not cut or frozenset([k,v])!=frozenset(cut))
    return seen

def matches_template(keys,heavy,graph,template):
    elements=template['elements'];edges=template['bonds']
    tg={i:set() for i in range(len(elements))}
    for i,j in edges:tg[i].add(j);tg[j].add(i)
    if len(keys)!=len(elements):return False
    options={i:sorted(k for k in keys if heavy[k]['element'].upper()==elements[i].upper() and len(graph[k])==len(tg[i])) for i in tg}
    order=sorted(tg,key=lambda i:len(options[i]));mapping={}
    def visit(n):
        if n==len(order):return True
        i=order[n]
        for k in options[i]:
            if k in mapping.values():continue
            if any((j in tg[i])!=(v in graph[k]) for j,v in mapping.items()):continue
            mapping[i]=k
            if visit(n+1):return True
            del mapping[i]
        return False
    return visit(0)

def detect(directory,stem='case',possible_solvents=()):
    directory=Path(directory);b,cell,ops,atoms,parsed=structure(directory/(stem+'.cif'),directory/(stem+'.res'))
    heavy,g,periodic=graph_model(b,cell,atoms);hs,unsupported=h_groups(parsed)
    sites=[];used=set();known=normalize_solvents(possible_solvents);catalog=load_catalog()
    def add(family,keys,axis=None,solvent=None):
        keys=sorted(keys);identifier=family+'_'+('_'.join(axis) if axis else keys[0])
        if identifier in used:return
        used.add(identifier);holds=[];symmetry_sites=[]
        for k in sorted(set(keys)|set(axis or [])):
            a=heavy[k]
            if a['part']!=0 or a['residue']!='0' or a['afix']!=0 or a['encoded_sof']!=11 or a['occupancy']!=1:
                holds.append('existing_PART_RESI_AFIX_or_partial_occupancy:'+k)
            if k in periodic:holds.append('fragment_needs_periodic_assembly:'+k)
            count=sum(cell.find_nearest_pbc_image(gemmi.Fractional(*a['xyz']),gemmi.Fractional(*op.apply_to_xyz(a['xyz'])),0).dist()<.001 for op in ops)
            if count!=1:holds.append('special_position:'+k)
            if count!=1:
                symmetry_sites.append({'atom':k,'stabilizer_order':count,'physical_occupancy':a['occupancy'],
                    'encoded_SHELX_sof':a['encoded_sof'],
                    'operators':[op.triplet() for op in ops if cell.find_nearest_pbc_image(gemmi.Fractional(*a['xyz']),gemmi.Fractional(*op.apply_to_xyz(a['xyz'])),0).dist()<.001]})
            if a['Ueq'] is None or not finite(a['Ueq']) or a['Ueq']<=0:holds.append('invalid_Ueq:'+k)
        for k in unsupported:
            a=next(v for v in parsed['atoms'] if v['label'].upper()==k)
            if any(norm(sub(pos(cell,a),pos(cell,heavy[v])))<1.35 for v in keys):holds.append('unsupported_or_free_H_ownership:'+k)
        if family=='alkyl_chain':
            for k in keys:
                expected=4-len(g[k])
                if len(hs[k])!=expected or any(h['afix'] not in {23,33,137} for h in hs[k]):
                    holds.append('sp3_chain_needs_explicit_CH2_CH3_evidence:'+k)
            if any(norm(sub(pos(cell,heavy[k]),pos(cell,heavy[v])))<1.43 for k in keys for v in g[k]):holds.append('short_bond_not_established_as_single')
        if solvent and solvent not in known:holds.append('solvent_identity_not_supplied:'+solvent)
        sites.append({'id':identifier,'family':family,'atoms':keys,'axis':axis,'solvent':solvent,
            'status':'screenable' if not holds else 'needs_review','review_reasons':sorted(set(holds)),
            'special_position_evidence':symmetry_sites,
            'next_tool':'occupancy' if symmetry_sites else ('density-disorder' if not holds else 'initial-review'),
            'chemistry':'Current-model topology hypothesis; not independent atom typing or solvent identification.'})
    for k,a in heavy.items():
        if a['element'].upper()!='C':continue
        fs=[v for v in g[k] if heavy[v]['element'].upper()=='F' and len(g[v])==1]
        cs=[v for v in g[k] if heavy[v]['element'].upper()=='C']
        anchors=sorted(g[k]-set(fs))
        if len(fs)==3 and len(anchors)==1 and len(g[k])==4:add('cf3',fs,[anchors[0],k])
        ends=[v for v in cs if len(g[v])==1]
        anchors=sorted(g[k]-set(ends))
        if len(ends)==3 and len(anchors)==1 and len(g[k])==4:add('tert_butyl',ends,[anchors[0],k])
    # A chain may rotate about an internal bond rather than only its longest tail.
    # Retain up to three nested distal paths per end; each trial still changes one torsion.
    chains={}
    for k,a in heavy.items():
        for v in sorted(g[k]):
            tail=component(g,v,(k,v))
            if k in tail or not 2<=len(tail)<=7:continue
            if any(heavy[t]['element'].upper()!='C' or len(g[t])>2 for t in tail):continue
            end=sorted(t for t in tail if len(g[t])==1)
            if len(end)!=1:continue
            chains.setdefault(end[0],[]).append((tail,[k,v]))
    for alternatives in chains.values():
        for tail,axis in sorted(alternatives,key=lambda x:(-len(x[0]),x[1]))[:3]:
            add('alkyl_chain',tail,axis)
    visited=set()
    for k in heavy:
        if k in visited:continue
        comp=component(g,k);visited.update(comp)
        if len(comp)>10:continue
        for solvent,t in catalog.items():
            if matches_template(comp,heavy,g,t):add('solvent',comp,solvent=solvent)
    return {'schema':VERSION,'source_hashes':{ext:digest(directory/(stem+'.'+ext)) for ext in ['res','cif']},
        'catalog_sha256':digest(CATALOG),'possible_solvents':sorted(known),'sites':sites,'AI_calls':0,
        'scope':'Read-only topology screening; no disorder is asserted and no model is changed.'}

def positions(parsed,block,config):
    cell=gemmi.UnitCell(*[gemmi.cif.as_number(block.find_value('_cell_'+v)) for v in ['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']])
    amap={a['label'].upper():a for a in parsed['atoms']};selected=[k.upper() for k in config['atoms']]
    if not 2<=len(selected)<=16 or len(set(selected))!=len(selected) or not set(selected)<=amap.keys():raise ValueError('Bounded unique heavy-atom fragment required')
    points={k:pos(cell,amap[k]) for k in selected}
    angle=config['angle_deg'];shift=config.get('translation_A',[0,0,0])
    if not finite(angle) or abs(angle)>180 or len(shift)!=3 or any(not finite(v) for v in shift) or norm(shift)>1.25:raise ValueError('Invalid bounded rigid pose')
    axis_labels=config.get('axis')
    if axis_labels:
        if len(axis_labels)!=2 or len(set(axis_labels))!=2 or not set(axis_labels)<=amap.keys() or axis_labels[0] in selected:raise ValueError('Invalid shared rotation axis')
        p,q=[pos(cell,amap[k]) for k in axis_labels];axis=sub(q,p);length=norm(axis)
        if not .8<length<2.1:raise ValueError('Axis is not a directly assembled local bond')
        axis=[x/length for x in axis];origin=q
    else:
        origin=[sum(v[i] for v in points.values())/len(points) for i in range(3)];axis=config['rigid_axis']
        if len(axis)!=3 or any(not finite(v) for v in axis) or norm(axis)<.5:raise ValueError('Invalid rigid axis')
        axis=[v/norm(axis) for v in axis]
    def transformed(a,alternate):
        xyz=pos(cell,a)
        if not alternate:return xyz
        r=rotate(sub(xyz,origin),axis,math.radians(angle));return [origin[i]+r[i]+shift[i] for i in range(3)]
    return cell,amap,transformed

def generate(parsed,block,config):
    allowed={'atoms','axis','rigid_axis','angle_deg','translation_A','occupancy_start','parts','basis','adp'}
    if set(config)-allowed or not config.get('basis'):raise ValueError('Unexpected seed settings or missing evidence')
    cell,amap,transform=positions(parsed,block,config);keys=[k.upper() for k in config['atoms']]
    hs,unsupported=h_groups(parsed);selected=set(keys)
    for k in keys:selected.update(h['label'].upper() for h in hs[k])
    if selected.intersection(unsupported):raise ValueError('Unsupported H ownership')
    physical={gemmi.cif.as_string(r[0]).upper():gemmi.cif.as_number(r[1]) for r in block.find(['_atom_site_label','_atom_site_occupancy'])}
    context_keys=sorted(set(keys)|set(config.get('axis') or []))
    for k in context_keys:
        a=amap[k]
        if a['part'] or a['residue']!='0' or a['afix'] or a['encoded_sof']!=11 or a['element'].upper()=='H':raise ValueError('Requires full-occupancy general PART0 heavy fragment')
        if physical.get(k)!=1:raise ValueError('CIF physical occupancy is not full; PART SOF/special-site accounting requires review')
        if any(abs(float(v))>=5 for v in a['row'][2:5]):raise ValueError('Encoded/fixed coordinates need explicit review')
        if any(norm(sub(pos(cell,amap[h]),pos(cell,a)))<1.35 for h in unsupported):raise ValueError('Unsupported/free H near split fragment')
        for h in hs[k]:
            if h['encoded_sof']!=11 or len(h['adp_raw'])!=1 or not -2<=h['adp_raw'][0]<0:raise ValueError('Only parent-linked riding H ADP supported')
            if physical.get(h['label'].upper())!=1:raise ValueError('H physical occupancy is not full')
    ops=[gemmi.Op(gemmi.cif.as_string(v)) for v in block.find_values('_space_group_symop_operation_xyz')]
    if not ops:raise ValueError('Explicit symmetry required')
    for k in context_keys:
        if sum(cell.find_nearest_pbc_image(gemmi.Fractional(*amap[k]['xyz']),gemmi.Fractional(*op.apply_to_xyz(amap[k]['xyz'])),0).dist()<.001 for op in ops)!=1:raise ValueError('Special position needs explicit population accounting')
    pop=config['occupancy_start'];parts=config['parts'];used={abs(a['part']) for a in parsed['atoms']}
    if not finite(pop) or not .15<=pop<=.85:raise ValueError('Interior population seed required')
    if len(parts)!=2 or parts[0]==parts[1] or any(type(v)!=int or v<=0 or v in used for v in parts):raise ValueError('Two unused positive PARTs required')
    adp=config.get('adp','ISO')
    if adp not in {'ISO','ANI','MAJOR_ANI'}:raise ValueError('Explicit ISO/ANI/MAJOR_ANI seed required')
    fv=[v for r in parsed['rows'] if r[0].upper()=='FVAR' for v in r[1:]];index=len(fv)+1
    if index<2:raise ValueError('FVAR scale missing')
    ue={gemmi.cif.as_string(r[0]).upper():gemmi.cif.as_number(r[1]) for r in block.find(['_atom_site_label','_atom_site_U_iso_or_equiv'])}
    reserved=set(amap);mapping={}
    for k in sorted(selected):
        prefix=amap[k]['element'].upper();stem=k
        for i in range(1000):
            names=[stem+s for s in 'AB']
            if all(len(n)<=4 and re.fullmatch('[A-Za-z][A-Za-z0-9]*',n) and n not in reserved for n in names):break
            stem=prefix+str(i+1)
        else:raise ValueError('No collision-free four-character labels available')
        mapping[k]=dict(zip('AB',names));reserved.update(names)
    drops=[]
    for i,r in enumerate(parsed['rows']):
        if r[0].upper()!='AFIX' or int(r[1])==0:continue
        end=next((j for j in range(i+1,len(parsed['rows'])) if parsed['rows'][j][0].upper() in {'AFIX','HKLF'}),len(parsed['rows']))
        group={v[0].upper() for v in parsed['rows'][i+1:end] if v[0].upper() in amap}
        if group&selected:
            if not group<=selected or any(amap[v]['element'].upper()!='H' for v in group):raise ValueError('Partial/rigid AFIX group needs review')
            drops.append(i)
    rows=[]
    for n,suffix in enumerate('AB'):
        rows.append(['PART',str(parts[n])]);sof=str((1 if n==0 else -1)*(10*index+1))
        for k in keys:
            a=amap[k];u=ue.get(k)
            if not finite(u) or u<=0:raise ValueError('Positive paired Ueq needed')
            def atomrow(a,u):
                f=cell.fractionalize(gemmi.Position(*transform(a,n==1)))
                return [mapping[a['label'].upper()][suffix],str(a['sfac_index']),*[f'{v:.7f}' for v in [f.x,f.y,f.z]],sof,f'{u:.7f}']
            rows.append(atomrow(a,u))
            if hs[k]:
                if len({h['afix'] for h in hs[k]})!=1:raise ValueError('Multiple H geometry groups on one parent')
                rows.append(['AFIX',str(hs[k][0]['afix'])])
                rows.extend(atomrow(h,h['adp_raw'][0]) for h in hs[k]);rows.append(['AFIX','0'])
        rows.append(['PART','0'])
    # Corresponding 1,2 and 1,3 distances are equated; no arbitrary ideal distances.
    heavy,g,periodic=graph_model(block,cell,parsed['atoms'])
    if set(keys)&periodic:raise ValueError('Periodic assembly must be resolved before splitting')
    bonds=set();one_three=set()
    for k in keys:
        for j in g[k]:
            if j in keys or j in (config.get('axis') or []):bonds.add(tuple(sorted([k,j])))
    participating=set(keys)|set(config.get('axis') or [])
    for k in participating:
        for x in g[k]&participating:
            for y in g[k]&participating:
                if x<y and (x in keys or y in keys):one_three.add((x,y))
    for pairs,sigma in [(bonds,.02),(one_three,.04)]:
        for x,y in sorted(pairs):
            rows.append(['SADI',str(sigma),mapping.get(x,{}).get('A',x),mapping.get(y,{}).get('A',y),mapping.get(x,{}).get('B',x),mapping.get(y,{}).get('B',y)])
    for suffix in 'AB':
        labels=[mapping[k][suffix] for k in keys]
        if adp=='ANI' or (adp=='MAJOR_ANI' and suffix=='A'):rows.extend([['ANIS',*labels],['RIGU','0.004','0.004',*labels]])
        rows.append(['SIMU','0.04','0.08','1.7',*labels])
    pivot=(config.get('axis') or [None,None])[1]
    if pivot in keys:
        rows.extend([[card,mapping[pivot]['A'],mapping[pivot]['B']] for card in ['EXYZ','EADP']])
    return {'rows':rows,'selected':sorted(selected),'original_H_groups_validated':len(drops),'mapping':mapping,'free_variable_number':index,'free_variable_start':pop,'starting_ADP':adp,
        'basis':config['basis'],'H_parent_groups':{k:[h['label'] for h in hs[k]] for k in keys},'model_adopted':False,
        'limitations':['Geometry and population are hypotheses. Equal branch distances do not prove correctness.','No special-site, pre-existing disorder, free H or flexible-ring automatic treatment.']}

def screen_poses(directory,site,stem='case',min_peak=.35):
    b,cell,ops,atoms,p=structure(Path(directory)/(stem+'.cif'),Path(directory)/(stem+'.res'))
    heavy,g,periodic=graph_model(b,cell,atoms);keys=site['atoms'];candidates=[]
    if site['status']!='screenable':return []
    used={abs(a['part']) for a in p['atoms']};parts=[i for i in range(1,100) if i not in used][:2]
    rotations=[]
    angles=[-60,-40,-20,20,40,60] if site['family']!='alkyl_chain' else [-120,-60,-30,30,60,120,180]
    if site['axis']:rotations=[{'axis':site['axis'],'angle_deg':x} for x in angles]
    else:
        rotations=[{'rigid_axis':axis,'angle_deg':angle} for axis in [[1,0,0],[0,1,0],[0,0,1]] for angle in [-60,-30,30,60]]
        for q in sorted(p['peaks'],key=lambda x:-x['height'])[:30]:
            if q['height']<min_peak:continue
            qp=pos(cell,q)
            for k in keys:
                v=sub(qp,pos(cell,heavy[k]))
                if .3<=norm(v)<=1.0:rotations.append({'rigid_axis':[1,0,0],'angle_deg':0,'translation_A':v})
    for pose in rotations[:80]:
        config=dict(pose,atoms=keys,parts=parts,occupancy_start=.7,adp='ISO',basis='Current Q-peak-supported local rigid-pose hypothesis')
        _,amap,transform=positions(p,b,config);matches=[];taken=set();clashes=[]
        for k in keys:
            xyz=transform(amap[k],True);old_dist=min(norm(sub(xyz,pos(cell,heavy[v]))) for v in keys if heavy[v]['element']==heavy[k]['element'])
            if old_dist<.30:continue
            choices=[]
            for q in p['peaks']:
                if q['label'] in taken or q['height']<min_peak:continue
                f=cell.fractionalize(gemmi.Position(*xyz));dist=cell.find_nearest_pbc_image(f,gemmi.Fractional(*q['xyz']),0).dist()
                if dist<=.45:choices.append((dist,-q['height'],q))
            if choices:
                dist,_,q=min(choices,key=lambda x:(x[0],x[1],x[2]['label']));taken.add(q['label']);matches.append({'atom':k,'peak':q['label'],'height':q['height'],'distance_A':dist})
            # Same-asymmetric-unit and symmetry mate short contacts, excluding a declared bonded anchor.
            f=cell.fractionalize(gemmi.Position(*xyz))
            for other,a in heavy.items():
                for op in ops:
                    transformed=op.apply_to_xyz(a['xyz']);d=cell.find_nearest_pbc_image(f,gemmi.Fractional(*transformed),0).dist()
                    if op.triplet()=='x,y,z' and other in keys:continue
                    if op.triplet()=='x,y,z' and other in g[k]:continue
                    lower=.65*(gemmi.Element(amap[k]['element']).covalent_r+gemmi.Element(a['element']).covalent_r)
                    if d<lower:clashes.append([k,other,op.triplet(),d])
        minimum=3 if site['family']=='solvent' and len(keys)>5 else 2
        if len(matches)<minimum or clashes:continue
        score=sum(m['height']/(1+m['distance_A']) for m in matches)
        candidates.append({'config':config,'peak_support':matches,'score':score,'short_contacts':clashes})
    # Equivalent endpoint sets must not consume the retry budget twice.
    result=[]
    for c in sorted(candidates,key=lambda v:-v['score']):
        _,amap,transform=positions(p,b,c['config']);pose={k:transform(amap[k],True) for k in keys}
        if any(all(min(norm(sub(pose[k],v)) for j,v in old['pose'].items() if amap[j]['element']==amap[k]['element'])<.15 for k in keys) for old in result):continue
        result.append(dict(c,pose=pose))
    return [{k:v for k,v in item.items() if k!='pose'} for item in result[:2]]

def prepare(directory,output,stem='case',possible_solvents=(),software=None):
    from crystal_runtime import paired_bundle
    start=time.perf_counter();base=Path(directory);out=Path(output)
    if out.exists():raise FileExistsError(str(out))
    audit=paired_bundle(base,stem);out.mkdir(parents=True)
    frozen=out/'baseline';frozen.mkdir()
    for ext,path in audit['files'].items():shutil.copy2(path,frozen/('case.'+ext))
    scan=detect(frozen,possible_solvents=possible_solvents);newjson(out/'screening.json',scan)
    plans=[{'name':'control','kind':'baseline','cycles':20,'reason':'Unchanged contemporaneous continuation','evidence':'Same frozen HKL, weights, atom model and setting'}];sites=[]
    for site in scan['sites']:
        poses=screen_poses(frozen,site);site=dict(site,candidate_poses=len(poses))
        if not poses and site['status']=='screenable':site.update(status='insufficient_density_support',review_reasons=['No distinct Q peaks support a tested alternate pose; no split generated.'])
        for i,pose in enumerate(poses):
            for adp in ['ISO','ANI']:
                config=dict(pose['config'],adp=adp,basis={'site':site['id'],'Q_peak_support':pose['peak_support'],'interpretation':'Peak list is truncated and phase-biased; trial evidence, not proof.'})
                plan={'name':f's{len(sites)+1}_p{i+1}_{adp.lower()}','kind':'diagnostic_refinement','cycles':30,'reason':site['family']+' alternate orientation hypothesis','evidence':config['basis'],'focus':site['atoms'],'common_disorder':config}
                # Dry build applies the same constraint/reference/H guards as execution.
                try:
                    from candidate_trials import build
                    build(frozen,plan,out)
                    plans.append(plan)
                except (ValueError,KeyError) as exc:site.setdefault('build_rejections',[]).append({'candidate':plan['name'],'error':str(exc)})
        sites.append(site)
    truncated=max(0,len(plans)-17)
    if truncated:plans=plans[:17] # Baseline + at most 16 native comparisons.
    for ext,path in audit['files'].items():
        if digest(path)!=audit['source_sha256'][ext] or digest(frozen/('case.'+ext))!=audit['source_sha256'][ext]:raise ValueError('Source changed while preparing immutable trial baseline')
    job={'baseline':str(frozen),'output':str(out/'trials'),'software':software or {},'trials':plans,
         'baseline_sha256':{p.name:digest(p) for p in frozen.iterdir() if p.is_file()},
         'implementation_sha256':{str(p):digest(p) for p in [Path(__file__),Path(__file__).with_name('candidate_trials.py'),CATALOG]}}
    newjson(out/'plan.json',job)
    result={'status':'prepared' if len(plans)>1 else 'needs_review','sites':sites,'trial_count':len(plans)-1,'unrun_due_to_budget':truncated,'plan':str(out/'plan.json'),'AI_calls':0,'model_adopted':False,'elapsed_s':time.perf_counter()-start,'source_hashes':audit['source_sha256'],
        'retained_baseline':str(frozen),'limits':'At most 16 alternatives. Only supplied solvent identities; no automatic final model selection. Accepted candidates still require the existing complete validation and bilingual report pipeline.'}
    newjson(out/'preparation.json',result);return result

def pairing_review(directory):
    from crystal_runtime import paired_bundle
    try:
        result=paired_bundle(Path(directory),'case')
        return {'status':'file_pairing_passed','native_gate':result['gate']['status'],'scientific_acceptance':False}
    except (ValueError,KeyError,IndexError) as exc:
        return {'status':'needs_specialist_review','error':str(exc),'scientific_acceptance':False}

def run_prepared(path):
    from candidate_trials import run_plan
    from compare_diagnostic_trials import compare
    job=json.loads(Path(path).read_text('utf-8'))
    if set(job['software'])!={'shelxl','platon'}:raise ValueError('Actual SHELXL and PLATON executables required')
    if any(not Path(p).is_file() for p in job['software'].values()):raise ValueError('Configured native executable is missing; no trials started')
    for name,h in job['baseline_sha256'].items():
        if Path(name).name!=name or digest(Path(job['baseline'])/name)!=h:raise ValueError('Prepared baseline changed')
    for name,h in job['implementation_sha256'].items():
        if digest(name)!=h:raise ValueError('Prepared generator implementation changed; prepare a new comparison')
    results=run_plan(path);control=results[0]
    summary={'cases':[compare(control,x) for x in results[1:]] if control['status']=='completed' else [],'control_status':control['status'],'model_adopted':False,'AI_calls':0,
        'next':'Review compact comparison, then complete the selected candidate through weighting, pairing, local AB, authorized IUCr PDF and both Word reports. No candidate is silently substituted.'}
    # Additional population/collapse checks use this run's models only.
    for item,trial in zip(summary['cases'],results[1:]):
        if trial['status']!='completed':
            item['AB']=None;item['AB_counts']=None;continue
        item['final_pairing_screen']=pairing_review(Path(trial['diagnostic']).parent/'paired')
        if item['final_pairing_screen']['status']!='file_pairing_passed':item['flags'].append('paired_bundle_requires_specialist_review')
        diag=json.loads(Path(trial['diagnostic']).read_text('utf-8'));amap={a['label'].upper():a for a in diag['all_atoms']};split=next(e['split_fragment'] for e in trial['edits'] if 'split_fragment' in e);mapping=split['mapping']
        missing=[n for m in mapping.values() for n in m.values() if n not in amap]
        if missing:
            item['flags'].append('native_atom_or_H_missing_after_trial');item['missing_labels']=missing;item['classification']='not_supported_without_further_review';continue
        pops=[amap[n]['occupancy'] for m in mapping.values() for n in m.values() if amap[n]['element']!='H']
        item['population_range']=[min(pops),max(pops)] if all(finite(p) for p in pops) else None
        if any(not finite(p) or not .05<=p<=.95 for p in pops):item['flags'].append('minor_population_unresolved_or_at_boundary')
        for parent,children in split.get('H_parent_groups',{}).items():
            for suffix in 'AB':
                pa=amap[mapping[parent][suffix]]
                for child in children:
                    ha=amap[mapping[child.upper()][suffix]]
                    if ha['part']!=pa['part'] or ha['occupancy']!=pa['occupancy']:item['flags'].append('H_parent_PART_or_population_mismatch')
        if trial.get('gate')!='numerically_converged_requires_chemical_validation':item['flags'].append('native_refinement_gate_requires_review')
        cell=gemmi.UnitCell(*diag['cell']);pairs=[]
        for m in mapping.values():
            x,y=[amap[m[s]] for s in 'AB']
            if x['element']=='H':continue
            pairs.append(norm(sub(pos(cell,x),pos(cell,y))))
        item['max_branch_atom_separation_A']=max(pairs)
        if max(pairs)<.2:item['flags'].append('alternate_components_collapsed')
        if item['flags']:item['classification']='not_supported_without_further_review'
    target=Path(job['output'])/'comparison.json';newjson(target,summary);return summary

def main():
    parser=argparse.ArgumentParser(description=__doc__);subp=parser.add_subparsers(dest='command',required=True)
    for mode in ['scan','prepare']:
        p=subp.add_parser(mode);p.add_argument('--baseline',required=True);p.add_argument('--stem',default='case');p.add_argument('--output',required=True);p.add_argument('--possible-solvents',nargs='*',default=[])
        if mode=='prepare':p.add_argument('--profile')
    p=subp.add_parser('run');p.add_argument('--plan',required=True)
    args=parser.parse_args()
    if args.command=='scan':
        value=detect(args.baseline,args.stem,args.possible_solvents);newjson(args.output,value)
    elif args.command=='prepare':
        profile=json.loads(Path(args.profile).read_text('utf-8-sig')) if args.profile else None
        software={k:profile['tools'][k]['path'] for k in ['shelxl','platon']} if profile else None
        value=prepare(args.baseline,args.output,args.stem,args.possible_solvents,software)
    else:value=run_prepared(args.plan)
    print(json.dumps(value,ensure_ascii=False,allow_nan=False))
if __name__=='__main__':main()
