"""Explicit-source experimental metadata ledger and reproducible CIF synchronization.

Input sources must already be authorized and paired with the experiment. No traversal,
reference atom import, guessed observations, refinement or upload is performed.
"""
import argparse
import json
import math
from pathlib import Path
import re

import gemmi
from crystal_runtime import sha, regular, utc_now, canonical
from inspect_experiment_metadata import inspect_metadata
from prepare_validation_metadata import TAGS, snapshot, missing, available, equivalent
from temperature_consistency import AMBIENT, CELL, audit_temperature

CELL_TAGS=['_cell_length_a','_cell_length_b','_cell_length_c','_cell_angle_alpha','_cell_angle_beta','_cell_angle_gamma']


def numeric(token):
    value=gemmi.cif.as_number(token)
    if not math.isfinite(value): raise ValueError('Expected finite numeric metadata')
    return value


def validate(fields):
    errors=[]
    for tag,token in fields.items():
        if not available(token):continue
        try:
            if tag in {AMBIENT,CELL,'_diffrn_radiation_wavelength'} or tag.startswith('_exptl_crystal_size_'):
                if numeric(token)<=0:raise ValueError('Value must be positive')
            if tag=='_cell_measurement_reflns_used':
                v=numeric(token)
                if v<=0 or int(v)!=v:raise ValueError('Reflection count must be a positive integer')
            if tag in {'_cell_measurement_theta_min','_cell_measurement_theta_max'} and not 0<=numeric(token)<=90:
                raise ValueError('Theta must be between 0 and 90 degrees; no implicit 2theta conversion')
            if tag in {'_exptl_absorpt_correction_T_min','_exptl_absorpt_correction_T_max'} and not 0<numeric(token)<=1:
                raise ValueError('Transmission must be in (0,1]')
        except ValueError as exc:errors.append({'tag':tag,'token':token,'reason':str(exc)})
    for tags in [['_cell_measurement_theta_min','_cell_measurement_theta_max'],
                 ['_exptl_crystal_size_min','_exptl_crystal_size_mid','_exptl_crystal_size_max'],
                 ['_exptl_absorpt_correction_T_min','_exptl_absorpt_correction_T_max']]:
        if all(available(fields.get(t)) for t in tags):
            try:
                values=[numeric(fields[t]) for t in tags]
                if values!=sorted(values):errors.append({'tags':tags,'reason':'Ordered values reversed'})
            except ValueError:pass
    return errors


def p4p_fields(path,temperature_scope,temperature_unit=None,temperature_basis=None):
    from p4p_metadata import read_p4p
    meta=read_p4p(path.read_text(encoding='latin1'),require_core=False,
                  temperature_unit=temperature_unit,temperature_basis=temperature_basis)
    if temperature_scope not in {'diffraction','cell','both','unconfirmed'}:raise ValueError('Specify P4P temperature scope')
    out={};locators={}
    if 'wavelength' in meta:
        out['_diffrn_radiation_wavelength']=str(meta['wavelength']);locators['_diffrn_radiation_wavelength']='SOURCE[1]'
    for tag,key in [('_cell_measurement_reflns_used','measurement_reflections'),('_cell_measurement_theta_min','measurement_theta_min'),('_cell_measurement_theta_max','measurement_theta_max')]:
        if meta.get(key) is not None:out[tag]=str(meta[key]);locators[tag]='SAINGL[0:3]'
    if 'temperature_K' in meta:
        for tag,scope in [(AMBIENT,'diffraction'),(CELL,'cell')]:
            if temperature_scope in {scope,'both'}:
                out[tag]=format(meta['temperature_K'],'.6f').rstrip('0').rstrip('.')
                locators[tag]='CSIZE[4]; '+str(meta['temperature_evidence'])
    return out,locators,meta.get('cell')


def sadabs_fields(source,hkl):
    """Parse the actual HKL-output section, never the approximate cell/wavelength."""
    text=source.read_text('latin1');lines=text.splitlines()
    versions=re.findall(r'(?m)^\s*(SADABS-[0-9]+/[0-9]+)\b',text)
    outputs=list(re.finditer(r'(?im)^\s*(\d+)\s+Corrected reflections written to file\s+(\S+)\s*$',text))
    if len(set(versions))!=1 or len(outputs)!=1:raise ValueError('Ambiguous SADABS version/output section')
    out=outputs[0]
    if Path(out[2]).name.casefold()!=hkl.name.casefold():raise ValueError('SADABS output filename differs from supplied HKL')
    count=0
    for line in hkl.read_text('latin1').splitlines():
        if not line.strip():continue
        try:indices=[int(line[i:i+4]) for i in (0,4,8)]
        except ValueError:raise ValueError('Unsupported HKL record for SADABS pairing')
        if indices==[0,0,0]:break
        count+=1
    if count!=int(out[1]):raise ValueError('SADABS output reflection count differs from supplied HKL')
    tail=text[out.end():];t=re.search(r'Estimated minimum and maximum transmission:\s*([.\d]+)\s+([.\d]+)',tail)
    if not t:raise ValueError('SADABS output transmission estimates absent')
    extra=re.search(r'Additional spherical absorption correction applied with mu\*r\s*=\s*([.\d]+)',tail)
    details=versions[0]+'; multi-scan scaling and absorption correction. Transmission estimates copied from the output log; their ratio is more reliable than absolute values.'
    if extra:details+=' Additional spherical correction mu*r='+extra[1]+'. Applicability to the provisional composition/specimen remains unverified.'
    values={'_exptl_absorpt_correction_type':'multi-scan','_exptl_absorpt_correction_T_min':t[1],'_exptl_absorpt_correction_T_max':t[2], '_exptl_absorpt_process_details':gemmi.cif.quote(details)}
    loc={k:'SADABS output section line '+str(text[:out.start()].count('\n')+1)+'; filename and reflection count matched' for k in values}
    return values,loc


def collect(config,output):
    config=regular(config);cfg=json.loads(config.read_text('utf-8-sig'));hkl=regular(cfg['hkl'])
    out=Path(output).absolute()
    if out.exists():raise ValueError('Use a new metadata ledger directory')
    hashes={str(config):sha(config),str(hkl):sha(hkl)};observations={};sources=[];unsupported=[]
    for entry in cfg['sources']:
        if entry.get('same_experiment_confirmed') is not True or not entry.get('basis'):
            raise ValueError('Source needs documented same-experiment pairing')
        if entry.get('hkl_sha256')!=sha(hkl):raise ValueError('Source pairing identifies different HKL')
        source=regular(entry['path']);digest=sha(source);hashes[str(source)]=digest
        if entry.get('source_sha256')!=digest:raise ValueError('Source hash not frozen in configuration')
        cell=None;locators={};metadata_details=None;field_context={}
        if entry['kind']=='p4p':
            fields,locators,cell=p4p_fields(source,entry.get('temperature_scope','unconfirmed'),entry.get('temperature_unit'),entry.get('temperature_unit_basis'))
            from p4p_metadata import read_p4p
            metadata_details=read_p4p(source.read_text('latin1'),False,entry.get('temperature_unit'),entry.get('temperature_unit_basis'))
        elif entry['kind']=='sadabs_log':
            fields,locators=sadabs_fields(source,hkl)
        elif entry['kind'] in {'cif_metadata','phil_metadata'}:
            record=inspect_metadata(source,entry.get('encoding','utf-8-sig'))
            blocks=[b for b in record['blocks'] if entry.get('block') is None or b['block']==entry['block']]
            if len(blocks)!=1:raise ValueError('Select one explicit metadata block')
            b=blocks[0];fields={k:v['token'] for k,v in b['fields'].items()}
            locators={k:'data_'+b['block']+'/'+k+'; line '+str(b['fields'][k].get('source_line')) for k in fields}
            field_context={k:{key:value for key,value in b['fields'][k].items()
                              if key in {'source_line','source_tag','provenance_tier','unit','measurement_origin_verified','device_specificity','model_inferred'}} for k in fields}
            unsupported.extend({'source':str(source),'tag':t,'reason':'looped_metadata_not_copied'} for t in b['looped_metadata_requires_review'])
        elif entry['kind']=='anonymous_sidecar':
            from experimental_sidecar import read_case,validate_fields
            for field in ['manifest','input_json']:
                linked=regular(entry[field]);hashes[str(linked)]=sha(linked)
            record=read_case(source,entry['manifest'],entry['case_id'],entry['input_json'],hkl)
            fields=validate_fields(record['fields'])
            locators={k:'cases/'+entry['case_id']+'/fields/'+k for k in fields}
        elif entry['kind']=='confirmed_json':
            record=json.loads(source.read_text('utf-8-sig'))
            if record.get('confirmed') is not True or not (record.get('basis') or record.get('provenance')):raise ValueError('Unconfirmed/default observation cannot enter measured ledger')
            if not set(record['cif_fields'])<=set(TAGS):raise ValueError('Non-experimental field in confirmed record')
            fields={k:gemmi.cif.quote(str(v)) for k,v in record['cif_fields'].items()}
            locators={k:'cif_fields/'+k for k in fields}
        else:raise ValueError('Unsupported source format; no guessed parser')
        errors=validate(fields)
        if errors:raise ValueError('Invalid source values: '+json.dumps(errors))
        sources.append({'path':str(source),'sha256':digest,'kind':entry['kind'],'basis':entry['basis'],'cell_for_consistency':cell,'p4p_details':metadata_details})
        for tag,token in fields.items():
            observations.setdefault(tag,[]).append({'token':token,'source':str(source),'source_sha256':digest,'locator':locators[tag],**field_context.get(tag,{})})
    resolved={};conflicts={}
    for tag,entries in observations.items():
        known=[e for e in entries if available(e['token'])]
        if any(e['token']=='.' for e in entries) and known:conflicts[tag]=entries;continue
        if known:
            if all(equivalent(known[0]['token'],v['token']) for v in known):resolved[tag]=known[0]['token']
            else:conflicts[tag]=entries
        elif any(e['token']=='.' for e in entries):resolved[tag]='.'
    errors=validate(resolved)
    if any(sha(p)!=h for p,h in hashes.items()):raise ValueError('Source changed during collection')
    result={'schema':1,'created_at':utc_now(),'hkl':str(hkl),'hkl_sha256':sha(hkl),'input_hashes':hashes,
            'sources':sources,'observations':observations,'resolved':resolved,'conflicts':conflicts,
            'unsupported':unsupported,'validation_errors':errors,'missing':[t for t in TAGS if not available(resolved.get(t))],
            'status':'needs_review' if conflicts or errors or unsupported else 'collected',
            'scientific_acceptance':False,'ai_calls':0}
    out.mkdir(parents=True)
    (out/'metadata_ledger.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result


def check_basis_audit(path, native, expected, actual):
    """Explicit signed-axis permutation only; idealization remains a review finding."""
    import math
    p=regular(path);a=json.loads(p.read_text('utf-8-sig'));matrix=a.get('matrix',[])
    if len(matrix)!=3 or any(len(row)!=3 for row in matrix):raise ValueError('3x3 basis matrix required')
    if any(v not in (-1,0,1) for row in matrix for v in row):raise ValueError('Only signed axis permutations supported')
    if any(sum(abs(v) for v in row)!=1 for row in matrix) or any(sum(abs(matrix[i][j]) for i in range(3))!=1 for j in range(3)):raise ValueError('Basis matrix is not a permutation')
    if not a.get('reason'):raise ValueError('Explicit basis rationale required')
    for ev in a.get('evidence',[]):
        if sha(regular(ev['path']))!=ev['sha256']:raise ValueError('Basis evidence changed')
    if not a.get('evidence'):raise ValueError('Frozen current-run basis evidence required')
    from crystal_runtime import records
    h=[r for r in records(native) if r[0].upper()=='HKLF']
    if len(h)!=1 or len(h[0])!=12 or int(h[0][1])!=4 or float(h[0][2])!=1 or [float(x) for x in h[0][3:]]!=[v for row in matrix for v in row]:raise ValueError('Explicit native HKLF matrix differs from basis audit')
    cell=gemmi.UnitCell(*expected);old=[]
    for i in range(3):
        f=[0,0,0];f[i]=1;v=cell.orthogonalize(gemmi.Fractional(*f));old.append([v.x,v.y,v.z])
    vec=[[sum(matrix[i][j]*old[j][k] for j in range(3)) for k in range(3)] for i in range(3)]
    length=[math.sqrt(sum(v*v for v in row)) for row in vec]
    angle=lambda i,j:math.degrees(math.acos(max(-1,min(1,sum(vec[i][k]*vec[j][k] for k in range(3))/(length[i]*length[j])))))
    transformed=length+[angle(1,2),angle(0,2),angle(0,1)]
    bound=float(a.get('reviewed_angle_idealization_max_deg',0))
    if not 0<=bound<=.1:raise ValueError('Angle idealization allowance outside supported review range')
    if any(abs(x-y)>max(.002,abs(y)*1e-4) for x,y in zip(actual[:3],transformed[:3])) or any(abs(x-y)>max(.002,bound) for x,y in zip(actual[3:],transformed[3:])):raise ValueError('Candidate cell does not match audited basis/idealization')
    return {'audit':str(p),'sha256':sha(p),'matrix':matrix,'transformed_measured_cell':transformed,'candidate_cell':actual,'angle_changes_deg':[x-y for x,y in zip(actual[3:],transformed[3:])],'scientific_status':'candidate_symmetry_requires_review'}


def synchronize(ledger,cif,res,hkl,output,basis_audit=None):
    ledger,cif,res,hkl=map(regular,(ledger,cif,res,hkl));out=Path(output).absolute()
    if out.exists():raise ValueError('Use a new synchronized-output directory')
    m=json.loads(ledger.read_text('utf-8-sig'))
    if sha(hkl)!=m['hkl_sha256']:raise ValueError('Ledger and refinement HKL do not match')
    if m.get('conflicts') or m.get('validation_errors'):raise ValueError('Resolve source conflicts before synchronization')
    hashes={str(p):sha(p) for p in (ledger,cif,res,hkl)}
    for p,h in m['input_hashes'].items():
        if sha(p)!=h:raise ValueError('Frozen metadata source changed')
    doc=gemmi.cif.read_file(str(cif))
    if len(doc)!=1:raise ValueError('Exactly one candidate datablock required')
    b=doc.sole_block();native=res.read_text('latin1');before=snapshot(doc)
    embedded=b.find_value('_shelx_res_file')
    if embedded and canonical(gemmi.cif.as_string(embedded))!=canonical(native):
        raise ValueError('CIF embedded RES differs from explicitly paired native model')
    basis_checks=[]
    for source in m['sources']:
        expected=source.get('cell_for_consistency')
        if expected:
            actual=[numeric(b.find_value(t)) for t in CELL_TAGS]
            # Same setting required. Solver basis changes need separately documented mapping.
            if any(abs(a-v)>max(.002,abs(v)*1e-4) for a,v in zip(actual,expected)):
                if not basis_audit:raise ValueError('Source/candidate cell setting differs; document basis transformation separately')
                basis_checks.append(check_basis_audit(basis_audit,native,expected,actual))
    filled=[];conflicts=[]
    from temperature_consistency import native_info
    if any(s.get('p4p_details') is not None for s in m['sources']) and AMBIENT not in m['resolved'] and native_info(native)['kelvin'] is None:
        old=b.find_value(AMBIENT)
        if available(old):
            b.set_pair(AMBIENT,'?');filled.append({'tag':AMBIENT,'before':old,'after':'?','mode':'unsubstantiated_native_default_removed'})
    for tag,token in m['resolved'].items():
        old=b.find_value(tag)
        if old=='.':
            if available(token):conflicts.append({'tag':tag,'current':old,'source':token})
            continue
        if missing(old) and available(token):
            b.set_pair(tag,token);filled.append({'tag':tag,'before':old,'after':token})
        elif available(old) and available(token) and not equivalent(old,token):
            if tag==AMBIENT and abs(numeric(old)-numeric(token))<1e-6 and '(' in old:
                b.set_pair(tag,token);filled.append({'tag':tag,'before':old,'after':token,'mode':'temperature_uncertainty_from_verified_source'});continue
            # A native literature citation and a paired SADABS output note can be
            # complementary. Retain both; never generalize this to scalar conflicts.
            kinds={s['path']:s['kind'] for s in m['sources']}
            if tag=='_exptl_absorpt_process_details' and all(kinds.get(e['source'])=='sadabs_log' for e in m['observations'][tag]):
                combined=append_sadabs_details(old,token)
                if combined is not None:
                    b.set_pair(tag,combined);filled.append({'tag':tag,'before':old,'after':combined,'mode':'append_verified_same_version_process_note'});continue
            # Numeric rounding is recorded, never a license to erase a different measurement.
            try: agrees=abs(numeric(old)-numeric(token))<1e-6
            except ValueError:agrees=False
            if not agrees:conflicts.append({'tag':tag,'current':old,'source':token})
    expected={k:dict(v) for k,v in before.items()}
    for f in filled:expected[b.name][f['tag'].lower()]=('scalar',f['after'].replace('\r\n','\n'))
    if snapshot(doc)!=expected:raise ValueError('Unexpected model/reflection modification')
    temperature=audit_temperature(b,native)
    if any(sha(p)!=h for p,h in hashes.items()):raise ValueError('Input changed during synchronization')
    out.mkdir(parents=True);new=out/'model.cif';doc.write_file(str(new))
    result={'created_at':utc_now(),'input_hashes':hashes,'output':str(new),'output_sha256':sha(new),
            'filled':filled,'conflicts_retained':conflicts,'temperature':temperature,'inputs_unchanged':True,
            'all_other_CIF_values_unchanged':True,'scientific_acceptance':False,'ai_calls':0,
            'basis_checks':basis_checks,
            'status':'needs_review' if conflicts or temperature['issues'] or basis_checks else 'synchronized',
            'native_refinement_required':any(i['code'] in {'TEMP_MISSING','TEMP_CIF_MISMATCH','TEMP_AFTER_ATOMS','TEMP_CONTROL_INVALID'} for i in temperature['issues'])}
    (out/'metadata_sync.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result


def append_sadabs_details(old,new):
    a,b=gemmi.cif.as_string(old).strip(),gemmi.cif.as_string(new).strip()
    va=set(re.findall(r'SADABS[-\s]+(\d+/\d+)',a,re.I));vb=set(re.findall(r'SADABS[-\s]+(\d+/\d+)',b,re.I))
    if len(va)!=1 or va!=vb:return None
    ma=re.findall(r'mu\s*\*\s*r\s*=\s*([.\d]+)',a,re.I);mb=re.findall(r'mu\s*\*\s*r\s*=\s*([.\d]+)',b,re.I)
    if ma and (not mb or {float(x) for x in ma}!={float(x) for x in mb}):return None
    if b in a:return old
    return gemmi.cif.quote(a+'\n'+b)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    c=sub.add_parser('collect');c.add_argument('--config',required=True);c.add_argument('--output',required=True)
    s=sub.add_parser('sync')
    for k in ('ledger','cif','res','hkl','output'):s.add_argument('--'+k,required=True)
    s.add_argument('--basis-audit')
    a=p.parse_args()
    try:r=collect(a.config,a.output) if a.cmd=='collect' else synchronize(a.ledger,a.cif,a.res,a.hkl,a.output,a.basis_audit)
    except (ValueError,OSError,RuntimeError) as exc:
        print(json.dumps({'status':'blocked','reason':str(exc)},ensure_ascii=False));return 2
    print(json.dumps({k:r[k] for k in ['status','output','filled','conflicts_retained','native_refinement_required','missing'] if k in r},ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
