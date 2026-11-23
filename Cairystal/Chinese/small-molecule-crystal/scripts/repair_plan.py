"""Compile evidence-backed local repair recipes into frozen, comparable native trials.

No alert number alone authorizes or defines a structural edit. No automatic winner.
"""
import argparse, json, math, re, shutil, sys
from pathlib import Path
from structure_diagnostics import structure, digest, newjson, analyse
from candidate_trials import build, run_plan

RECIPES={
 'restraint_strength': {'alerts':['213','214','234','330','331','332','333','334','335','336'], 'source':'Current local restraint and chemical hypothesis; controlled sigma comparison', 'required':['instruction','factors','basis'], 'description':'Keep target geometry, cutoff and atoms unchanged; vary only one explicit local restraint sigma, stronger/control/weaker.'},
 'occupancy_stability': {'alerts':['214','230','234','241','242'], 'source':'Current complementary two-PART model; independent-start sensitivity test', 'required':['fvar_index','starts','basis'], 'description':'Restart an existing balanced SOF-only complementary population at multiple interior values; compare final populations/coordinates without adopting a model.'},
 'remove_extinction': {'alerts':['031'], 'source':'checkcif:100; IUCr PLAT031', 'required':['basis'], 'description':'Compare removal of a paired weak extinction coefficient (<3.33 su), same raw data.'},
 'release_damping': {'alerts':['936','731','732'], 'source':'checkcif:348-351,422; SHELXL DAMP', 'required':['basis'], 'description':'Isolated final full-matrix comparison without an existing DAMP; recheck convergence and covariance.'},
 'resolution_window': {'alerts':['019','020','023','026','027','028','029','905','906','910','911','912','913','THETM01','RINTA01'], 'source':'checkcif:85-99,384-406,519; SHELXL SHEL', 'required':['d_min_A','basis'], 'description':'Explicit resolution sensitivity trial; preserve HKL, report excluded records and completeness, never rank against full-data R.'},
 'water_orient': {'alerts':['420','417'], 'source':'ppt:229,260-265; checkcif:261,314-315', 'required':['parent','hydrogens','acceptors','basis'], 'description':'Existing full-occupancy water H: unchanged control, fixed current vectors and two rigid orientation hypotheses.'},
 'reflection_omit': {'alerts':['919','934'], 'source':'ppt:305-306; checkcif:409,418', 'required':['hkls','basis'], 'description':'Fixed-list <=20 active >10 sigmaW OMIT sensitivity comparison; preserve measured HKL; no iterative pruning or winner ranking.'},
 'element_scan': {'alerts':['241','242'], 'source':'ppt:248; checkcif:232,239', 'required':['atom','elements'], 'description':'One-site supplied C/N/O alternatives; preserve SFAC order; derive UNIT.'},
 'adp_local': {'alerts':['213','214','220','221','230','232','234'], 'source':'ppt:229,246-248; checkcif:203,209,212,218,222,227,229', 'required':['atoms','methods'], 'description':'Separate local RIGU/DELU/SIMU/ISOR or ISO hypotheses, never blanket restraints.'},
 'geometry_local': {'alerts':[], 'source':'ppt:229-230,310', 'required':['restraint','atoms','sigma','basis'], 'description':'One explicit DFIX/DANG/SADI/FLAT hypothesis with chemical target/equivalence basis.'},
 'h_freeze': {'alerts':['080','SHFSU01'], 'source':'ppt:261,265,307; checkcif:132,145', 'required':['parent'], 'description':'Existing riding H group to AFIX 3 without deleting/recreating H or changing SOF/U.'},
 'oh_rotate': {'alerts':['420'], 'source':'ppt:229,260-262; checkcif:314', 'required':['parent','anchor','angles'], 'description':'Existing simple full-occupancy C-O-H rotation candidates with AFIX 3; no bond count changes.'},
 'omit_map': {'alerts':['097','098','306','430'], 'source':'ppt:264,317; checkcif:153,155,261', 'required':['atoms'], 'description':'Local atom-omission L.S. 0 map diagnostic, not reflection OMIT or a refined final model.'},
}

def checked_number(value,low,high,name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:raise ValueError(f'{name} must be finite in [{low},{high}]')
    return value

def compile_trials(base,request):
    recipe=request.get('recipe');params=request.get('parameters',{})
    if recipe not in RECIPES:raise ValueError('Unknown repair recipe')
    if set(request)-{'recipe','parameters','reason','evidence','cycles'}:raise ValueError('Unknown request fields')
    if not isinstance(params,dict) or not isinstance(request.get('reason'),str) or not request['reason'].strip() or not request.get('evidence'):raise ValueError('Explicit reason and current-case evidence are required')
    b,cell,ops,atoms,parsed=structure(Path(base)/'case.cif',Path(base)/'case.res')
    amap={a['label'].upper():a for a in parsed['atoms']}
    if len(amap)!=len(parsed['atoms']):raise ValueError('Unique atom labels required')
    cycles=request.get('cycles',20)
    if isinstance(cycles,bool) or not isinstance(cycles,int) or not 1<=cycles<=100:raise ValueError('Cycles must be an integer in 1..100')
    def fields(required,optional=()):
        if set(params)-set(required)-set(optional) or set(required)-set(params):raise ValueError('Recipe fields: required '+str(required)+' optional '+str(optional))
    def names(values,minimum=1,maximum=12):
        if not isinstance(values,list) or not minimum<=len(values)<=maximum or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,3}',x) for x in values):raise ValueError('Explicit bounded atom label list required (no ranges, wildcards, symmetry selectors)')
        result=[s.upper() for s in values]
        if len(set(result))!=len(result) or not set(result)<=set(amap):raise ValueError('Repeated/unknown target atom')
        return result
    def base_trial(name):return {'name':name,'kind':'diagnostic_refinement','cycles':cycles,'reason':request['reason'],'evidence':request['evidence']}
    variants=[]
    if recipe=='restraint_strength':
        fields(['instruction','factors','basis'])
        from restraint_strength import variants as strength_variants
        if not isinstance(params['basis'],str) or not params['basis'].strip():raise ValueError('Chemical restraint basis required')
        for i,v in enumerate(strength_variants(base,params['instruction'],params['factors'])):
            variants.append(dict(base_trial('sigma_'+str(i+1)),focus=v['atoms'],remove_restraints=[v['original']],add_restraints=[v['replacement']]))
    elif recipe=='occupancy_stability':
        fields(['fvar_index','starts','basis'])
        from population_stability import context
        context(base,params['fvar_index'])
        if not isinstance(params['basis'],str) or not params['basis'].strip():raise ValueError('Disorder hypothesis basis required')
        starts=params['starts']
        if not isinstance(starts,list) or not 2<=len(starts)<=5 or len(set(starts))!=len(starts):raise ValueError('Two to five distinct initial populations required')
        for i,value in enumerate(starts):
            checked_number(value,.1,.9,'occupancy start')
            variants.append(dict(base_trial('population_'+str(i+1)),occupancy_start=dict(fvar_index=params['fvar_index'],value=value,basis=params['basis'])))
    elif recipe in {'remove_extinction','release_damping','resolution_window'}:
        fields(RECIPES[recipe]['required'])
        if not isinstance(params['basis'],str) or not params['basis'].strip():raise ValueError('Evidence basis required')
        variants.append(dict(base_trial(recipe),control_change=dict(params,mode=recipe)))
    elif recipe=='water_orient':
        fields(['parent','hydrogens','acceptors','basis']);parent=names([params['parent']])[0];hs=names(params['hydrogens'],2,2)
        if not isinstance(params['basis'],str) or not params['basis'].strip() or not isinstance(params['acceptors'],list) or len(params['acceptors'])!=2:raise ValueError('Two explicit acceptor images and water/acceptor chemical basis required')
        cfg=dict(parent=parent,hydrogens=hs,basis=params['basis'])
        variants.append(dict(base_trial('water_fixed_vectors'),focus=[parent],water_orientation=dict(cfg,mode='freeze',acceptors=[])))
        for i,targets in enumerate([params['acceptors'],list(reversed(params['acceptors']))]):
            variants.append(dict(base_trial('water_pose_'+str(i+1)),focus=[parent],water_orientation=dict(cfg,mode='orient',acceptors=targets)))
    elif recipe=='reflection_omit':
        fields(['hkls','basis'])
        from reflection_omit_trial import validate_list
        validate_list(params['hkls'])
        if not isinstance(params['basis'],str) or not params['basis'].strip():raise ValueError('Explicit current-case investigation basis required')
        variants.append(dict(base_trial('fixed_reflection_omit'),reflection_omit=params))
    elif recipe=='element_scan':
        fields(['atom','elements']);target=names([params['atom']])[0];els=params['elements']
        if not isinstance(els,list) or not 1<=len(els)<=3 or len(set(els))!=len(els) or not set(els)<={'C','N','O'}:raise ValueError('Supply one to three distinct C/N/O candidates')
        if amap[target]['element'] not in {'C','N','O'}:raise ValueError('Light-atom scan supports C/N/O sites only')
        # Attached H must be reviewed as a separate chemical model, not silently retained.
        pi=parsed['atoms'].index(amap[target])
        if pi+1<len(parsed['atoms']) and parsed['atoms'][pi+1]['afix'] and parsed['atoms'][pi+1]['element']=='H':raise ValueError('Type change affects riding H; use a reviewed full chemical/H plan')
        for el in els:
            if el not in parsed['sfac']:raise ValueError('Candidate element absent from supplied SFAC')
            if el!=amap[target]['element']:
                # Keep labels consistent with the trial's scattering type; do not create a naming-only PLAT017.
                available=next((el+str(i) for i in range(1,1000) if (el+str(i)).upper() not in amap),None)
                if available is None:raise ValueError('No free short element-consistent atom label')
                variants.append(dict(base_trial('element_'+el.lower()),element_changes={target:el},rename={target:available},focus=[available]))
    elif recipe=='adp_local':
        fields(['atoms','methods'],['sigma','terminal_sigma','cutoff']);selected=names(params['atoms']);methods=params['methods']
        if not isinstance(methods,list) or not methods or len(set(methods))!=len(methods) or not set(methods)<={'RIGU','DELU','SIMU','ISOR','ISO'}:raise ValueError('Explicit ADP method list required')
        if any(amap[n]['element']=='H' or len(amap[n]['adp_raw'])!=6 for n in selected):raise ValueError('ADP recipes require selected anisotropic non-H atoms')
        sigma=checked_number(params.get('sigma',.04),.001,.5,'sigma');terminal=checked_number(params.get('terminal_sigma',.08),.001,.5,'terminal_sigma');cutoff=checked_number(params.get('cutoff',1.7),.5,4,'cutoff')
        if len({(amap[n]['part'],amap[n]['residue']) for n in selected})!=1:raise ValueError('Cross-PART/RESI ADP restraints require separate review')
        for method in methods:
            if method in {'RIGU','DELU','SIMU'} and len(selected)<2:raise ValueError('Pair/group ADP restraint requires at least two atoms')
            p=dict(base_trial('adp_'+method.lower()),focus=selected)
            if method=='ISO':p['isotropic']=selected
            else:p['add_restraints']=[f'{method} {sigma:g} {terminal:g} '+(f'{cutoff:g} ' if method=='SIMU' else '')+' '.join(selected)]
            variants.append(p)
    elif recipe=='geometry_local':
        fields(['restraint','atoms','sigma','basis'],['target']);method=params['restraint'];selected=names(params['atoms']);sigma=checked_number(params['sigma'],.005,.2,'geometry sigma')
        if method not in {'DFIX','DANG','SADI','FLAT'} or not isinstance(params['basis'],str) or not params['basis'].strip():raise ValueError('Explicit geometry basis and supported method required')
        if any(amap[n]['element']=='H' for n in selected):raise ValueError('Hydrogen geometry needs a separate parent-aware route')
        if len({(amap[n]['part'],amap[n]['residue']) for n in selected})!=1:raise ValueError('Cross-PART/RESI geometry needs explicit mapping')
        target=params.get('target')
        if method in {'DFIX','DANG'}:
            if len(selected)!=2:raise ValueError('One explicit distance pair per geometry trial')
            checked_number(target,.7,4,'distance target')
            line=f'{method} {target:g} {sigma:g} '+' '.join(selected)
        else:
            if 'target' in params or len(selected)<4 or (method=='SADI' and len(selected)%2):raise ValueError('SADI needs >=2 distinct pairs; FLAT >=4 atoms; neither takes target')
            line=f'{method} {sigma:g} '+' '.join(selected)
        p=dict(base_trial('geometry_'+method.lower()),add_restraints=[line],focus=selected)
        if method in {'DFIX','DANG'}:p['geometry_checks']=[{'atoms':selected,'range':[target-3*sigma,target+3*sigma],'basis':params['basis']}]
        variants.append(p)
    elif recipe=='h_freeze':
        fields(['parent']);parent=names([params['parent']])[0]
        variants.append(dict(base_trial('h_fixed_vector'),focus=[parent],hydrogen_riding={'parent':parent,'mode':'freeze'}))
    elif recipe=='oh_rotate':
        fields(['parent','anchor','angles']);parent,anchor=names([params['parent'],params['anchor']]);angles=params['angles']
        if not isinstance(angles,list) or not 1<=len(angles)<=8:raise ValueError('Supply 1..8 bounded OH rotation angles')
        for i,angle in enumerate(angles):
            checked_number(angle,-360,360,'angle')
            variants.append(dict(base_trial('oh_pose_'+str(i+1)),focus=[parent],hydrogen_riding={'parent':parent,'anchor':anchor,'mode':'rotate_oh','angle_degrees':angle}))
    elif recipe=='omit_map':
        fields(['atoms']);selected=names(params['atoms'])
        variants.append(dict(base_trial('omit_map'),kind='omit_map',cycles=0,omit_atoms=selected,focus=selected))
    if not variants:raise ValueError('No changed hypothesis to test')
    control={'name':'control','kind':'baseline','cycles':cycles,'reason':'Unchanged contemporaneous continuation','evidence':'Same frozen data, starting model, WGHT and setting as every alternative'}
    return [control]+variants

def prepare(directory,stem,request,profile,output):
    from crystal_runtime import paired_bundle
    out=Path(output)
    if out.exists():raise FileExistsError(str(out))
    audit=paired_bundle(directory,stem);out.mkdir(parents=True);newjson(out/'request.json',request)
    try:
        base=out/'baseline';base.mkdir()
        for ext,p in audit['files'].items():shutil.copy2(p,base/('case.'+ext))
        trials=compile_trials(base,request);previews=out/'preview';previews.mkdir()
        for trial in trials:
            text,edits=build(base,trial,previews);(previews/(trial['name']+'.ins')).write_text(text,encoding='ascii');newjson(previews/(trial['name']+'.json'),edits)
        diag=analyse(base,focus=list({x for p in trials for x in p.get('focus',[])}));newjson(out/'before.json',diag)
        for ext,path in audit['files'].items():
            if digest(path)!=audit['source_sha256'][ext] or digest(base/('case.'+ext))!=audit['source_sha256'][ext]:raise ValueError('Input changed during preparation')
        software={k:profile['tools'][k]['path'] for k in ['shelxl','platon']}
        hashes={k:digest(p) for k,p in software.items()}
        for k,h in hashes.items():
            if profile['tools'][k].get('sha256')!=h:raise ValueError('Executable does not match pinned profile: '+k)
        impl=[Path(__file__)]+[Path(__file__).with_name(n) for n in ['candidate_trials.py','hydrogen_riding_trial.py','water_h_trial.py','reflection_omit_trial.py','reflection_audit.py','donor_audit.py','structure_diagnostics.py','compare_diagnostic_trials.py','refinement_controls.py','geometry_audit.py','population_stability.py','restraint_strength.py']]
        job={'schema':1,'recipe':request['recipe'],'baseline':str(base.resolve()),'output':str((out/'trials').resolve()),'software':software,'software_sha256':hashes,'trials':trials,'baseline_sha256':{p.name:digest(p) for p in base.iterdir()},'implementation_sha256':{str(p):digest(p) for p in impl},'source_hashes':audit['source_sha256'],'source_directory':str(Path(directory).resolve()),'source_stem':stem,'source_notes':RECIPES[request['recipe']]['source']}
        job['stop_on_control_failure']=True
        newjson(out/'plan.json',job);result={'status':'prepared','plan':str(out/'plan.json'),'alternatives':len(trials)-1,'preview':str(previews),'model_adopted':False,'source_unchanged':True}
    except Exception as exc:
        newjson(out/'preparation.json',{'status':'failed','error':str(exc),'model_adopted':False});raise
    newjson(out/'preparation.json',result);return result

def run(path):
    from compare_diagnostic_trials import compare
    job=json.loads(Path(path).read_text('utf-8'))
    if job.get('schema')!=1 or job.get('recipe') not in RECIPES:raise ValueError('Not a repair-plan job')
    for name,h in job['baseline_sha256'].items():
        if Path(name).name!=name or digest(Path(job['baseline'])/name)!=h:raise ValueError('Prepared baseline changed')
    for p,h in job['implementation_sha256'].items():
        if digest(p)!=h:raise ValueError('Implementation changed; prepare a new comparison')
    for k,p in job['software'].items():
        if digest(p)!=job['software_sha256'][k]:raise ValueError('Native executable changed')
    request=json.loads((Path(path).parent/'request.json').read_text('utf8'))
    if compile_trials(job['baseline'],request)!=job['trials']:raise ValueError('Trial definitions differ from validated request')
    results=run_plan(path);control=results[0]
    rows=[compare(control,r) for r in results[1:]] if control['status']=='completed' else []
    for row in rows:
        if row['status']!='completed':row['AB']=None;row['AB_counts']=None
    summary={'schema':1,'recipe':job['recipe'],'control_status':control['status'],'cases':rows,'trial_statuses':[{'name':r['name'],'status':r['status'],'result':str(Path(job['output'])/r['name']/'result.json')} for r in results], 'model_adopted':False,'official_validation':False,'AI_calls_in_script':0,'next':'Review chemistry, density, geometry, ADP and AB together. Then return to complete/resume-delivery for authorized IUCr PDF and both Word reports.'}
    if job['recipe']=='occupancy_stability':
        from population_stability import summarize
        summary['population_stability']=summarize(results,job['output'],request['parameters']['fvar_index'])
    if job['recipe']=='restraint_strength':
        from restraint_strength import observations
        summary['restraint_strength']={'instruction':request['parameters']['instruction'],'sigma_factors':[1]+request['parameters']['factors'],
            'basis':request['parameters']['basis'],'targets_and_cutoff_unchanged':True,'automatic_winner':None,
            'observations':observations(results,job['output'],request['parameters']['instruction']),
            'review':'Compare A/B, observed geometry, ADP, residual density, convergence and restraint tension; a small sigma is not experimental precision.'}
    if job['recipe'] in {'reflection_omit','resolution_window'}:
        import gemmi
        data=[]
        for result in results:
            entry={'name':result['name'],'status':result['status'],'metrics':result.get('metrics'),'completeness':None}
            cif=Path(job['output'])/result['name']/'paired/case.cif'
            if result['status']=='completed' and cif.is_file():
                b=gemmi.cif.read_file(str(cif)).sole_block();values={}
                for tag in ['_diffrn_measured_fraction_theta_full','_diffrn_measured_fraction_theta_max','_refine_ls_number_reflns']:
                    token=b.find_value(tag);v=gemmi.cif.as_number(token or '?')
                    values[tag]=v if math.isfinite(v) else None
                entry['completeness']=values
            data.append(entry)
        summary['reflection_selection_comparison']={'fixed_hkls':request['parameters'].get('hkls'),
            'd_min_A':request['parameters'].get('d_min_A'),'cases':data,
            'ranking_allowed':False,'raw_HKL_changed':False,'note':'Different fitted reflection sets: R reduction alone is not improvement. Native completeness describes measured data and may not decrease for OMIT; inspect used reflection counts and excluded set separately.'}
    newjson(Path(job['output'])/'comparison.json',summary);return summary

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('list')
    prep=sub.add_parser('prepare');prep.add_argument('--baseline',required=True);prep.add_argument('--stem',default='case');prep.add_argument('--request',required=True);prep.add_argument('--profile',required=True);prep.add_argument('--output',required=True)
    runp=sub.add_parser('run');runp.add_argument('--plan',required=True)
    resume=sub.add_parser('resume');resume.add_argument('--plan',required=True);resume.add_argument('--output',required=True);resume.add_argument('--retry-failed',action='store_true')
    args=p.parse_args()
    try:
        if args.action=='list':value=RECIPES
        elif args.action=='prepare':value=prepare(args.baseline,args.stem,json.loads(Path(args.request).read_text('utf-8-sig')),json.loads(Path(args.profile).read_text('utf-8-sig')),args.output)
        elif args.action=='resume':
            from trial_checkpoint import prepare_resume
            prepared=prepare_resume(args.plan,args.output,args.retry_failed);value=run(prepared['plan'])
        else:value=run(args.plan)
        print(json.dumps(value,ensure_ascii=False));return 0
    except Exception as exc:print(json.dumps({'status':'failed','error':str(exc),'model_adopted':False},ensure_ascii=False));return 2

if __name__=='__main__':raise SystemExit(main())
