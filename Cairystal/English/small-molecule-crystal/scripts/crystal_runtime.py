"""Shared, conservative file/runner utilities. No scientific model edits."""
from pathlib import Path
import hashlib, json, os, re, shutil, subprocess, time, math
from datetime import datetime, timezone

REFLECTION_TAGS = ['_refln_index_h', '_refln_index_k', '_refln_index_l',
    '_refln_F_squared_calc', '_refln_F_squared_meas', '_refln_F_squared_sigma', '_refln_observed_status']

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def write_json(path, value):
    path = Path(path); temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def utc_now(): return datetime.now(timezone.utc).isoformat()
def flags(): return 0x08000000 if os.name == 'nt' else 0

def regular(path):
    path = Path(path).absolute()
    if not path.is_file() or path.is_symlink(): raise ValueError('Expected ordinary file: ' + str(path))
    return path

def new_directory(path):
    path = Path(path).absolute()
    if path.exists(): raise ValueError('Output already exists; choose a new run directory: ' + str(path))
    if any(p.is_symlink() for p in path.parents): raise ValueError('Symlinked output parent unsupported')
    path.mkdir(parents=True); return path

def check_stem(stem):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', stem):
        raise ValueError('Use a simple ASCII basename without path separators')
    return stem

def records(text):
    """Active SHELX logical records from CELL through HKLF, without comments/Q peaks."""
    result=[]; pending=''; active=False
    for raw in text.splitlines():
        # Native RES header text is indented and is not a control record.
        line=raw.split('!',1)[0].strip()
        if not line: continue
        line=(pending+' '+line).strip(); pending=''
        if line.endswith('='): pending=line[:-1]; continue
        f=line.split(); key=f[0].upper()
        if key=='CELL': active=True
        if not active or key=='REM': continue
        if key=='END': break
        result.append(f)
        if key=='HKLF': break
    if pending: raise ValueError('Unfinished SHELX continuation')
    if not result or result[-1][0].upper()!='HKLF': raise ValueError('CELL/HKLF active block missing')
    return result

def canonical(text):
    from decimal import Decimal, InvalidOperation
    out=[]
    for line in records(text):
        row=[]
        for token in line:
            try: row.append(str(Decimal(token).normalize()))
            except InvalidOperation: row.append(token.upper())
        out.append(row)
    return out

def check_instructions(text):
    lines=records(text); names=[r[0].upper() for r in lines]
    if 'SFAC' not in names or 'UNIT' not in names or names.index('SFAC')>names.index('UNIT'):
        raise ValueError('SFAC must precede UNIT')
    if next(r[1] for r in lines if r[0].upper()=='HKLF')!='4':
        raise ValueError('Routine delivery supports HKLF 4; HKLF 5 overlap records require a dedicated factor-pairing route, not ordinary reflection counting')
    if any(r[0].startswith(('+','@')) for r in lines): raise ValueError('External include files require an explicit specialist job')
    return lines

def cif_tolerance(token):
    match=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+))(?:\(\d+\))?([Ee][+-]?\d+)?',token)
    if not match:raise ValueError('Non-numeric CIF value: '+token)
    central=match[1];places=len(central.split('.')[1]) if '.' in central else 0
    exponent=int(match[2][1:]) if match[2] else 0
    # Few-digit exact fractions are not permission to hide coordinate changes.
    return 0.5001*10**(exponent-places)+1e-8 if '(' in token or places>=2 else 1e-8

def number(token):
    import gemmi
    val=gemmi.cif.as_number(token or '?')
    if not math.isfinite(val):raise ValueError('Missing/non-finite required numeric field: '+str(token))
    return val

def symmetry_operations(block):
    import gemmi
    values=list(block.find_values('_space_group_symop_operation_xyz')) or list(block.find_values('_symmetry_equiv_pos_as_xyz'))
    if not values:raise ValueError('Explicit symmetry operations required for file pairing')
    operations=[]
    for value in values:
        op=gemmi.Op(gemmi.cif.as_string(value));op.wrap();operations.append(op.triplet())
    return sorted(operations)

def compare_cell(block,text):
    values=next(r[1:] for r in records(text) if r[0].upper()=='CELL')
    tags=['_diffrn_radiation_wavelength','_cell_length_a','_cell_length_b','_cell_length_c','_cell_angle_alpha','_cell_angle_beta','_cell_angle_gamma']
    if len(values)!=len(tags):raise ValueError('CELL wavelength and six cell parameters required')
    for tag,val in zip(tags,values):
        token=block.find_value(tag)
        if abs(number(token)-float(val))>cif_tolerance(token):raise ValueError('RES/CIF cell or wavelength mismatch: '+tag)

def compare_cell_tokens(left, right):
    """Serialization consistency only; uncertainties are NOT matching tolerances."""
    checks={}
    for tag in ['_cell_length_a','_cell_length_b','_cell_length_c','_cell_angle_alpha','_cell_angle_beta','_cell_angle_gamma']:
        a=left.find_value(tag);b=right.find_value(tag)
        delta=abs(number(a)-number(b))
        tolerance=max(cif_tolerance(a),cif_tolerance(b))
        if delta>tolerance:raise ValueError('CIF/FCF cell mismatch: '+tag)
        checks[tag]={'left':a,'right':b,'difference':delta,'rounding_tolerance':tolerance}
    return checks

def compare_atom_loop(block, occupancy, text):
    import gemmi
    if any(a['residue']!='0' for a in occupancy['atoms']):
        raise ValueError('RESI label mapping needs specialist audit; routine path declines it')
    model={a['label'].upper():a for a in occupancy['atoms']}
    rows=[list(r) for r in block.find(['_atom_site_label','_atom_site_type_symbol','_atom_site_fract_x','_atom_site_fract_y','_atom_site_fract_z','_atom_site_occupancy'])]
    if len(model)!=len(occupancy['atoms']) or {r[0].upper() for r in rows}!=set(model) or len(rows)!=len(model):
        raise ValueError('CIF/RES atom label sets differ or are ambiguous')
    for r in rows:
        a=model[r[0].upper()]
        if r[1].upper()!=a['element'].upper():raise ValueError('CIF/RES element mismatch '+r[0])
        for token,x in zip(r[2:5],a['xyz']):
            if abs(number(token)-x)>cif_tolerance(token):raise ValueError('CIF/RES coordinate mismatch '+r[0])
        # Use printed central-value precision, never the parenthesized uncertainty.
        # SHELXL may export 0.598(3) for a RES free variable of 0.59832.
        if abs(number(r[5])-a['inferred_cif_occupancy'])>cif_tolerance(r[5])+a['sof_serialization_rounding_bound']:
            raise ValueError('CIF/RES occupancy mismatch '+r[0])
    atom_records={r[0].upper():r for r in records(text) if r[0].upper() in model}
    ani=[list(r) for r in block.find(['_atom_site_aniso_label','_atom_site_aniso_U_11','_atom_site_aniso_U_22','_atom_site_aniso_U_33','_atom_site_aniso_U_23','_atom_site_aniso_U_13','_atom_site_aniso_U_12'])]
    expected={k for k,r in atom_records.items() if len(r)>=12}
    if {r[0].upper() for r in ani}!=expected:raise ValueError('CIF/RES anisotropic parameterization differs')
    for row in ani:
        vals=[float(x) for x in atom_records[row[0].upper()][6:12]]
        if any(abs(x)>=1 for x in vals):raise ValueError('Encoded/free-variable anisotropic tensor needs specialist decoding')
        for token,x in zip(row[1:],vals):
            if abs(number(token)-x)>cif_tolerance(token):raise ValueError('CIF/RES anisotropic tensor mismatch '+row[0])
    cell=gemmi.UnitCell(*map(float,next(r[2:] for r in records(text) if r[0].upper()=='CELL')))
    orth=cell.orth.mat.tolist();recip=cell.reciprocal();lengths=[recip.a,recip.b,recip.c]
    tensors={r[0].upper():r for r in ani};uvalues={};ubounds={};parent_u=None;parent_bound=0
    for label,r in atom_records.items():
        vals=list(map(float,r[6:]));u=vals[0];bound=cif_tolerance(r[6])
        if label in tensors:
            u11,u22,u33,u23,u13,u12=vals[:6];matrix=[[u11,u12,u13],[u12,u22,u23],[u13,u23,u33]]
            u=sum(orth[i][j]*orth[i][k]*lengths[j]*lengths[k]*matrix[j][k] for i in range(3) for j in range(3) for k in range(3))/3
            coefficients=[sum(orth[i][j]*orth[i][k]*lengths[j]*lengths[k] for i in range(3))/3*(1 if j==k else 2) for j,k in [(0,0),(1,1),(2,2),(1,2),(0,2),(0,1)]]
            bound=sum(abs(coefficient)*cif_tolerance(token) for coefficient,token in zip(coefficients,r[6:12]))
        elif u<0:
            if model[label]['element'].upper() not in {'H','D'} or parent_u is None:raise ValueError('Unsupported encoded isotropic U')
            bound=abs(u)*parent_bound
            u=-u*parent_u
        elif u>=1:raise ValueError('Encoded/free-variable isotropic U requires specialist decoding')
        uvalues[label]=u;ubounds[label]=bound
        if model[label]['element'].upper() not in {'H','D'}:parent_u=u;parent_bound=bound
    urows=[list(r) for r in block.find(['_atom_site_label','_atom_site_U_iso_or_equiv','_atom_site_adp_type'])]
    if len(urows)!=len(model) or {r[0].upper() for r in urows}!=set(model):
        raise ValueError('CIF Ueq/Uiso and ADP-type rows missing or ambiguous')
    for r in urows:
        label=r[0].upper();expected_type='Uani' if label in tensors else 'Uiso'
        if r[2]!=expected_type or abs(number(r[1])-uvalues[label])>cif_tolerance(r[1])+ubounds[label]+1e-8:
            raise ValueError('CIF/RES Ueq/Uiso or ADP type mismatch '+r[0])

def read_hkl(text):
    """Fixed-column three-index HKLF4 rows, preserving batch/scaling columns."""
    from inspect_case import reflection_after_blank
    rows=[]
    blank_after_rows=False
    for raw in text.splitlines():
        if not raw.strip():
            if rows:blank_after_rows=True
            continue
        if blank_after_rows:
            if reflection_after_blank(raw):
                raise ValueError('Reflection after blank HKL terminator; review the input extent')
            break
        try:
            h=(int(raw[:4]),int(raw[4:8]),int(raw[8:12]))
            if h==(0,0,0): break
            intensity=float(raw[12:20]); sigma=float(raw[20:28])
            tail=raw[28:].split(); batch=int(tail[0]) if tail else 1
            if len(tail)>1: raise ValueError('Additional reflection columns unsupported')
            if sigma<=0 or not math.isfinite(sigma) or not math.isfinite(intensity): raise ValueError('Invalid intensity/uncertainty')
        except ValueError as exc: raise ValueError('Unsupported HKL row: '+raw[:100]) from exc
        rows.append((*h,intensity,sigma,batch))
    if not rows: raise ValueError('No reflection rows')
    return rows

def run_command(command, cwd, log, timeout=180):
    from native_process import hidden_kwargs
    from native_resources import prepare
    command,resources,resource_decision=prepare(command)
    start=time.perf_counter()
    with Path(log).open('w',encoding='utf-8') as stream:
        p=subprocess.Popen([str(x) for x in command],cwd=cwd,stdout=stream,stderr=subprocess.STDOUT,**hidden_kwargs())
        state='finished'
        try: rc=p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill(); rc=p.wait(); state='timeout'
    return {'command':[str(x) for x in command], 'elapsed_s':round(time.perf_counter()-start,3),
        'returncode':rc,'process_state':state,'log':str(log),'native_resources':resources,
        'resource_decision':resource_decision}

def paired_bundle(directory, stem):
    """Fail closed on model/data mismatch; no geometry, SFAC, ADP or reflection edits."""
    import gemmi
    from refinement_gate import assess
    from audit_occupancy import audit
    stem=check_stem(stem); directory=Path(directory)
    files={ext:regular(directory/f'{stem}.{ext}') for ext in ['ins','res','hkl','cif','fcf','lst']}
    before={ext:sha(p) for ext,p in files.items()}
    text=files['res'].read_text(encoding='latin1'); lines=check_instructions(text)
    from twin_delivery import classify,check_batch_columns
    twin_route=classify(lines)
    if not twin_route['supported_for_pairing']:
        raise ValueError(twin_route['message_zh']+' ['+twin_route['reason']+']')
    if any(r[0].upper()=='ABIN' for r in lines):
        files['fab']=regular(directory/f'{stem}.fab');before['fab']=sha(files['fab'])
    gate=assess(directory,stem)
    if not gate['execution_complete']: raise ValueError('SHELXL execution incomplete: '+str(gate['failures']))
    doc=gemmi.cif.read_file(str(files['cif'])); fdoc=gemmi.cif.read_file(str(files['fcf']))
    if len(doc)!=1 or len(fdoc)!=1: raise ValueError('Exactly one CIF and FCF datablock required')
    b=doc.sole_block(); fb=fdoc.sole_block()
    from squeeze_bundle import verify as verify_solvent_mask
    solvent_mask=verify_solvent_mask(directory,stem,b,text)
    compare_cell(b,text)
    embedded=b.find_value('_shelx_res_file')
    if not embedded or canonical(gemmi.cif.as_string(embedded))!=canonical(text):
        raise ValueError('CIF embedded RES does not match delivered RES controls/atoms/ADPs')
    embedded_hkl=b.find_value('_shelx_hkl_file')
    measured_text=files['hkl'].read_text(encoding='latin1')
    measured_rows=read_hkl(measured_text)
    check_batch_columns(twin_route,measured_rows)
    embedded_text=gemmi.cif.as_string(embedded_hkl) if embedded_hkl else ''
    # Identical texts have identical validated rows. Other serializations
    # still require a full numeric comparison (including uncertainties and batches).
    if not embedded_text or (embedded_text.strip('\r\n')!=measured_text.strip('\r\n')
                             and read_hkl(embedded_text)!=measured_rows):
        raise ValueError('CIF embedded HKL does not match delivered measured HKL')
    cell_pairing=compare_cell_tokens(b,fb)
    refl=[list(r) for r in fb.find(REFLECTION_TAGS)]
    if not refl: raise ValueError('LIST 4 FCF reflection loop missing/unsupported')
    if symmetry_operations(b)!=symmetry_operations(fb):raise ValueError('CIF/FCF symmetry operations differ')
    for r in refl:
        for x in r[:3]:int(x)
        if number(r[3])<0 or number(r[5])<=0:raise ValueError('Invalid calculated intensity or reflection uncertainty')
        number(r[4])
    if str(fb.find_value('_shelx_refln_list_code'))!='4': raise ValueError('FCF is not LIST 4')
    n=int(b.find_value('_refine_ls_number_reflns') or '0')
    if n!=len(refl) or gate['metrics'].get('unique')!=n: raise ValueError('CIF/FCF/LST reflection counts differ')
    keys=[tuple(r[:3]) for r in refl]
    if len(set(keys))!=len(keys): raise ValueError('Duplicate FCF hkl rows')
    present=[list(r) for r in b.find(REFLECTION_TAGS)]
    if present and present!=refl: raise ValueError('CIF embedded structure factors differ from supplied FCF')
    pairs={'_refine_ls_R_factor_gt':'R1_observed','_refine_ls_R_factor_all':'R1_all','_refine_ls_wR_factor_ref':'wR2','_refine_ls_goodness_of_fit_ref':'GooF'}
    for tag,key in pairs.items():
        if abs(number(b.find_value(tag))-gate['metrics'][key])>0.0011:
            raise ValueError('CIF versus final LST metric mismatch: '+tag)
    occupancy=audit(files['res'],gemmi)
    sg=gemmi.find_spacegroup_by_name(occupancy.get('space_group') or '')
    if not sg or sorted(op.triplet() for op in sg.operations())!=symmetry_operations(b):
        raise ValueError('RES/CIF symmetry differs or requires a specialist nonstandard-setting audit')
    if occupancy.get('unit_discrepancies') or occupancy.get('overlapping_orbit_groups'):
        raise ValueError('UNIT/orbit accounting requires specialist review')
    compare_atom_loop(b,occupancy,text)
    if {ext:sha(p) for ext,p in files.items()}!=before: raise ValueError('Input changed during audit')
    from routine_consistency import audit_files
    routine_checks=audit_files(files['cif'],files['res'])
    if {ext:sha(p) for ext,p in files.items()}!=before: raise ValueError('Input changed during consistency audit')
    return {'cell_pairing':cell_pairing,'twin_handling':twin_route,'solvent_mask':solvent_mask,'routine_checks':routine_checks,'files':{k:str(v) for k,v in files.items()},'source_sha256':before,'gate':gate,
        'occupancy':occupancy,'structure_factor_rows':len(refl),'has_embedded_structure_factors':bool(present),
        'scope':'File pairing and execution/occupancy checks; scientific acceptance requires review.'}

def freeze_bundle(audit, destination, stem):
    import gemmi
    destination=Path(destination); destination.mkdir()
    for ext,p in audit['files'].items(): shutil.copy2(p,destination/f'{stem}.{ext}')
    if not audit['has_embedded_structure_factors']:
        doc=gemmi.cif.read_file(str(destination/f'{stem}.cif')); b=doc.sole_block()
        fb=gemmi.cif.read_file(str(destination/f'{stem}.fcf')).sole_block(); loop=b.init_loop('',REFLECTION_TAGS)
        for r in fb.find(REFLECTION_TAGS): loop.add_row(list(r))
        b.set_pair('_shelx_refln_list_code','4');b.set_pair('_shelx_F_squared_multiplier','1')
        doc.write_file(str(destination/f'{stem}.cif'))
    return {p.name:sha(p) for p in destination.iterdir() if p.is_file()}

def local_validation(executable, frozen, destination, stem, timeout=120, allow_embedded=False, completion_mode=None):
    from parse_platon_alerts import parse
    from native_process import hidden_kwargs,visible_window_count
    from cif_format_check import require as require_cif_format
    require_cif_format(Path(frozen)/f'{stem}.cif')
    destination=Path(destination);destination.mkdir()
    from platon_execution import rules_context,native_versions,validation_ready,embedded_reflections,completion_fingerprint
    from native_resources import policy
    completion_mode=completion_mode or policy()['platon_completion']
    if completion_mode not in {'strict_fast','conservative'}:raise ValueError('Invalid PLATON completion mode')
    poll_seconds=.1 if completion_mode=='strict_fast' else .25
    input_exts=['cif','fcf'];reflection_source='paired_FCF'
    if not (Path(frozen)/f'{stem}.fcf').is_file() and allow_embedded:
        reflection_source=embedded_reflections(Path(frozen)/f'{stem}.cif');input_exts=['cif']
    input_hashes={ext:sha(regular(Path(frozen)/f'{stem}.{ext}')) for ext in input_exts}
    for ext in input_exts:shutil.copy2(Path(frozen)/f'{stem}.{ext}',destination/f'{stem}.{ext}')
    environment=rules_context(executable)
    command=[str(regular(executable)),'-u',f'{stem}.cif'];start=time.perf_counter()
    status='running'; old=None;stable=0;visible_counts=[];previous_signature=None;stable_since=None;completion_proof=None;old_since=None
    with (destination/'process.log').open('w') as out:
        p=subprocess.Popen(command,cwd=destination,stdout=out,stderr=subprocess.STDOUT,**hidden_kwargs())
        while time.perf_counter()-start<timeout:
            time.sleep(poll_seconds)
            try:count=visible_window_count(p.pid)
            except (OSError,AttributeError):count=None
            if count is not None:visible_counts.append(count)
            outputs=[destination/f'{stem}.chk',destination/f'{stem}.ckf']
            log=(destination/'platon.out').read_text(errors='replace') if (destination/'platon.out').exists() else ''
            if validation_ready(destination,stem):
                now=time.perf_counter();sizes=tuple(x.stat().st_size for x in outputs)
                if sizes!=old:old_since=now
                old=sizes
                signature=completion_fingerprint(destination,stem) if completion_mode=='strict_fast' else None
                if signature!=previous_signature or stable_since is None:stable_since=now
                previous_signature=signature
                fast_ready=bool(signature and now-stable_since>=.4)
                conservative_ready=bool(not signature and old_since is not None and now-old_since>=1.5)
                if fast_ready or conservative_ready:
                    completion_proof={'method':'native_notices_PS_EOF_and_content_hashes' if fast_ready else 'conservative_report_size_settling','stable_seconds':round(now-(stable_since if fast_ready else old_since),4),'artifact_sha256':signature}
                    status='reports_complete'
                    if p.poll() is None:p.terminate();p.wait(timeout=10);status='reports_complete_process_terminated'
                    break
            else:previous_signature=None;stable_since=None;old=None;old_since=None
            if p.poll() is not None:status='exited';break
        if p.poll() is None:p.kill();p.wait();status='timeout'
    parsed=parse((destination/f'{stem}.chk').read_text(encoding='latin1')) if (destination/f'{stem}.chk').exists() else None
    result={'command':command,'executable_sha256':sha(executable),'elapsed_s':round(time.perf_counter()-start,3),
        'returncode':p.returncode,'state':status,'alerts':parsed,'official':False,'rules_context':environment,'reflection_source':reflection_source,'native_versions':native_versions((destination/f'{stem}.chk').read_text('latin1') if (destination/f'{stem}.chk').exists() else '')}
    result['completion_policy']={'requested':completion_mode,'poll_seconds':poll_seconds,'proof':completion_proof,'validation_checks_skipped':False}
    result['window_startup']={'hidden_requested':os.name=='nt','max_observed_visible_windows':max(visible_counts) if visible_counts else None,'scope':f'Own process only, sampled every {round(poll_seconds*1000)} ms; mandatory dialogs or very brief/child-process windows may remain.'}
    result['validation_complete']=False
    result['validated_counts']=None
    result['parse_scope']='Raw partial output is not a completed validation; use validated_counts.'
    result['input_sha256']=input_hashes
    write_json(destination/'local_validation.json',result)
    try:
        if status not in {'reports_complete','reports_complete_process_terminated','exited'} or not parsed or not parsed['report_footer_present'] or parsed['warnings']:
            raise ValueError('Local validation incomplete or alert parsing inconsistent; see '+str(destination))
        if not (destination/f'{stem}.ckf').exists():raise ValueError('Local FCF validation missing')
        final_log=(destination/'platon.out').read_text(errors='replace') if (destination/'platon.out').exists() else ''
        if 'CheckCIF' not in final_log or 'CheckFCF' not in final_log or (destination/f'{stem}.ckf').stat().st_size<=100:
            raise ValueError('Local CIF/FCF completion markers absent')
        if any(sha(Path(frozen)/f'{stem}.{ext}')!=h for ext,h in input_hashes.items()):raise ValueError('Local validation input changed during execution')
        if completion_proof and completion_proof['artifact_sha256'] and any(sha(destination/name)!=h for name,h in completion_proof['artifact_sha256'].items()):raise ValueError('PLATON completion artifacts changed after settling; preserve output for review')
        if rules_context(executable)!=environment:raise ValueError('PLATON rules configuration changed during execution')
    except (ValueError,OSError) as exc:
        result['failure_reason']=str(exc)
        result['partial_parse']=result['alerts'];result['alerts']=None
        write_json(destination/'local_validation.json',result)
        raise
    result['validation_complete']=True
    result['validated_counts']=parsed['counts']
    result['input_sha256']=input_hashes
    result['artifact_sha256']={name:sha(destination/name) for name in [*[f'{stem}.{ext}' for ext in input_exts],f'{stem}.chk',f'{stem}.ckf','platon.out','process.log']}
    result['cache_hit']=False
    write_json(destination/'local_validation.json',result)
    return result
