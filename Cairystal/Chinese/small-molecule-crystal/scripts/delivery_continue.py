"""Continue an exact submitted/frozen pair, preserving the first delivery attempt."""
import hashlib
import json
import time
from pathlib import Path
from types import SimpleNamespace

from crystal_runtime import check_stem, regular, sha, utc_now, write_json
from pipeline_intake import unlinked, verify_profile
import iucr_validation as iucr


def read(path):
    return json.loads(regular(unlinked(path)).read_text(encoding='utf-8-sig'))


def sealed_files(folder):
    return {p.name:sha(regular(unlinked(p))) for p in folder.iterdir() if p.is_file()}


def inspect(root, expected_cif, expected_hkl):
    root=unlinked(root)
    record=read(root/'result.json')
    stem=check_stem(record['stem'])
    frozen=unlinked(root/'frozen')
    cif=regular(unlinked(frozen/(stem+'.cif')))
    cif_sha=sha(cif)
    hkl_sha=sha(regular(unlinked(expected_hkl)))
    if (sha(regular(unlinked(expected_cif)))!=cif_sha or
            sha(regular(unlinked(frozen/(stem+'.hkl'))))!=hkl_sha or
            record.get('inputs',{}).get('hkl')!=hkl_sha):
        raise ValueError('Wrong specimen or model version: expected CIF/HKL differ from the frozen delivery.')
    official=unlinked(root/'official')
    rec=read(official/'submission.json')
    snapshot=unlinked(official/'submitted.cif')
    awaiting=(rec.get('state')=='awaiting_upload_authorization' and rec.get('post_may_have_started') is False)
    if (rec.get('schema')!=1 or rec.get('options')!=iucr.OPTIONS or rec.get('cif_sha256')!=cif_sha
            or (not snapshot.is_file() and not awaiting) or (snapshot.is_file() and sha(regular(snapshot))!=cif_sha)):
        raise ValueError('Receipt and frozen model/options do not match.')
    if rec.get('state')=='completed':
        iucr.validate_saved(official,cif_sha)
        action='reuse_verified_report'
    elif rec.get('pdf_url') or rec.get('ckf_url') or (official/'response.html').exists():
        iucr.recover(official,expected_cif=cif,check_only=True)
        action='download_existing_reports'
    elif rec.get('state') in {'awaiting_upload_authorization','form_unreachable_before_submission'} and rec.get('post_may_have_started') is False:
        action='submit_only_with_authorization'
    else:
        action='inspect_unknown_submission'
    return {'run':str(root),'stem':stem,'cif_sha256':cif_sha,'hkl_sha256':hkl_sha,
            'official_state':rec.get('state'),'next':action,'network_action':'none'}


def run(args):
    root=unlinked(args.run)
    pair=inspect(root,args.cif,args.expected_hkl)
    if args.inspect_only:
        print(json.dumps(pair,ensure_ascii=False))
        return 0
    if not args.output or not args.profile:
        raise ValueError('Resuming delivery requires a new output folder and a local runtime profile.')
    if not 0 < args.timeout <= 86400:
        raise ValueError('Timeout must be positive and at most one day.')
    output=unlinked(args.output)
    if output.exists() or root in output.parents:
        raise ValueError('Use a new delivery directory outside the original run.')
    profile=read(args.profile)
    tools=verify_profile(profile)
    # Use the same workflow version for an actual continuation; old receipts remain inspectable.
    record=read(root/'result.json')
    version=read(Path(__file__).resolve().parents[1]/'release_info.json')['release_id']
    if record.get('workflow_version',{}).get('release')!=version:
        raise ValueError('Use the checkpoint release to continue this job. Read-only receipt inspection is available.')
    binding=record.get('resume_binding',{})
    notes=root/'resume_notes.json'
    if (not binding or sealed_files(root/'frozen')!=binding.get('frozen_files')
            or sha(regular(unlinked(notes)))!=binding.get('notes_sha256')):
        raise ValueError('Incomplete or changed frozen model/notes. Preserve the checkpoint for review.')
    guard=root/'continue_delivery.lock'
    with guard.open('x',encoding='utf-8') as handle:
        handle.write(utc_now())
    try:
        pair=inspect(root,args.cif,args.expected_hkl)
        if sealed_files(root/'frozen')!=binding['frozen_files'] or sha(notes)!=binding['notes_sha256']:
            raise ValueError('Frozen inputs changed before continuation.')
        official=root/'official'
        if pair['next']=='inspect_unknown_submission':
            raise ValueError('A submission may have been made; inspect the existing receipt. No POST performed.')
        if pair['next']=='submit_only_with_authorization':
            if not args.authorize_iucr_upload:
                raise ValueError('Direct authorization covering this specimen is required before submitting it.')
            snapshot=official/'submitted.cif'
            payload=(snapshot if snapshot.exists() else regular(unlinked(args.cif))).read_bytes()
            if hashlib.sha256(payload).hexdigest()!=pair['cif_sha256']:
                raise ValueError('Payload changed before submission.')
            if not snapshot.exists():
                with snapshot.open('xb') as file:file.write(payload)
            rec=read(official/'submission.json')
            rec.setdefault('continuations',[]).append({'time':utc_now(),'from':rec['state']})
            rec.update(state='preflight')
            rec.pop('error',None)
            write_json(official/'submission.json',rec)
            iucr.submit_snapshot(payload,rec,official,args.timeout,time.perf_counter())
        elif pair['next']=='download_existing_reports':
            iucr.recover(official,args.timeout,args.cif)
        if sealed_files(root/'frozen')!=binding['frozen_files'] or sha(notes)!=binding['notes_sha256']:
            raise ValueError('Frozen inputs changed during report retrieval.')
        from crystal_delivery import run as deliver
        settings=SimpleNamespace(input=str(root/'frozen'),output=str(output),notes=str(notes),
            stem=pair['stem'],renderer=profile['renderer'],platon=tools['platon'],pdftoppm=tools['pdftoppm'],
            powershell=tools.get('powershell'),soffice=tools.get('soffice'),timeout=args.timeout,
            authorize_iucr_upload=False,official_cache=str(official),local_cache=str(root/'local_validation'),
            metadata_source=None,pairing_evidence=None,data_dir=record['data_directory'],no_open_viewer=True,
            render_cache=str(root/'qa'))
        return deliver(settings)
    finally:
        guard.unlink()
