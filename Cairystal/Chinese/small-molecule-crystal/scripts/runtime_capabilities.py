"""Report executable Python capabilities without importing models or contacting services."""
import argparse,hashlib,importlib,json,sys
from pathlib import Path
FEATURES={
 'core_refinement':['gemmi'],
 'bilingual_reports':['gemmi','docx','pypdf','PIL'],
 'automatic_report_qa':['pdfplumber','PIL'],
 'local_fourier_diagnostics':['gemmi','numpy'],
}
def inspect(importer=importlib.import_module):
 modules={}
 for name in sorted({n for values in FEATURES.values() for n in values}):
  try:
   m=importer(name);modules[name]={'available':True,'version':getattr(m,'__version__',None)}
  except (ImportError,OSError,RuntimeError) as e:modules[name]={'available':False,'error':str(e)}
 return {'python':sys.executable,'modules':modules,'features':{k:{'ready':all(modules[m]['available'] for m in v),'missing':[m for m in v if not modules[m]['available']]} for k,v in FEATURES.items()},'scope':'Import checks only; no native crystallographic execution, model download or network request.'}
def require(feature):
 report=inspect();missing=report['features'][feature]['missing']
 if missing:raise RuntimeError('Missing dependencies for '+feature+': '+', '.join(missing)+'. Configure this runtime before starting the operation.')
 return report

def environment_report(profile=None, output_root=None):
 """Read the selected machine/profile only; do not launch native programs."""
 from native_resources import decision,disk_info
 report=inspect();report['native_resources']=decision();report['configured_tools']={}
 for name,spec in (profile or {}).get('tools',{}).items():
  item={'path':spec.get('path'),'ready':False,'execution_verified':False}
  try:
   if not item['path']:raise ValueError('No executable path configured')
   path=Path(item['path']);item['exists']=path.is_file()
   if not item['exists']:raise FileNotFoundError('Configured executable not found on this computer')
   digest=hashlib.sha256()
   with path.open('rb') as stream:
    for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
   item['sha256']=digest.hexdigest();expected=spec.get('sha256')
   item['hash_matches_profile']=item['sha256'].lower()==str(expected).lower() if expected else None
   item['ready']=item['hash_matches_profile'] is not False
   if item['hash_matches_profile'] is False:item['error']='Executable differs from pinned profile; verify this installation and generate a new local profile.'
  except (OSError,ValueError) as exc:item['error']=str(exc)
  report['configured_tools'][name]=item
 if output_root:report['disk']=disk_info(output_root)
 report.update(network_used=False,system_settings_modified=False,
               scope='Local hardware, imports and configured executable file/hash checks only; no native execution or specimen upload. Readiness is not a licence or scientific validation.')
 return report

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile');p.add_argument('--output-root');p.add_argument('--output');a=p.parse_args();profile=None
 if a.profile:
  from pipeline_intake import bootstrap
  profile=json.loads(Path(a.profile).read_text('utf-8-sig'));bootstrap(profile)
 report=environment_report(profile,a.output_root)
 if a.output:
  with Path(a.output).open('x',encoding='utf8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
 print(json.dumps(report,ensure_ascii=False,indent=2))
