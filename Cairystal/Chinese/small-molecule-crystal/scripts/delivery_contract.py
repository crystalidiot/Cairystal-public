"""Check concrete deliverables; CIF existence alone never means full delivery."""
from pathlib import Path
import argparse,json,zipfile
from crystal_runtime import sha,write_json,utc_now,check_stem

def audit(root,stem='model'):
 root=Path(root);check_stem(stem);folder=root/'delivery'
 names=[f'{stem}.{ext}' for ext in ['res','hkl','cif','lst','fcf']]+['IUCr_checkCIF.pdf','晶体学报表_中文.docx','Crystallographic_Report_EN.docx']
 missing=[n for n in names if not (folder/n).is_file() or not (folder/n).stat().st_size];issues=[];official=None
 if not missing:
  try:
   from iucr_validation import validate_saved
   r,parsed=validate_saved(root/'official',sha(folder/f'{stem}.cif'));official=parsed['counts']
   if sha(folder/'IUCr_checkCIF.pdf')!=sha(root/'official/IUCr_checkCIF.pdf'):raise ValueError('Delivered official PDF differs')
   if sha(folder/f'{stem}.cif')!=sha(root/'frozen'/f'{stem}.cif'):raise ValueError('Delivered CIF differs from frozen candidate')
   for ext in ['res','hkl','lst','fcf']:
    if sha(folder/f'{stem}.{ext}')!=sha(root/'frozen'/f'{stem}.{ext}'):raise ValueError('Delivered native file differs from frozen candidate: '+ext)
   for n in names:
    if n.endswith('.docx'):
     with zipfile.ZipFile(folder/n) as z:
      if z.testzip() or not z.read('word/document.xml').strip():raise ValueError('Invalid Word document: '+n)
   build=json.loads((root/'qa/report_build.json').read_text('utf-8'))
   if build.get('same_numeric_tables') is not True:raise ValueError('Bilingual numerical agreement not recorded')
   if build.get('cif_sha256')!=sha(folder/f'{stem}.cif'):raise ValueError('Word build belongs to a different final CIF')
   outputs=build.get('outputs',{})
   for lang,name in [('zh','晶体学报表_中文.docx'),('en','Crystallographic_Report_EN.docx')]:
    if outputs.get(lang,{}).get('sha256')!=sha(folder/name):raise ValueError('Word document changed or belongs to another build: '+lang)
   if not outputs['zh'].get('data_sha256') or outputs['zh']['data_sha256']!=outputs['en'].get('data_sha256'):raise ValueError('Bilingual table data hashes differ or are absent')
   from squeeze_bundle import companion_fab
   if companion_fab(folder/f'{stem}.res') is not None:
    names.append(f'{stem}.fab')
    if sha(folder/f'{stem}.fab')!=sha(root/'frozen'/f'{stem}.fab'):raise ValueError('Delivered FAB differs from frozen candidate')
  except Exception as e:issues.append(str(e))
 return {'schema':1,'checked_at':utc_now(),'status':'artifacts_complete' if not missing and not issues else 'incomplete','missing_artifacts':missing,'verification_issues':issues,'official_counts':official,'artifacts':{n:str(folder/n) for n in names if (folder/n).is_file()},'scientific_acceptance':'not_established_by_file_completion','scope':'Exact-CIF official report, paired deliverable presence and both Word files; scientific and layout review remain separate.'}

def require(root,stem='model'):
 r=audit(root,stem);write_json(Path(root)/'completion.json',r)
 if r['status']!='artifacts_complete':raise ValueError('Delivery incomplete: '+str(r['missing_artifacts']+r['verification_issues']))
 return r

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);p.add_argument('--stem',default='model');a=p.parse_args();r=audit(a.run,a.stem);print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(0 if r['status']=='artifacts_complete' else 2)
