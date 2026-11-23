"""Explicit same-job render reuse; unchanged DOCX contents and local renderer only.

Never searches historical jobs. Reuse preserves PDF/PNG bytes and reruns report QA.
Old manifests without this contract are deliberately ineligible.
"""
import hashlib,json,os,platform,shutil,time
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as E
from crystal_runtime import sha,write_json

VERSION=2

def file_signature(path):
    """Fast local font-change signal; cached PDF/PNG still require SHA256 checks.

    This is not a cryptographic attestation of the host OS or font installation.
    Full source/PDF layout QA is rerun after reuse.
    """
    s=Path(path).stat()
    return {'size':s.st_size,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns}

def package_fingerprint(path):
    """Ignore ZIP container timestamps, but retain every document part byte."""
    h=hashlib.sha256()
    with ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate DOCX archive members')
        for name in sorted(names):
            data=z.read(name)
            if name.endswith('.rels'):
                if any(e.get('TargetMode')=='External' for e in E.fromstring(data)):
                    raise ValueError('External relationship: render again')
            if name.startswith('word/') and name.endswith('.xml'):
                ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                root=E.fromstring(data)
                fields=[e.text or '' for e in root.iter(ns+'instrText')]
                fields.extend(e.get(ns+'instr','') for e in root.iter(ns+'fldSimple'))
                if any(f.strip().split()[0].upper() not in {'PAGE','NUMPAGES','SECTIONPAGES'} for f in fields if f.strip()):
                    raise ValueError('Dynamic/unknown Word field: render again')
            h.update(name.encode('utf-8')+b'\0'+hashlib.sha256(data).digest())
    return h.hexdigest()

def registry_values(hive,key):
    import winreg
    try:
        with winreg.OpenKey(hive,key) as h:
            return sorted((winreg.EnumValue(h,i) for i in range(winreg.QueryInfoKey(h)[1])),key=lambda x:x[0])
    except FileNotFoundError:return []

def environment(renderer,pdftoppm,soffice=None,powershell=None):
    """Conservatively support the observed Windows Word route; else fresh render."""
    if renderer!='word' or os.name!='nt':raise ValueError('Cache currently requires Windows Word')
    import winreg
    key=r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\WINWORD.EXE'
    word=None
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive,key,0,winreg.KEY_READ|view) as h:word=Path(winreg.QueryValueEx(h,'')[0].strip('"'))
                if word.is_file():break
            except FileNotFoundError:continue
        if word and word.is_file():break
    if not word or not word.is_file():raise ValueError('Cannot fingerprint Word executable')
    font_dirs=[Path(os.environ['WINDIR'])/'Fonts',Path(os.environ['LOCALAPPDATA'])/'Microsoft/Windows/Fonts']
    fonts={}
    for folder in font_dirs:
        if folder.exists():
            for p in sorted(folder.iterdir()):
                if p.is_file() and p.suffix.lower() in {'.ttf','.ttc','.otf','.fon','.fnt'}:fonts[str(p)]=file_signature(p)
    if not fonts:raise ValueError('No font fingerprint')
    normal=Path(os.environ['APPDATA'])/'Microsoft/Templates/Normal.dotm'
    registries={}
    for hive_name,hive in [('user',winreg.HKEY_CURRENT_USER),('machine',winreg.HKEY_LOCAL_MACHINE)]:
        for k in [r'Software\Microsoft\Windows NT\CurrentVersion\Fonts',r'Software\Microsoft\Office\16.0\Word\Options',r'Software\Microsoft\Windows NT\CurrentVersion\Windows']:
            if hive_name=='machine' and not k.endswith('Fonts'):continue
            values=registry_values(hive,k)
            if k.endswith('Fonts'):
                for _,value,_ in values:
                    if isinstance(value,str):
                        font=Path(os.path.expandvars(value))
                        if font.is_absolute() and font.is_file():fonts[str(font)]=file_signature(font)
            # A hash records printer/Word/font settings without exposing their values.
            registries[hive_name+'/'+k]=hashlib.sha256(repr(values).encode('utf-8')).hexdigest()
    return {'platform':platform.platform(),'renderer':renderer,'word':sha(word),
        'powershell':sha(powershell),'pdftoppm':sha(pdftoppm),'font_file_signatures':fonts,
        'normal_template':sha(normal) if normal.is_file() else None,'registry':registries,
        'implementation':{n:sha(Path(__file__).parent/n) for n in ('bilingual_report.py','report_render_cache.py')},'raster_dpi':110}

def contract(reports,renderer,pdftoppm,soffice=None,powershell=None):
    try:
        outputs=reports['outputs']
        if set(outputs)!={'zh','en'}:raise ValueError('Both document languages required')
        return {'schema':VERSION,'documents':{k:package_fingerprint(v['path']) for k,v in outputs.items()},
                'environment':environment(renderer,pdftoppm,soffice,powershell)},None
    except Exception as exc:return None,type(exc).__name__+': '+str(exc)

def bounded_artifact(path,root):
    p=Path(path).absolute();root=Path(root).absolute()
    if not p.is_relative_to(root) or p==root:raise ValueError('Cache artifact leaves its QA directory')
    for item in (p,*p.parents):
        if item==root.parent:break
        if item.is_symlink() or (hasattr(item,'is_junction') and item.is_junction()):raise ValueError('Linked cache artifact')
    if not p.is_file():raise ValueError('Missing cached artifact')
    return p

def restore(source,qa,reports,expected):
    """Validate everything before copying. Any miss falls back to native render."""
    started=time.perf_counter()
    if not source:return None,'not_requested'
    if not expected:return None,'environment_or_document_ineligible'
    try:
        source=Path(source).absolute();qa=Path(qa).absolute()
        manifest=bounded_artifact(source/'render_manifest.json',source)
        cached=json.loads(manifest.read_text('utf-8'))
        if cached.get('render_contract')!=expected:raise ValueError('Document or render environment changed')
        jobs=cached.get('jobs',[])
        if len(jobs)!=2 or {j['language'] for j in jobs}!={'zh','en'}:raise ValueError('Incomplete language pair')
        from pypdf import PdfReader
        planned=[]
        for job in jobs:
            pdf=bounded_artifact(job['pdf'],source)
            if sha(pdf)!=job['pdf_sha256']:raise ValueError('Cached PDF hash changed')
            if len(PdfReader(pdf).pages)!=len(job['pages']) or not job['pages']:raise ValueError('Incomplete cached pages')
            pages=[]
            for page in job['pages']:
                p=bounded_artifact(page['path'],source)
                if sha(p)!=page['sha256']:raise ValueError('Cached PNG hash changed')
                pages.append(p)
            planned.append((job,pdf,pages))
    except Exception as exc:return None,type(exc).__name__+': '+str(exc)
    render=qa/'render';render.mkdir();new_jobs=[]
    for job,pdf,pages in planned:
        folder=render/job['language'];folder.mkdir();target=folder/'report.pdf';shutil.copy2(pdf,target)
        if sha(target)!=job['pdf_sha256']:raise ValueError('PDF changed during cache copy')
        fresh={'language':job['language'],'docx':str(Path(reports['outputs'][job['language']]['path']).absolute()),'pdf':str(target),'pdf_sha256':job['pdf_sha256'],'pages':[]}
        for i,p in enumerate(pages,1):
            dest=folder/f'page-{i}.png';shutil.copy2(p,dest);h=sha(dest)
            if h!=job['pages'][i-1]['sha256']:raise ValueError('Page changed during cache copy')
            fresh['pages'].append({'path':str(dest),'sha256':h})
        new_jobs.append(fresh)
    result={'renderer':cached['renderer'],'jobs':new_jobs,'visual_review':'pending','cache_hit':True,
        'cache_source':str(source),'cache_manifest_sha256':sha(manifest),'render_contract':expected,
        'timings_s':{'cache_verify_and_copy':round(time.perf_counter()-started,6)}}
    return result,None
