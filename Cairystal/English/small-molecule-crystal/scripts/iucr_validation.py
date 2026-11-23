"""Authorized official checkCIF submission and exact-hash cache. No deposition/email/identity lookup."""
import json,re,shutil,time,urllib.request,urllib.parse,uuid
import urllib.error
import hashlib
import io
from html.parser import HTMLParser
import iucr_browser
from checkcif_identifiers import ALERT_TOKEN, test_code
from pathlib import Path
from crystal_runtime import sha,write_json,utc_now

HOST='checkcif.iucr.org'
OPTIONS={'from_index':'from_index','runtype':'symmonly','referer':'checkcif_server',
 'outputtype':'PDF','Qemailaddress':'','validtype':'checkcif_with_hkl','valout':'vrfab','duplic':'duplicno','UPLOAD':'Send CIF for checking'}

class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        check_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def check_url(url):
    p=urllib.parse.urlparse(url)
    if p.scheme!='https' or p.hostname!=HOST or p.username is not None or p.password is not None or p.port not in (443,None):raise ValueError('Only HTTPS checkcif.iucr.org allowed')
    return url

def check_report_pair(record):
    pdf=check_url(record['pdf_url'])
    ckf=check_url(record['ckf_url'])
    if urllib.parse.urljoin(pdf,'.')!=urllib.parse.urljoin(ckf,'.'):
        raise ValueError('Official report links belong to different jobs')

def fetch(url,data=None,headers=None,timeout=180,limit=20*1024*1024):
    check_url(url);opener=urllib.request.build_opener(RestrictedRedirect())
    req=urllib.request.Request(url,data=data,headers=headers or {})
    with opener.open(req,timeout=timeout) as response:
        check_url(response.url);body=response.read(limit+1)
        if len(body)>limit:raise ValueError('Official response exceeded bounded size')
        return body,response.url

def measured_fetch(record,stage,*args,**kwargs):
    """Record a single request, including failures; never add a retry."""
    start=time.perf_counter()
    try:return fetch(*args,**kwargs)
    finally:record.setdefault('timings_s',{})[stage]=round(time.perf_counter()-start,6)

def parse_official_text(text):
    alerts=[]
    for line in text.splitlines():
        line=line.lstrip()
        m=ALERT_TOKEN.match(line)
        if m:
            # Preserve non-PLAT dictionary checks (EXPT, DIFF, CHEMW, ...).
            # Keep the established numeric PLAT code for existing callers.
            level=m[3].upper()
            alerts.append({'code':f'{test_code(m[1])}_ALERT_{m[2]}_{level}',
                'full_code':m[0].upper(),'level':level,'text':line[m.end():].strip()})
    counts={l:sum(a['level']==l for a in alerts) for l in 'ABCG'}
    printed={m[2].upper():int(m[1]) for m in re.finditer(r'(\d+)\s+ALERT\s+level\s+([ABCG])\s*=',text,re.I)}
    if set(printed)!=set('ABCG') or printed!=counts:raise ValueError('Official alert summary absent or counts inconsistent')
    if not re.search(r'Structure factors have been supplied',text,re.I):raise ValueError('Official report does not confirm structure factors')
    if not re.search(r'No syntax errors',text,re.I):raise ValueError('Official CIF syntax success absent')
    return {'counts':counts,'alerts':alerts,'structure_factors_supplied':True,'no_syntax_errors':True}

def verified_files(folder,cif_hash,rec):
    if rec.get('schema')!=1 or rec.get('cif_sha256')!=cif_hash or rec.get('options')!=OPTIONS:
        raise ValueError('Cache schema, exact CIF hash or validation options differ')
    files=rec.get('files',{})
    if files.get('submitted.cif')!=cif_hash or sha(folder/'submitted.cif')!=cif_hash:
        raise ValueError('Cached submitted CIF hash differs')
    check_report_pair(rec)
    pdf=(folder/'IUCr_checkCIF.pdf').read_bytes()
    ckf=(folder/'ckf.html').read_bytes()
    for name,content in [('IUCr_checkCIF.pdf',pdf),('ckf.html',ckf)]:
        if hashlib.sha256(content).hexdigest()!=files.get(name):raise ValueError('Official cache file hash differs: '+name)
    if b'FCF-File Validation' not in ckf or b'LIST4' not in ckf:raise ValueError('Structure-factor validation detail incomplete')
    return pdf


def validate_saved(folder,cif_hash):
    from pypdf import PdfReader
    folder=Path(folder);rec=json.loads((folder/'submission.json').read_text(encoding='utf-8'))
    pdf=verified_files(folder,cif_hash,rec)
    txt='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(pdf)).pages)
    return rec,parse_official_text(txt)

class ReportLinks(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base = check_url(base)
        self.links = {}

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get('href')
        if tag != 'a' or not href:
            return
        url = urllib.parse.urljoin(self.base, href)
        name = urllib.parse.urlsplit(url).path.rsplit('/', 1)[-1]
        if name in ('checkcif.pdf', 'ckf.html'):
            self.links.setdefault(name, set()).add(check_url(url))

    def pair(self):
        if any(len(self.links.get(name, ())) != 1 for name in ('checkcif.pdf', 'ckf.html')):
            raise ValueError('Official receipt has no unique PDF and structure-factor report pair')
        pdf, ckf = (next(iter(self.links[name])) for name in ('checkcif.pdf','ckf.html'))
        if urllib.parse.urljoin(pdf, '.') != urllib.parse.urljoin(ckf, '.'):
            raise ValueError('Official report links belong to different jobs')
        return {'pdf_url': pdf, 'ckf_url': ckf}


def record_receipt(destination, rec, page, url):
    rec['receipt_url'] = check_url(url)
    (destination/'response.html').write_text(page, encoding='utf-8')
    parser = ReportLinks(url)
    parser.feed(page)
    rec.update(parser.pair(), state='reports_available')
    write_json(destination/'submission.json', rec)


def get_receipt(payload, rec, destination, timeout):
    stage = 'form_get'
    endpoint = iucr_browser.FORM
    rec['route'] = 'direct_http'
    try:
        form,_=measured_fetch(rec,stage,endpoint,timeout=min(timeout,30))
        names=set(re.findall(r'name=["\']([^"\']+)',form.decode(errors='replace'),re.I))
        if not set(OPTIONS).union({'filecif'})<=names:raise ValueError('Official form changed; inspect before submission')
        bound='----CrystalSkill'+uuid.uuid4().hex
        parts=[(f'--{bound}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n').encode() for k,v in OPTIONS.items()]
        parts.extend([(f'--{bound}\r\nContent-Disposition: form-data; name="filecif"; filename="model.cif"\r\nContent-Type: chemical/x-cif\r\n\r\n').encode(),payload,f'\r\n--{bound}--\r\n'.encode()])
        rec.update(state='submitting', post_may_have_started=True)
        write_json(destination/'submission.json',rec)
        stage, endpoint = 'submission_post_and_server', iucr_browser.SUBMIT
        body,url=measured_fetch(rec,stage,endpoint,b''.join(parts),{'Content-Type':'multipart/form-data; boundary='+bound},timeout)
    except urllib.error.HTTPError as exc:
        if exc.code != 403 or exc.geturl() != endpoint or any(exc.headers and exc.headers.get(k) for k in ('Retry-After','WWW-Authenticate','cf-mitigated')):
            raise
        exc.close()
        rec['route'] = 'official_browser_after_http_403'
        rec['browser'] = {'stage': 'opening', 'direct_stage': stage, 'direct_http_status': 403}
        write_json(destination/'submission.json',rec)
        def checkpoint(state, details):
            if state == 'submitting':
                rec['post_may_have_started'] = True
            rec['browser'].update(details, stage=state)
            write_json(destination/'submission.json',rec)
        stamp = time.perf_counter()
        try:
            iucr_browser.submit(payload, OPTIONS, timeout, checkpoint,
                                lambda page, url: record_receipt(destination, rec, page, url))
        finally:
            rec['timings_s']['browser_session'] = round(time.perf_counter()-stamp, 6)
            write_json(destination/'submission.json',rec)
        return
    record_receipt(destination, rec, body.decode('utf-8', errors='replace'), url)


def validate(cif,destination,authorized=False,cache=None,timeout=180):
    from pypdf import PdfReader
    from cif_text_preflight import check_ascii
    cif=Path(cif);destination=Path(destination);destination.mkdir()
    # Before even fetching the form; never pay network latency for invalid CIF1 bytes.
    check_ascii(cif)
    from cif_format_check import require as require_cif_format
    require_cif_format(cif)
    start=time.perf_counter();digest=sha(cif)
    if cache:
        rec,parsed=validate_saved(cache,digest)
        for name in ['submitted.cif','IUCr_checkCIF.pdf','ckf.html','response.html','official_text.txt']:
            if (Path(cache)/name).exists():shutil.copy2(Path(cache)/name,destination/name)
        rec.update(cache_source=str(Path(cache).absolute()),cache_hit=True,elapsed_s=round(time.perf_counter()-start,3))
        write_json(destination/'submission.json',rec);return rec,parsed
    payload=cif.read_bytes()
    import hashlib
    if hashlib.sha256(payload).hexdigest()!=digest:raise ValueError('CIF changed before the upload snapshot')
    rec={'schema':1,'date':utc_now(),'cif_sha256':digest,'options':OPTIONS,'state':'preflight','cache_hit':False,
         'post_may_have_started':False}
    if not authorized:
        rec['state']='awaiting_upload_authorization'
        write_json(destination/'submission.json',rec)
        raise ValueError('Official upload requires explicit authorization flag; no network submission performed')
    (destination/'submitted.cif').write_bytes(payload)
    write_json(destination/'submission.json',rec)
    return submit_snapshot(payload, rec, destination, timeout, start)


def submit_snapshot(payload, rec, destination, timeout, start):
    try:
        get_receipt(payload, rec, destination, timeout)
        return download_reports(destination,rec,timeout,start)
    except Exception as exc:
        never_sent = (rec.get('post_may_have_started') is False and rec.get('route')=='direct_http'
                      and isinstance(exc, OSError) and not isinstance(exc,urllib.error.HTTPError))
        state = 'reports_download_failed' if rec.get('pdf_url') and rec.get('ckf_url') else (
            'form_unreachable_before_submission' if never_sent else 'failed_or_submission_outcome_unknown')
        rec.update(state=state,error=str(exc),elapsed_s=round(time.perf_counter()-start,3))
        write_json(destination/'submission.json',rec);raise


def report_get(url,destination,rec,kind,timeout=180):
    """Bounded retries of an existing report GET; never retries a CIF POST."""
    import urllib.error
    destination=Path(destination)
    for attempt in range(1,4):
        request_start=time.perf_counter()
        event={'kind':kind,'url':check_url(url),'method':'GET','attempt':attempt,'started_at':utc_now()}
        rec.setdefault('report_get_attempts',[]).append(event)
        try:
            body,_=fetch(url,timeout=min(timeout,60))
            if kind=='pdf' and not body.startswith(b'%PDF'):
                (destination/f'pdf_non_pdf_response_{len(rec["report_get_attempts"]):02d}.bin').write_bytes(body)
                raise ValueError('Linked PDF returned non-PDF content; response preserved')
            if kind=='ckf' and (b'FCF-File Validation' not in body or b'LIST4' not in body):
                (destination/f'ckf_incomplete_response_{len(rec["report_get_attempts"]):02d}.bin').write_bytes(body)
                raise ValueError('Linked FCF report incomplete; response preserved')
            event.update(status='downloaded',bytes=len(body));return body
        except (OSError,ValueError) as e:
            event.update(status='failed',error=str(e))
            retry=not isinstance(e,urllib.error.HTTPError) or e.code in {404,408,429,500,502,503,504}
            if attempt==3 or not retry:raise
            time.sleep(attempt)
        finally:
            event['elapsed_s']=round(time.perf_counter()-request_start,6)
            event['finished_at']=utc_now();write_json(destination/'submission.json',rec)


def download_reports(destination,rec,timeout=180,start=None):
    """GET existing report URLs only; never repeat the CIF POST."""
    from pypdf import PdfReader
    destination=Path(destination);start=time.perf_counter() if start is None else start
    digest=rec['cif_sha256']
    if sha(destination/'submitted.cif')!=digest:raise ValueError('Frozen submitted CIF changed; cannot associate reports')
    check_report_pair(rec)
    event={'started_at':utc_now(),'method':'GET_reports_only','status':'running'}
    rec.setdefault('download_attempts',[]).append(event);write_json(destination/'submission.json',rec)
    try:
        pdf_path=destination/'IUCr_checkCIF.pdf';retained=rec.get('downloaded_pdf')
        if retained:
            if not pdf_path.is_file():raise ValueError('Retained PDF changed; cannot reuse it')
            pdf=pdf_path.read_bytes()
            if hashlib.sha256(pdf).hexdigest()!=retained['sha256']:raise ValueError('Retained PDF changed; cannot reuse it')
            event['retained_pdf_reused']=True
        else:
            pdf=report_get(check_url(rec['pdf_url']),destination,rec,'pdf',timeout)
            # Save PDF before fetching FCF detail; a later failure must not lose it.
            pdf_path.write_bytes(pdf)
        reader=PdfReader(io.BytesIO(pdf))
        if not reader.pages:raise ValueError('Downloaded PDF has no readable pages')
        rec['downloaded_pdf']={'path':'IUCr_checkCIF.pdf','sha256':hashlib.sha256(pdf).hexdigest(),'pages':len(reader.pages),'bytes':len(pdf)}
        rec['state']='pdf_downloaded';write_json(destination/'submission.json',rec)
        txt='\n'.join(p.extract_text() or '' for p in reader.pages)
        (destination/'official_text.txt').write_text(txt,encoding='utf-8');parsed=parse_official_text(txt)
        ckf=report_get(check_url(rec['ckf_url']),destination,rec,'ckf',timeout)
        (destination/'ckf.html').write_bytes(ckf)
        if sha(destination/'submitted.cif')!=digest:raise ValueError('Frozen submitted CIF changed during download')
        rec.update(counts=parsed['counts'],alerts=parsed['alerts'],files={'submitted.cif':digest,
                   'IUCr_checkCIF.pdf':rec['downloaded_pdf']['sha256'],'ckf.html':hashlib.sha256(ckf).hexdigest()})
        # Check the exact bytes on disk against the payloads just parsed before declaring completion.
        verified_files(destination,digest,rec)
        rec.update(state='completed',elapsed_s=round(time.perf_counter()-start,3))
        event['status']='completed';rec.pop('error',None)
        return rec,parsed
    except Exception as e:
        event.update(status='failed',error=str(e));rec.update(state='reports_download_failed',error=str(e));raise
    finally:
        event['finished_at']=utc_now();write_json(destination/'submission.json',rec)


def recover(folder,timeout=180,expected_cif=None,check_only=False):
    """Resume a known report response without uploading or changing CIF content."""
    folder=Path(folder);rec=json.loads((folder/'submission.json').read_text('utf-8'))
    if rec.get('schema')!=1 or rec.get('options')!=OPTIONS:raise ValueError('Unknown submission record/options')
    if rec.get('state')=='awaiting_upload_authorization' and rec.get('post_may_have_started') is False and not (folder/'submitted.cif').exists():
        if expected_cif is None or sha(expected_cif)!=rec['cif_sha256']:
            raise ValueError('This pending job needs its exact frozen CIF.')
        if check_only:return rec,None
        raise ValueError('No report to download. Continue the specimen-bound delivery after upload authorization.')
    if sha(folder/'submitted.cif')!=rec.get('cif_sha256'):raise ValueError('Submitted CIF hash mismatch')
    if expected_cif is not None and sha(expected_cif)!=rec['cif_sha256']:
        raise ValueError('Selected CIF hash differs from this receipt. Select the matching delivery job.')
    if rec.get('state')=='completed':return validate_saved(folder,rec['cif_sha256'])
    if rec.get('state')=='form_unreachable_before_submission' and rec.get('post_may_have_started') is False:
        if check_only:return rec,None
        raise ValueError('The initial form GET failed before upload. Use specimen-bound delivery continuation after resolving connectivity and authorization.')
    if check_only:
        if rec.get('downloaded_pdf'):
            retained=folder/'IUCr_checkCIF.pdf'
            if not retained.is_file() or sha(retained)!=rec['downloaded_pdf'].get('sha256'):
                raise ValueError('Retained PDF changed; cannot reuse it')
        if rec.get('pdf_url') and rec.get('ckf_url'):
            check_report_pair(rec)
        else:
            response=folder/'response.html'
            if not response.is_file():raise ValueError('No confirmed report response; outcome remains uncertain')
            parser=ReportLinks(rec.get('receipt_url', iucr_browser.SUBMIT))
            parser.feed(response.read_text('utf-8'));parser.pair()
        return rec,None
    if not rec.get('pdf_url') or not rec.get('ckf_url'):
        response=folder/'response.html'
        if not response.is_file():raise ValueError('No confirmed report response; outcome remains uncertain and no resubmission is performed')
        record_receipt(folder, rec, response.read_text('utf-8'), rec.get('receipt_url', iucr_browser.SUBMIT))
    return download_reports(folder,rec,timeout)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('recover');r.add_argument('--directory',required=True);r.add_argument('--timeout',type=float,default=180)
    r.add_argument('--cif',help='Compare this exact CIF to the submitted one before recovery')
    r.add_argument('--check-only',action='store_true',help='Check local files and receipt without fetching or writing')
    s=sub.add_parser('submit');s.add_argument('--cif',required=True);s.add_argument('--output',required=True);s.add_argument('--authorize-iucr-upload',action='store_true');s.add_argument('--timeout',type=float,default=180)
    args=p.parse_args()
    try:
        if args.command=='recover':
            record,parsed=recover(args.directory,args.timeout,args.cif,args.check_only);folder=Path(args.directory)
            if args.check_only:
                print(json.dumps({'state':record['state'],'cif_sha256':record['cif_sha256'],'compared_cif':args.cif,
                                  'counts':parsed['counts'] if parsed else None,'network_action':'none',
                                  'next':'reuse_complete_official_cache' if parsed else (
                                      'continue_delivery_with_matching_specimen' if record['state'] in {'awaiting_upload_authorization','form_unreachable_before_submission'} else 'recover_from_receipt')},ensure_ascii=False))
                raise SystemExit(0)
        else:record,parsed=validate(args.cif,args.output,args.authorize_iucr_upload,timeout=args.timeout);folder=Path(args.output)
        print(json.dumps({'state':record['state'],'counts':parsed['counts'],'pdf':str(folder/'IUCr_checkCIF.pdf'),'pdf_sha256':sha(folder/'IUCr_checkCIF.pdf'),'network_action':'existing_report_GET_only' if args.command=='recover' else 'one_authorized_submission_then_report_GETs'},ensure_ascii=False))
    except Exception as e:
        print(json.dumps({'state':'incomplete','error':str(e),'next':'Inspect saved submission.json; recover existing report URLs without repeating the CIF upload.'},ensure_ascii=False));raise SystemExit(1)
