"""Run local validation to completion; return actual reports and native rule versions."""
from pathlib import Path
import argparse,json,shutil,sys,time
from crystal_runtime import regular,new_directory,sha,write_json,local_validation
from pipeline_intake import unlinked,verify_profile

def run(a):
    source=regular(unlinked(a.cif));target=unlinked(a.output)
    if target==source.parent or source.parent in target.parents:raise ValueError('Use an independent output directory, outside the input folder')
    profile=json.loads(regular(unlinked(a.profile)).read_text('utf-8-sig'));tools=verify_profile(profile)
    root=new_directory(target);frozen=root/'input';frozen.mkdir();shutil.copy2(source,frozen/'model.cif')
    inputs={'cif':{'path':str(source),'sha256':sha(source)}}
    if a.fcf:
        fcf=regular(unlinked(a.fcf));shutil.copy2(fcf,frozen/'model.fcf');inputs['fcf']={'path':str(fcf),'sha256':sha(fcf)}
    write_json(root/'inputs.json',inputs);start=time.perf_counter()
    result={'status':'running','official':False,'scientific_acceptance':'not_established'}
    try:
        r=local_validation(tools['platon'],frozen,root/'validation','model',a.timeout,allow_embedded=True)
        result.update(status='local_validation_complete',counts=r['alerts']['counts'],versions=r.get('native_versions'),reports={ext:str(root/'validation'/f'model.{ext}') for ext in ['chk','ckf']},process_state=r['state'])
    except Exception as e:result.update(status='failed',error=str(e),logs=str(root/'validation'),reason='Inspect native logs. Empty files or absent external check.def alone do not establish missing rules.')
    result['inputs_unchanged']=all(sha(v['path'])==v['sha256'] for v in inputs.values())
    if not result['inputs_unchanged']:result.update(status='failed',error='Source changed during local validation')
    result['seconds']=round(time.perf_counter()-start,3);write_json(root/'result.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['cif','profile','output']:p.add_argument('--'+n,required=True)
    p.add_argument('--fcf');p.add_argument('--timeout',type=float,default=120);a=p.parse_args()
    r=run(a);print(json.dumps(r,ensure_ascii=False));raise SystemExit(r['status']!='local_validation_complete')
