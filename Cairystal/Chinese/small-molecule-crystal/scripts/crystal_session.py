"""Reusable, headless raw-data sessions. Chemical decisions are explicit job plans.

No model cache, implicit reference reads, automatic OMIT or automatic acceptance.
"""
import argparse, contextlib, io, json, math, re, shutil, sys, time, html
from pathlib import Path
from types import SimpleNamespace
import gemmi
from crystal_runtime import records, sha, write_json, utc_now, new_directory, regular, paired_bundle
from audit_occupancy import audit
from run_crystal_stage import run as native_run

def inside(root, path):
    p=Path(path).resolve(strict=True)
    if not p.is_relative_to(root.resolve()):raise ValueError('Model/plan must be inside this new job: '+str(p))
    return p

def load(root):return json.loads((root/'session.json').read_text(encoding='utf-8'))
def save(root,m):write_json(root/'session.json',m)

def timed(root,name,fn):
    start=utc_now();clock=time.perf_counter()
    try:value=fn();status='completed';return value
    except Exception as exc:status='failed';raise
    finally:
        m=load(root);m['events'].append({'name':name,'started_at':start,'finished_at':utc_now(),'seconds':round(time.perf_counter()-clock,4),'status':status});save(root,m)

def parse_p4p(text):
    from p4p_metadata import read_p4p
    return read_p4p(text)


def laue_seed(meta, hkl=None):
    """Use declared Bravais/Laue information, not the metric alone or final SG."""
    if 'bravais' not in meta:
        from measured_seed import infer
        return infer(meta, hkl)
    name=meta['bravais'].lower();cell=gemmi.UnitCell(*meta['cell'])
    if 'monoclinic(b-unique)' in name:
        lattice=7 if name.split()[-1]=='c' else 1 if name.split()[-1]=='p' else None
        if lattice is None:raise ValueError('Unsupported monoclinic lattice; supply reviewed INS')
        symbol='C 1 2/m 1' if lattice==7 else 'P 1 2/m 1'
    elif name == 'orthorhombic p':
        declared = set(meta.get('declared_symmetry', []))
        if declared and declared != {'mmm'}:
            raise ValueError('Conflicting or unsupported orthorhombic SYMM declaration; review the indexing')
        if not cell.is_compatible_with_spacegroup(gemmi.SpaceGroup('P m m m')):
            raise ValueError('Bravais/Laue/cell conflict')
        if hkl is None:
            raise ValueError('Orthorhombic P seed requires measured HKL rotation mates')
        from ortho_laue import screen, LaueReviewRequired
        meta['laue_screen'] = screen(hkl)
        if not meta['laue_screen']['passed']:
            raise LaueReviewRequired(meta['laue_screen'])
        lattice, symbol = 1, 'P m m m'
    elif 'triclinic' in name and name.split()[-1]=='p':
        lattice,symbol=1,'P -1'
    elif name in {'hexagonal','hexagonal p'}:
        declared=set(meta.get('declared_symmetry',[]))
        if declared=={'6/mmm'}:symbol='P 6/m m m'
        elif declared=={'6/m'}:symbol='P 6/m'
        else:raise ValueError('Hexagonal metric alone is insufficient; original SYMM must explicitly declare 6/m or 6/mmm, or supply reviewed INS')
        lattice=1
    else:raise ValueError('This raw P4P initializer requires reviewed Laue input for '+meta['bravais'])
    group=gemmi.SpaceGroup(symbol)
    if not cell.is_compatible_with_spacegroup(group):raise ValueError('Bravais/Laue/cell conflict')
    # Positive LATT supplies inversion; centering is encoded by LATT. Supply every
    # remaining proper primitive operation, not just generators; omit identity.
    symmetry=[op.triplet().upper() for op in group.operations().sym_ops if op.det_rot()>0 and op.triplet()!='x,y,z']
    basis='Declared Bravais/Laue seed '+symbol+'; complete operations from Gemmi '+gemmi.__version__+'. Final space group remains a solver hypothesis.'
    if name == 'orthorhombic p':
        basis += ' All three twofold rotations supported by measured intensity pairs; see metadata.laue_screen.'
    return lattice,symmetry,basis


def logical_text(rows):
    from shelx_input_preflight import render_records
    return render_records(rows)


def sfac(text):return next(r[1:] for r in records(text) if r[0].upper()=='SFAC')

def normalize_solver_records(text):
    rows=records(text)
    if any(r[0].upper()=='FVAR' for r in rows):return text
    symbols=sfac(text);out=[];inserted=False
    control={'CELL','ZERR','SYMM','SFAC','UNIT','LATT','L.S.','PLAN','FMAP','LIST','BOND','TEMP','WGHT','HKLF'}
    for row in rows:
        atom=False
        if len(row)>=7 and row[0].upper() not in control:
            try:atom=1<=int(row[1])<=len(symbols);list(map(float,row[2:7]))
            except ValueError:atom=False
        if atom:
            if not inserted:out+=['WGHT 0.1','FVAR 1'];inserted=True
            # SHELXT's eighth column is a peak height, not a second U tensor term.
            if len(row)==8:row=row[:7]
        out.append(row)
    if not inserted:raise ValueError('Solver file contains no recognized sites')
    return 'TITL mechanical normalization of fresh solver output\n'+logical_text(out)

def edit_candidate(root,source,plan):
    original=source.read_text(encoding='latin1');text=normalize_solver_records(original);rows=records(text);symbols=sfac(text)
    audit_source=source
    if text!=original:
        audit_source=root/'prepared/_normalized_solver.res';audit_source.write_text(text,encoding='ascii')
    before=audit(audit_source,gemmi);labels={x['label'].upper() for x in before['atoms']}
    changes={k.upper():v for k,v in plan.get('element_changes',{}).items()}
    if not set(changes)<=labels:raise ValueError('Unknown element-change labels')
    mapping={k.upper():v for k,v in plan.get('rename',{}).items()}
    if not set(mapping)<=labels or len(set(mapping.values()))!=len(mapping):raise ValueError('Invalid atom rename')
    finalnames=[mapping.get(label,label).upper() for label in labels]
    if len(set(finalnames))!=len(finalnames):raise ValueError('Atom rename collision with an existing label')
    metadata=load(root)['metadata']
    inserts=['L.S. '+str(plan.get('cycles',12))]+(['ANIS'] if plan.get('anisotropic',False) else [])+plan.get('hydrogens',[])
    if 'temperature_K' in metadata:inserts.insert(0,'TEMP '+format(metadata['temperature_K']-273.15,'.6f').rstrip('0').rstrip('.'))
    if plan.get('suggested_weights'):
        suggestions=re.findall(r'^WGHT\s+(.+)$',text.split('\nEND',1)[-1],re.M)
        if not suggestions:raise ValueError('Suggested weighting record absent')
        weight=suggestions[-1]
    else:weight=plan.get('weight')
    result=[];inserted=False
    for row in rows:
        key=row[0].upper()
        if key in {'L.S.','CGLS','TREF','LIST','ACTA','FMAP','PLAN'}:continue
        if key=='ANIS' and plan.get('anisotropic',False):continue
        if key=='TEMP' and 'temperature_K' in metadata:continue
        if key in {'HTAB','EQIV'} and (plan.get('discover_hbonds') or any(str(x).split()[0].upper() in {'HTAB','EQIV'} for x in plan.get('post',[]) if str(x).split())):continue
        if key in labels:
            if not inserted:result+=inserts;inserted=True
            if key in changes:
                names=[s.upper() for s in symbols]
                if changes[key].upper() not in names:raise ValueError('Element absent from explicit SFAC')
                row[1]=str(names.index(changes[key].upper())+1)
        if key=='WGHT' and weight:row=['WGHT',*str(weight).split()]
        if key=='ZERR' and plan.get('asu_formula_bookkeeping',False):row=['ZERR',str(before['general_multiplicity']),*map(str,metadata['cell_su'])]
        if key=='HKLF':result+=plan.get('post',[])+['LIST 4','ACTA','FMAP 2','PLAN 50']
        result.append([mapping.get(x.upper(),x) for x in row])
    if not inserted:raise ValueError('No atoms in candidate')
    # UNIT derived from actual SOF, FVAR and symmetry orbit accounting, not a guessed formula.
    temp=root/'prepared/_unit_audit.res';temp.write_text('TITL candidate\n'+logical_text(result),encoding='ascii')
    account=audit(temp,gemmi);composition={k.upper():v for k,v in account['modeled_unit_cell_composition'].items()}
    if plan.get('riding_h_counts'):
        from hydrogen_plan import predicted_unit_h
        if [s.upper() for s in symbols].count('H')!=1:
            raise ValueError('Riding H counts require a unique H position in SFAC')
        composition['H']=predicted_unit_h(plan['riding_h_counts'],plan['hydrogens'],account)
    for row in result:
        if isinstance(row,list) and row[0].upper()=='UNIT':row[1:]=[f'{composition.get(s.upper(),0):.6g}' for s in symbols]
    temp.unlink()
    return 'TITL raw-data independent candidate\n'+logical_text(result),account

def summarize(stage):
    b=gemmi.cif.read_file(str(stage/'model.cif')).sole_block();cell=gemmi.UnitCell(*[gemmi.cif.as_number(b.find_value(t)) for t in ['_cell_length_a','_cell_length_b','_cell_length_c','_cell_angle_alpha','_cell_angle_beta','_cell_angle_gamma']])
    tags=['_atom_site_label','_atom_site_type_symbol','_atom_site_fract_x','_atom_site_fract_y','_atom_site_fract_z','_atom_site_U_iso_or_equiv']
    atoms=[]
    for row in b.find(tags):
        r=list(row);atoms.append({'label':r[0],'element':r[1],'xyz':[gemmi.cif.as_number(v) for v in r[2:5]],'Ueq':gemmi.cif.as_number(r[5])})
    ops=[gemmi.Op(gemmi.cif.as_string(x)) for x in b.find_values('_space_group_symop_operation_xyz')]
    if not ops:
        ops=[gemmi.Op(gemmi.cif.as_string(x)) for x in b.find_values('_symmetry_equiv_pos_as_xyz')]
    if not ops:
        raise ValueError('Explicit CIF symmetry operations required for the neighbor review')
    origins=[gemmi.Fractional(*a['xyz']) for a in atoms]
    images=[[gemmi.Fractional(*op.apply_to_xyz(a['xyz'])) for op in ops] for a in atoms]
    for a,origin in zip(atoms,origins):
        neighbors=[]
        for other,positions in zip(atoms,images):
            if a['label']==other['label']:continue
            distance=min(cell.find_nearest_pbc_image(origin,position,0).dist() for position in positions)
            if distance<1.95:neighbors.append([other['label'],other['element'],round(distance,3)])
        a['neighbors']=sorted(neighbors,key=lambda n:n[2])
    for a in atoms:a.pop('xyz')
    result={'space_group':gemmi.cif.as_string(b.find_value('_space_group_name_H-M_alt')),'formula':gemmi.cif.as_string(b.find_value('_chemical_formula_sum')),'atoms':atoms,'difference_density':[b.find_value('_refine_diff_density_max'),b.find_value('_refine_diff_density_min')]}
    write_json(stage/'model_review.json',result);return result

def execute(root,name,text,program,reason,fab=None,timeout=600):
    from crystal_runtime import check_stem
    check_stem(name);m=load(root);prepared=root/'prepared'/f'{name}.ins';stage=root/'stages'/name
    if prepared.exists() or stage.exists():raise ValueError('Stage name already used; original prepared input and results are preserved')
    prepared.write_text(text,encoding='ascii')
    a=SimpleNamespace(executable=m['software'][program],ins=str(prepared),hkl=m['working_hkl'],fab=str(fab) if fab else None,output=str(stage),stem='model',reason=reason,timeout=timeout)
    def perform():
        with contextlib.redirect_stdout(io.StringIO()) as captured:rc=native_run(a)
        if rc:raise ValueError('Native run failed; retained '+str(stage/'attempt.json')+' '+captured.getvalue())
        record=json.loads((stage/'attempt.json').read_text(encoding='utf-8'))
        if program=='shelxl':record['review']=summarize(stage)
        return record
    return timed(root,name,perform)

def compact_candidates(payload):
    result=dict(payload);result['candidates']=[]
    for candidate in payload['candidates']:
        item={k:v for k,v in candidate.items() if k!='review'};review=candidate.get('review',{})
        item['review_summary']={k:v for k,v in review.items() if k!='atoms'}
        item['review_summary']['atom_sites']=len(review.get('atoms',[]))
        item['model_review']=str(Path(candidate['stage'])/'model_review.json');result['candidates'].append(item)
    return result

def emit_candidates(root,payload,detail,filename):
    write_json(root/filename,payload)
    result=payload if detail else compact_candidates(payload)
    print(json.dumps(dict(result,full_record=str(root/filename)),ensure_ascii=False))

def start(a):
    from pipeline_intake import normalize_elements,validate_specimen
    a.elements=normalize_elements(a.elements)
    submitted_specimen,_=validate_specimen(getattr(a,'specimen',None))
    root=new_directory(a.output);(root/'input').mkdir();(root/'prepared').mkdir();(root/'stages').mkdir()
    m={'schema':1,'started_at':utc_now(),'events':[],'software':{'shelxt':str(regular(a.shelxt)),'shelxl':str(regular(a.shelxl))},'inputs':{},'prior_models_read':False,'prior_conversation_exposure':a.prior_conversation_exposure,'skill_hashes':{p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}}
    for name in ['hkl','p4p','integration_log','absorption_log','specimen','solver_fallback']:
        path=getattr(a,name,None)
        if not path:continue
        source=regular(path)
        dest=root/'input'/source.name
        if dest.exists():
            dest=root/'input'/name/source.name
            dest.parent.mkdir()
        digest=sha(source)
        if getattr(a,'expected_hashes',{}).get(name,digest)!=digest:
            raise ValueError('Input changed since preflight: '+name)
        shutil.copy2(source,dest)
        if sha(dest)!=digest or sha(source)!=digest:
            raise ValueError('Input changed during snapshot: '+name)
        m['inputs'][name]={'source':str(source),'copy':str(dest),'sha256':digest}
    m['working_hkl']=m['inputs']['hkl']['copy'];m['elements']=a.elements
    save(root,m)  # Preserve input hashes even if metadata initialization fails.
    checked_specimen,_=validate_specimen(m['inputs'].get('specimen',{}).get('copy'))
    if checked_specimen!=submitted_specimen:
        raise ValueError('Specimen information changed between intake and snapshot')
    m['metadata']=parse_p4p(Path(m['inputs']['p4p']['copy']).read_text(encoding='latin1'))
    m['specimen']=checked_specimen
    from p4p_metadata import input_conflicts
    m['metadata_conflicts']=input_conflicts(m['metadata'],a.elements,checked_specimen)
    save(root,m)
    supplied_t=m['specimen'].get('cif_fields',{}).get('_diffrn_ambient_temperature')
    if supplied_t is not None:
        supplied_t=float(supplied_t)
        if 'temperature_K' in m['metadata'] and abs(supplied_t-m['metadata']['temperature_K'])>.51:raise ValueError('User/P4P temperature conflict; consolidate this new conflict with any other blocking questions')
        m['metadata']['temperature_K']=supplied_t
    # Reuse only an in-process intake result bound to both independently copied inputs.
    intake = getattr(a, 'checked_laue', None)
    if intake and all(intake[k] == m['inputs'][k]['sha256'] for k in ('p4p','hkl')) and intake['screen']['hkl_sha256'] == intake['hkl']:
        lattice,symmetry,basis = intake['seed']
        m['metadata']['laue_screen'] = intake['screen']
    else:
        try:
            lattice,symmetry,basis=laue_seed(m['metadata'], m['working_hkl'])
        finally:
            save(root,m)
    m['laue_basis']=basis;save(root,m)
    volume=gemmi.UnitCell(*m['metadata']['cell']).volume
    # Search bookkeeping only: approximate non-H volume, deliberately not exact stoichiometry.
    nonh=[e for e in a.elements if e.upper() not in {'H','D'}];weights={e:1/math.sqrt(gemmi.Element(e).atomic_number) for e in nonh};total=sum(weights.values())
    counts=[0 if e not in weights else max(1,round(volume/18*weights[e]/total)) for e in a.elements]
    meta=m['metadata'];rows=['CELL '+str(meta['wavelength'])+' '+' '.join(map(str,meta['cell'])),'ZERR 1 '+' '.join(map(str,meta['cell_su'])),'LATT '+str(lattice),*['SYMM '+s for s in symmetry],'SFAC '+' '.join(a.elements),'UNIT '+' '.join(map(str,counts)),'TREF','HKLF 4','END']
    m['search_unit']={'values':counts,'meaning':'Rough phasing search bookkeeping from volume/18 and element scattering weights; not molecular formula, Z or atom counts established from experiment.'};save(root,m)
    search_text='TITL raw-data search\n'+logical_text(rows)
    from solver_fallback import configuration
    cfg=json.loads(Path(m['inputs']['solver_fallback']['copy']).read_text('utf-8-sig')) if 'solver_fallback' in m['inputs'] else None
    cfg=configuration(search_text,cfg)
    primary_error=None;candidates=[];failed=[]
    try:result=execute(root,'00_solution',search_text,'shelxt',basis+' Explicit elements; no previous model read.',timeout=cfg['primary_timeout_seconds'])
    except Exception as exc:
        primary_error=str(exc);attempt=root/'stages/00_solution/attempt.json'
        result=json.loads(attempt.read_text('utf8')) if attempt.is_file() else {'error':primary_error}
    if result.get('success'):
        for index,filename in enumerate(result.get('candidate_outputs',[])[:4]):
            src=root/'stages/00_solution'/filename
            try:
                from solver_fallback import candidate
                screened=candidate(src,gemmi.UnitCell(*meta['cell']),a.elements,meta['wavelength'])
                if screened['status']!='candidate_requires_refinement':raise ValueError(screened['reason'])
                text,account=edit_candidate(root,src,{'cycles':12,'anisotropic':True,'asu_formula_bookkeeping':True})
                c=execute(root,f'01_baseline_{index}',text,'shelxl','Fresh solver candidate, provisional elements. Original HKL; first non-H anisotropic baseline.')
                stage=root/'stages'/f'01_baseline_{index}'
                from initial_model_review import save_review
                initial_review=save_review(stage,'model',m['elements'],stage/'initial_review.json')
                candidates.append({'stage':str(stage),'metrics':c['gate']['metrics'],'review':c['review'],'initial_review':initial_review})
            except Exception as exc:failed.append({'source':str(src),'error':str(exc)})
    payload={'job':str(root),'laue_basis':basis,'search_unit':m['search_unit'],'candidates':candidates,'primary_error':primary_error,'failed_candidates':failed}
    if candidates:
        current=load(root);current['solution_program']='SHELXT';save(root,current)
    else:
        from solver_fallback import run_fallback,fallback_reason
        decision=fallback_reason(result,0)
        if decision=='blocked_environment_or_input':
            payload['solver_handoff']={'status':'software_environment_failure','reason':primary_error or result.get('error'),'record':str(root/'stages/00_solution/attempt.json')}
        else:
            exe=getattr(a,'shelxd',None)
            if not exe:
                neighbour=Path(a.shelxt).with_name('shelxd.exe')
                exe=str(neighbour) if neighbour.is_file() else None
            fallback=timed(root,'SHELXD_fallback',lambda:run_fallback(search_text,m['working_hkl'],exe,root/'stages/02_shelxd_fallback',cfg))
            payload['solver_handoff']={'status':fallback['status'],'record':str(root/'stages/02_shelxd_fallback/fallback.json'),
                'unrefined_candidates':fallback['candidates'],'required_review':'SHELXD site types and SOF-like peak ranking fields need chemical/graph assignment before ordinary SHELXL refinement. No peak height is adopted as physical occupancy.'}
            current=load(root);current['solution_program']='SHELXD' if fallback['candidates'] else None;save(root,current)
    emit_candidates(root,payload,getattr(a,'detail',False),'start_summary.json')

def refine(a):
    root=Path(a.job).resolve();source=inside(root,a.source);plan_path=inside(root,a.plan);plan=json.loads(plan_path.read_text(encoding='utf-8'))
    if not plan.get('reason'):raise ValueError('Scientific decision reason required')
    from squeeze_bundle import companion_fab
    fab=companion_fab(source)
    variants=plan.get('variants',[None]);results=[]
    for variant in variants:
        current=dict(plan);current['element_changes']=dict(plan.get('element_changes',{}))
        if variant:current['element_changes'][plan['variant_site']]=variant
        name=a.name+('_'+variant if variant else '')
        text,account=edit_candidate(root,source,current)
        record=execute(root,name,text,'shelxl',plan['reason'],fab=fab)
        results.append({'stage':str(root/'stages'/name),'metrics':record['gate']['metrics'],'review':record['review']})
        if plan.get('discover_hbonds'):
            current_source=root/'stages'/name/'model.res'
            tail=current_source.read_text(encoding='latin1').split('\nEND',1)[-1]
            labels={x['label'].upper() for x in audit(current_source,gemmi)['atoms'] if x['element'].upper() in {'O','N'}}
            htab=[line.strip() for line in tail.splitlines() if line.startswith('HTAB ') and line.split()[1].upper() in labels]
            excluded={str(k).upper():v for k,v in plan.get('excluded_acceptors',{}).items()}
            omitted=[x for x in htab if x.split()[2].split('_')[0].upper() in excluded]
            htab=[x for x in htab if x not in omitted]
            if excluded:write_json(root/'stages'/name/'contact_rule_review.json',{'excluded_acceptors':excluded,'omitted_annotations':omitted,'retained_annotations':htab,'scope':'Only graph-supported contact annotations; no coordinate or reflection edits.'})
            identifiers={s for line in htab for s in re.findall(r'\$\d+',line)}
            equiv=[line.strip() for line in tail.splitlines() if line.startswith('EQIV ') and line.split()[1] in identifiers]
            if htab:
                compiled,_=edit_candidate(root,current_source,{'post':equiv+htab,'cycles':6})
                complete=execute(root,name+'_hbonds',compiled,'shelxl','Explicit donor geometry from this-run HTAB discovery; no new structural hypothesis.',fab=companion_fab(current_source))
                results.append({'stage':str(root/'stages'/(name+'_hbonds')),'metrics':complete['gate']['metrics'],'review':complete['review']})
    emit_candidates(root,{'candidates':results},getattr(a,'detail',False),a.name+'_summary.json')

def prepare(a):
    from prepare_validation_metadata import prepare as merge,snapshot
    root=Path(a.job).resolve();stage=inside(root,a.stage);m=load(root);out=new_directory(root/a.name)
    audit_pair=paired_bundle(stage,'model')
    for ext,path in audit_pair['files'].items():shutil.copy2(path,out/f'model.{ext}')
    meta=m['metadata'];doc=gemmi.cif.Document();b=doc.add_new_block('raw_experiment')
    tags=['_cell_length_a','_cell_length_b','_cell_length_c','_cell_angle_alpha','_cell_angle_beta','_cell_angle_gamma']
    fields=dict(zip(tags,meta['cell']));fields.update({'_diffrn_radiation_wavelength':meta['wavelength']})
    for tag,key in [('_cell_measurement_reflns_used','measurement_reflections'),('_cell_measurement_theta_min','measurement_theta_min'),('_cell_measurement_theta_max','measurement_theta_max')]:
        if meta.get(key) is not None:fields[tag]=meta[key]
    specimen=m['specimen']
    for k,v in specimen.get('cif_fields',{}).items():fields[k]=v
    if 'temperature_K' in meta:fields.update(_diffrn_ambient_temperature=meta['temperature_K'])
    if 'absorption_log' in m['inputs']:
        log=Path(m['inputs']['absorption_log']['copy']).read_text(encoding='latin1')
        match=re.search(r'Estimated minimum and maximum transmission:\s*([.\d]+)\s+([.\d]+)',log)
        if match:fields.update(_exptl_absorpt_correction_type='multi-scan',_exptl_absorpt_correction_T_min=match[1],_exptl_absorpt_correction_T_max=match[2])
        extra=re.search(r'Additional spherical absorption correction applied with mu\*r\s*=\s*([.\d]+)',log)
        if extra:fields['_exptl_absorpt_special_details']='Original absorption log: additional spherical correction mu*r='+extra[1]+'. Its applicability must be reviewed against composition and specimen size; original data retained.'
    for k,v in fields.items():b.set_pair(k,gemmi.cif.quote(str(v)))
    meta_path=root/'raw_experiment.cif';doc.write_file(str(meta_path));evidence=root/'metadata_pairing.json';write_json(evidence,{'source':'Explicit original files copied at session start','inputs':m['inputs'],'cell_measurement':'P4P SAINGL theta values, distinct from refinement reflection range','specimen':specimen})
    merged=root/(a.name+'_metadata.cif');merge(meta_path,out/'model.cif',merged,evidence);shutil.copy2(merged,out/'model.cif')
    doc=gemmi.cif.read_file(str(out/'model.cif'));b=doc.sole_block();before=snapshot(doc);annotations={}
    if 'temperature_K' in meta:annotations.update(_diffrn_ambient_temperature=str(meta['temperature_K']))
    elif not any(r[0].upper()=='TEMP' for r in records((out/'model.res').read_text('latin1'))):
        annotations['_diffrn_ambient_temperature']='?'
    annotations['_atom_sites_solution_primary']='dual' if m.get('solution_program') in {'SHELXT','SHELXD'} else '?'
    annotations['_computing_structure_solution']=(m.get('solution_program') or 'Unconfirmed solution program')+' (actual version recorded in session native logs)'
    annotations['_computing_structure_refinement']='SHELXL (actual version recorded in session native logs)'
    annotations['_computing_publication_material']='Gemmi and python-docx shared-CIF bilingual reports'
    if a.annotations:
        given=json.loads(inside(root,a.annotations).read_text(encoding='utf-8'))
        allowed={'_chemical_formula_moiety','_publ_section_exptl_refinement','_computing_cell_refinement','_computing_data_reduction','_computing_molecular_graphics','_computing_structure_solution','_computing_structure_refinement'}
        if not set(given)<=allowed:raise ValueError('Unsupported report annotation')
        annotations.update(given)
    audit_changes=[]
    for k,v in annotations.items():audit_changes.append({'tag':k,'before':b.find_value(k),'after':str(v)});b.set_pair(k,'?' if v=='?' else gemmi.cif.quote(str(v)))
    after=snapshot(doc)
    for name,entries in before.items():
        for tag,val in entries.items():
            if tag not in annotations and after[name].get(tag)!=val:raise ValueError('Unexpected protected CIF change')
    doc.write_file(str(out/'model.cif'));write_json(root/'report_annotations.json',audit_changes)
    from report_preflight import review_contacts
    contact_audit=review_contacts(out/'model.cif');write_json(root/'report_contact_preflight.json',contact_audit)
    paired=paired_bundle(out,'model');write_json(root/'selected_pairing.json',paired)
    m=load(root);m['selected']=str(out);m['model_prepared_at']=utc_now();save(root,m)
    print(json.dumps({'selected':str(out),'metrics':paired['gate']['metrics'],'contact_preflight':contact_audit},ensure_ascii=False))

def close(a):
    from datetime import datetime
    root=Path(a.job).resolve();m=load(root);delivery=inside(root,a.delivery)
    d=json.loads((delivery/'result.json').read_text(encoding='utf-8'))
    if d['status']!='delivery_complete_needs_scientific_review':raise ValueError('Actual visual review and delivery finalization required first')
    checks={k:sha(v['source'])==v['sha256'] and sha(v['copy'])==v['sha256'] for k,v in m['inputs'].items()}
    if not all(checks.values()):raise ValueError('Original input changed')
    checks_skill={k:sha(Path(__file__).parent/k)==v for k,v in m['skill_hashes'].items()}
    if not all(checks_skill.values()):raise ValueError('Skill changed during measured run')
    finished=utc_now();total=(datetime.fromisoformat(finished)-datetime.fromisoformat(m['started_at'])).total_seconds()
    attempts=[]
    for p in sorted((root/'stages').glob('*/attempt.json')):
        rec=json.loads(p.read_text(encoding='utf-8'));attempts.append({'stage':p.parent.name,'seconds':rec.get('elapsed_s'),'command':rec['command'],'metrics':rec.get('gate',{}).get('metrics'),'log':rec.get('log')})
    result={'status':d['status'],'started_at':m['started_at'],'finished_at':finished,'total_seconds':round(total,3),'native_seconds':round(sum(x['seconds'] or 0 for x in attempts),3),'events':m['events'],'attempts':attempts,'delivery_timings':d['timings_s'],'metrics':d['metrics'],'official':d['official'],'AB_alerts':d['AB_alerts'],'original_inputs_unchanged':checks,'skill_unchanged':checks_skill,'delivery':str(delivery/'delivery'),'zip':d['zip'],'prior_models_read':False,'prior_conversation_exposure':m['prior_conversation_exposure'],'comparison':{'previous_seconds':a.baseline_seconds,'reduction_fraction':1-total/a.baseline_seconds if a.baseline_seconds else None},'scope':'New phasing from original data; see recorded conversational exposure. No prior model read. Process completion and self-consistency, not reference-scored proof of chemical correctness.'}
    write_json(root/'result.json',result)
    rows=''.join(f'<tr><td>{html.escape(x["stage"])}</td><td>{x["seconds"]:.3f}</td><td>{html.escape(str(x["metrics"]))}</td></tr>' for x in attempts)
    times=''.join(f'<tr><td>{html.escape(k)}</td><td>{v:.3f}</td></tr>' for k,v in d['timings_s'].items())
    files=['model.res','model.hkl','model.cif','IUCr_checkCIF.pdf','晶体学报表_中文.docx','Crystallographic_Report_EN.docx']
    links=''.join(f'<li><a href="{(delivery/"delivery"/name).relative_to(root).as_posix()}">{name}</a></li>' for name in files)
    (root/'index.html').write_text(f'''<!doctype html><html lang="zh"><meta charset="utf-8"><title>新一轮解析计时</title><style>body{{font:16px/1.6 'Microsoft YaHei',sans-serif;max-width:1050px;margin:40px auto;color:#24334a;padding:20px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;border:1px solid #ddd}}th{{background:#eef1f5}}a{{color:#126ba1}}</style><h1>从原始数据重新解析：计时与结果</h1><p>新一轮开始：{m['started_at']}；完成：{finished}。本轮总耗时 <b>{total:.3f} 秒</b>。开发、测试脚本的时间在本轮开始之前，未计入。</p><p>IUCr 官网：{html.escape(str(d['official']['counts']))}。原生求解/精修累计 {result['native_seconds']:.3f} 秒。未读取旧模型；已有聊天信息，因此不属于完全未知样品盲测。</p><p><a href="{(delivery/'structure_and_reports.zip').relative_to(root).as_posix()}">下载完整文件包</a> · <a href="result.json">完整结果与计时</a> · <a href="session.json">输入、版本与事件</a></p><ul>{links}</ul><h2>原生运行</h2><table><tr><th>阶段</th><th>计算秒数</th><th>指标</th></tr>{rows}</table><h2>交付自动化</h2><table><tr><th>阶段</th><th>秒数</th></tr>{times}</table><p>以上为软件执行耗时，已经包含在总时间内。其余时间包含模型判断、工具交互和实际视觉复核，不将其冒充为精确的科研分析计时。完整 A/B、C/G 与局限请见官网 PDF 及中英文 Word。无 A/B 或低 R 不能证明数据处理和化学模型完全正确。</p></html>''',encoding='utf-8')
    print(json.dumps({'job':str(root),'total_seconds':result['total_seconds'],'native_seconds':result['native_seconds'],'official':d['official']['counts'],'comparison':result['comparison']},ensure_ascii=False))

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    s=sub.add_parser('start')
    for k in ['hkl','p4p','output','shelxt','shelxl']:s.add_argument('--'+k,required=True)
    s.add_argument('--elements',nargs='+',required=True)
    s.add_argument('--prior-conversation-exposure',action='store_true');s.add_argument('--detail',action='store_true',help='Include full atom/neighbor table in stdout; always saved on disk')
    for k in ['integration-log','absorption-log','specimen','solver-fallback','shelxd']:s.add_argument('--'+k)
    s=sub.add_parser('refine')
    for k in ['job','source','plan','name']:s.add_argument('--'+k,required=True)
    s.add_argument('--detail',action='store_true')
    s=sub.add_parser('prepare')
    for k in ['job','stage']:s.add_argument('--'+k,required=True)
    s.add_argument('--name',default='selected');s.add_argument('--annotations')
    s=sub.add_parser('close');s.add_argument('--job',required=True);s.add_argument('--delivery',required=True);s.add_argument('--baseline-seconds',type=float)
    a=p.parse_args();globals()[a.action](a)
if __name__=='__main__':main()
