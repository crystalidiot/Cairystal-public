"""Launch/reopen the local console without a persistent terminal window."""
import argparse,hashlib,json,os,subprocess,sys,time,urllib.request,webbrowser
from pathlib import Path
from urllib.parse import urlparse

def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def healthy(info,workspace,script):
 try:
  u=urlparse(info['url'])
  if u.scheme!='http' or u.hostname!='127.0.0.1' or u.path!='/':return False
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  with opener.open(info['url']+'health',timeout=1) as r:h=json.load(r)
  return h.get('service')=='cairystal-console' and h.get('pid')==info['pid'] and h.get('workspace_hash')==hashlib.sha256(str(workspace).casefold().encode()).hexdigest() and h.get('code_hash')==hashlib.sha256(script.read_bytes()).hexdigest() and str(h.get('skill_root','')).casefold()==str(script.resolve().parent.parent).casefold()
 except (ValueError,OSError,KeyError):return False

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True);p.add_argument('--profile',required=True);p.add_argument('--no-browser',action='store_true');p.add_argument('--register',action='append',default=[])
 a=p.parse_args();workspace=Path(a.workspace).resolve();workspace.mkdir(parents=True,exist_ok=True)
 script=Path(__file__).with_name('crystal_console.py');ready=workspace/'server.json'
 if ready.is_file():
  info=read(ready)
  if healthy(info,workspace,script):
   if not a.no_browser:webbrowser.open(info['url'])
   print(json.dumps({'status':'reopened',**info},ensure_ascii=False));return 0
 cfg=read(a.profile);argv=[cfg['python'],'-B',str(script),'--workspace',str(workspace),'--profile',str(Path(a.profile).resolve()),'--port','0']
 ready=workspace/('server_start_'+str(time.time_ns())+'.json');argv+=['--ready-file',str(ready)]
 for folder in a.register:argv+=['--register',folder]
 env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
 with (workspace/'server.log').open('a',encoding='utf-8') as log:
  proc=subprocess.Popen(argv,stdout=log,stderr=log,cwd=workspace,env=env,creationflags=0x08000000 if os.name=='nt' else 0,shell=False)
 for _ in range(100):
  if ready.is_file():
   info=read(ready)
   if healthy(info,workspace,script):
    temp=workspace/'server.json.tmp';temp.write_text(json.dumps(info,ensure_ascii=False,indent=2),'utf-8');temp.replace(workspace/'server.json')
    if not a.no_browser:webbrowser.open(info['url'])
    print(json.dumps({'status':'started',**info},ensure_ascii=False));return 0
  if proc.poll() is not None:break
  time.sleep(.1)
 raise RuntimeError('控制台未能启动；请查看 '+str(workspace/'server.log'))

if __name__=='__main__':raise SystemExit(main())
