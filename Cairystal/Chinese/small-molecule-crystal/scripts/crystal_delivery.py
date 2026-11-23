"""Audited final-model delivery: local/official validation, bilingual DOCX and explicit visual-review gate."""
import argparse,json,shutil,sys,time,zipfile
from pathlib import Path
from crystal_runtime import *
from validation_route import validate_local as local_validation,append_local_limit,mark_provisional

def run(args):
    from iucr_validation import validate
    from bilingual_report import build_from_dataset,render_reports
    root=new_directory(args.output);start=time.perf_counter()
    record={'schema':1,'stem':args.stem,'started_at':utc_now(),'status':'running','scientific_acceptance':'needs_review','timings_s':{},'inputs':{},'workflow_version':{p.name:sha(p) for p in Path(__file__).parent.glob('*.py') if p.name in {'crystal_delivery.py','crystal_runtime.py','bilingual_report.py','iucr_validation.py','refinement_gate.py','audit_occupancy.py','parse_platon_alerts.py','local_validation_cache.py','report_preflight.py','routine_consistency.py','structure_viewer.py'}}}
    record['workflow_version']['release']=json.loads((Path(__file__).resolve().parent.parent/'release_info.json').read_text('utf-8'))['release_id']
    def save():write_json(root/'result.json',record)
    def timed(name,fn):
        t=time.perf_counter();event={'stage':name,'started_at':utc_now(),'status':'running'}
        record.setdefault('events',[]).append(event);save()
        try:
            result=fn();event['status']='completed';return result
        except Exception as exc:
            event.update(status='failed',error=str(exc));raise
        finally:
            event['finished_at']=utc_now();event['seconds']=round(time.perf_counter()-t,3)
            record['timings_s'][name]=event['seconds'];save()
    record['data_directory']=str(Path(getattr(args,'data_dir',None) or args.input).absolute())
    save()
    try:
        notes_path=regular(args.notes);notes=json.loads(notes_path.read_text(encoding='utf-8'));record['notes_sha256']=sha(notes_path)
        shutil.copy2(notes_path,root/'reviewer_notes.json')
        audit=timed('input_pairing',lambda:paired_bundle(args.input,args.stem));write_json(root/'input_audit.json',audit)
        if audit.get('solvent_mask'):
            from squeeze_bundle import bilingual_notes
            mask_notes=bilingual_notes(audit['solvent_mask'])
            for lang in ['zh','en']:
                for key in ['methods','limitations']:
                    text=mask_notes[lang][key]
                    if text not in notes.setdefault(lang,{}).get(key,''):notes[lang][key]=notes[lang].get(key,'')+' '+text
            notes.setdefault('audit_records',{})['solvent_mask']=audit['solvent_mask']
            write_json(root/'reviewer_notes.json',notes)
            record['effective_notes_sha256']=sha(root/'reviewer_notes.json')
        record['inputs']=audit['source_sha256'];record['input_paths']=audit['files'];record['metrics']=audit['gate']['metrics'];save()
        frozen=root/'frozen';timed('freeze_bundle',lambda:freeze_bundle(audit,frozen,args.stem))
        naming_map=Path(args.input)/'atom_label_map.json'
        if naming_map.is_file():shutil.copy2(naming_map,frozen/'atom_label_map.json')
        if args.metadata_source:
            if not args.pairing_evidence:raise ValueError('Metadata source requires --pairing-evidence for the same experiment')
            from prepare_validation_metadata import prepare
            original=frozen/f'{args.stem}.cif';temp=root/'metadata_augmented.cif'
            timed('metadata_merge',lambda:prepare(Path(args.metadata_source),original,temp,Path(args.pairing_evidence)))
            shutil.copy2(original,root/'pre_metadata.cif');shutil.copy2(temp,original)
        from report_preflight import review_contacts
        contact_review=timed('contact_reporting_preflight',lambda:review_contacts(frozen/f'{args.stem}.cif'))
        write_json(root/'contact_reporting_preflight.json',contact_review)
        from cif_text_preflight import encode_narratives,add_assistance_comment
        text_preflight=timed('cif_text_preflight',lambda:encode_narratives(frozen/f'{args.stem}.cif',root/'cif_text_preflight.json'))
        final_audit=paired_bundle(frozen,args.stem)
        from routine_consistency import require_consistency,summary as consistency_summary
        write_json(root/'routine_consistency.json',final_audit['routine_checks'])
        record['routine_consistency']=consistency_summary(final_audit['routine_checks'])
        timed('routine_consistency_gate',lambda:require_consistency(final_audit['routine_checks']))
        from atom_labels import require_normalized,sort_cif
        record['atom_numbering']=timed('atom_numbering_gate',lambda:require_normalized(Path(audit['files']['res']).read_text('latin1')))
        record['atom_table_order']=timed('atom_table_order',lambda:sort_cif(frozen/f'{args.stem}.cif'))
        attribution=timed('cif_assistance_credit',lambda:add_assistance_comment(frozen/f'{args.stem}.cif',root/'cif_assistance_credit.json'))
        from disorder_bond_review import annotate,trial_review
        bond_review=timed('disorder_bond_review',lambda:trial_review(frozen,args.stem))
        write_json(root/'disorder_bond_review.json',bond_review)
        record['disorder_bond_review']=bond_review
        annotate(bond_review,notes)
        if getattr(args,'local_cache',None):
            from validation_route import reuse_local as reuse
            local=timed('local_validation',lambda:reuse(args.local_cache,frozen,root/'local_validation',args.stem,args.platon))
        else:
            local=timed('local_validation',lambda:local_validation(args.platon,frozen,root/'local_validation',args.stem,args.timeout))
        from delivery_continue import sealed_files
        write_json(root/'resume_notes.json',notes)
        record['resume_binding']={'frozen_files':sealed_files(frozen),'notes_sha256':sha(root/'resume_notes.json')}
        record['local_counts']=(local.get('alerts') or {}).get('counts')
        save()
        official,parsed=timed('official_validation',lambda:validate(frozen/f'{args.stem}.cif',root/'official',args.authorize_iucr_upload,args.official_cache,args.timeout))
        record['official']={'cif_sha256':official['cif_sha256'],'cache_hit':official['cache_hit'],'counts':parsed['counts'],'pdf_url':official['pdf_url'],'ckf_url':official['ckf_url']}
        record['AB_alerts']=[a for a in parsed['alerts'] if a['level'] in 'AB'];record['local_counts']=(local.get('alerts') or {}).get('counts');record['local_validation_available']=local.get('available',True)
        append_local_limit(notes,local)
        if record['AB_alerts']:mark_provisional(notes,record['AB_alerts'])
        write_json(root/'reviewer_notes.json',notes);record['effective_notes_sha256']=sha(root/'reviewer_notes.json');save()
        qa=root/'qa';qa.mkdir();delivery=root/'delivery';shutil.copytree(frozen,delivery)
        from bilingual_report import extract
        dataset=extract(frozen/f'{args.stem}.cif')
        write_json(delivery/'full_audit_records.json',{'source_notes':notes,'source_narratives':{k.lower():v for k,v in dataset['scalars'].items() if k.lower() in {'_publ_section_exptl_refinement','_exptl_absorpt_special_details'}},'text_preflight':text_preflight,'cairystal_attribution':attribution,'routine_consistency':final_audit['routine_checks'],'input_audit':audit,'native_log':f'{args.stem}.lst'})
        shutil.copy2(root/'official/IUCr_checkCIF.pdf',delivery/'IUCr_checkCIF.pdf');shutil.copy2(root/'official/submission.json',delivery/'IUCr_submission.json')
        figure=None
        from pypdf import PdfReader
        for p in PdfReader(root/'official/IUCr_checkCIF.pdf').pages:
            if 'ellipsoid plot' in (p.extract_text() or '').lower() and list(p.images):
                im=max(p.images,key=lambda i:len(i.data));figure=qa/('official_structure'+Path(im.name).suffix);figure.write_bytes(im.data);break
        reports=timed('bilingual_docx',lambda:build_from_dataset(delivery/f'{args.stem}.cif',dataset,parsed,notes,delivery,qa,figure))
        rendered=timed('rendering',lambda:render_reports(reports,qa,args.renderer,args.pdftoppm,args.soffice,args.powershell,getattr(args,'render_cache',None)))
        record['report_render_cache']={k:rendered.get(k) for k in ('cache_hit','cache_source','cache_miss_reason')}
        def official_previews():
            preview=qa/'official_pages';preview.mkdir()
            result=run_command([args.pdftoppm,'-r','110','-png',root/'official/IUCr_checkCIF.pdf',preview/'page'],preview,preview/'raster.log',args.timeout)
            pages=sorted(preview.glob('page-*.png'))
            if result['returncode'] or len(pages)!=len(PdfReader(root/'official/IUCr_checkCIF.pdf').pages):raise ValueError('Official PDF preview incomplete')
            result['pages']=[{'path':str(p),'sha256':sha(p)} for p in pages];write_json(qa/'official_pages_manifest.json',result);return result
        timed('official_pdf_preview',official_previews)
        from delivery_contract import require
        record['completion']=timed('delivery_completeness',lambda:require(root,args.stem))
        from structure_viewer import prepare_delivery
        record['structure_viewer']=timed('structure_viewer',lambda:prepare_delivery(delivery/f'{args.stem}.cif',delivery/f'{args.stem}.res',delivery,parsed['counts']))
        record['viewer_auto_open']=not getattr(args,'no_open_viewer',False)
        record['delivery_seal']={p.name:sha(p) for p in delivery.iterdir() if p.is_file()}
        record['qa_seal']={str(p.relative_to(qa)):sha(p) for p in qa.rglob('*') if p.is_file()}
        if not all(sha(path)==audit['source_sha256'][ext] for ext,path in audit['files'].items()):raise ValueError('Source changed during pipeline')
        record.update(status='awaiting_visual_review',automated_elapsed_s=round(time.perf_counter()-start,3),automated_finished_at=utc_now(),inputs_unchanged=True,report_pages={j['language']:len(j['pages']) for j in rendered['jobs']})
        from performance_audit import summarize as summarize_performance
        record['performance_summary']=summarize_performance(record['timings_s'],record['automated_elapsed_s'])
        write_json(root/'performance.json',record['performance_summary'])
        save()
        print(json.dumps({'output':str(root),'status':record['status'],'metrics':record['metrics'],'official_counts':parsed['counts'],'AB_alerts':record['AB_alerts'],'routine_consistency':record['routine_consistency'],'timings_s':record['timings_s'],'automated_elapsed_s':record['automated_elapsed_s'],'render_manifest':str(qa/'render_manifest.json')},ensure_ascii=False))
        return 0
    except Exception as exc:
        record.update(status='failed',failed_at=utc_now(),failure=str(exc),elapsed_s=round(time.perf_counter()-start,3))
        if record.get('resume_binding') and (root/'official/submission.json').is_file():
            if record['events'][-1].get('stage')=='official_validation':
                checkpoint=json.loads((root/'official/submission.json').read_text(encoding='utf-8'))
                if checkpoint.get('state') in {'awaiting_upload_authorization','form_unreachable_before_submission','reports_download_failed'}:
                    record['status']=checkpoint['state']
            record['continuation']={'command':'cairystal.py run deliver -- continue','run':str(root.absolute()),
                'cif':str(frozen/(args.stem+'.cif')),'expected_hkl_sha256':record['inputs']['hkl'],
                'first_step':'Use --inspect-only with the intended specimen HKL and selected CIF.'}
        save()
        print(json.dumps({'output':str(root),'status':record['status'],'failure':str(exc),'continuation':record.get('continuation')},ensure_ascii=False));return 1

def finalize(args):
    if getattr(args,'expected_hkl',None) or getattr(args,'cif',None):
        if not (args.expected_hkl and args.cif):
            raise ValueError('Provide both the expected HKL and selected CIF for the case-bound export.')
        from delivery_continue import inspect
        if inspect(args.run,args.cif,args.expected_hkl)['next']!='reuse_verified_report':
            raise ValueError('This specimen has no verified official report to export.')
    root=Path(args.run);record=json.loads((root/'result.json').read_text(encoding='utf-8'));delivery=root/'delivery'
    if record['status']!='awaiting_visual_review':raise ValueError('Only a complete awaiting-review run can be finalized')
    automatic=getattr(args,'automatic_qa',None)
    if automatic:
        q=json.loads(Path(automatic).read_text('utf-8-sig'))
        if q.get('status')!='automatic_checks_passed' or q.get('visual_review_performed') is not False:raise ValueError('Automatic QA must pass without claiming actual visual inspection')
        if q.get('delivery_hashes')!=record['delivery_seal'] or q.get('render_manifest_sha256')!=sha(root/'qa/render_manifest.json'):raise ValueError('Automatic QA belongs to different artifacts')
    elif not args.reviewed_zh or not args.reviewed_en or not args.reviewed_official or not args.review_note:
        raise ValueError('Both rendered languages and official report need actual review and a recorded note')
    for name,digest in record['delivery_seal'].items():
        if sha(delivery/name)!=digest:raise ValueError('Delivery changed since validation/render: '+name)
    for name,digest in record['qa_seal'].items():
        if sha(root/'qa'/name)!=digest:raise ValueError('QA evidence changed: '+name)
    for ext,path in record['input_paths'].items():
        if sha(path)!=record['inputs'][ext]:raise ValueError('Source changed since run: '+path)
    from delivery_contract import require
    record['completion']=require(root,record.get('stem','model'))
    audit={'reviewed_at':utc_now(),'review_note':args.review_note,'languages':['zh','en'],'official_report_reviewed':not bool(automatic),'pages':record['report_pages'],'delivery_hashes':record['delivery_seal'],'review_mode':'automated_rules' if automatic else 'actual_visual_review','visual_review_performed':not bool(automatic)}
    if automatic:audit.update(automated_qa_path=str(automatic),automated_qa_sha256=sha(automatic))
    write_json(root/('automatic_review.json' if automatic else 'visual_review.json'),audit)
    write_json(delivery/'SHA256SUMS.json',record['delivery_seal'])
    archive=root/'structure_and_reports.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for name in [*record['delivery_seal'],'SHA256SUMS.json']:z.write(delivery/name,name)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() or [n for n in z.namelist() if n.lower().endswith('.pdf')]!=['IUCr_checkCIF.pdf']:
            raise ValueError('ZIP verification or PDF delivery policy failed')
    record.update(status='delivery_complete_needs_scientific_review',finalized_at=utc_now(),zip={'path':str(archive),'sha256':sha(archive)})
    write_json(root/'result.json',record)
    from customer_delivery import publish
    try:
        exported=publish(root,getattr(args,'data_dir',None) or record['data_directory'])
        record.update(customer_delivery=exported,customer_notice=exported['notice'])
    except Exception as exc:
        record.update(status='customer_export_failed',customer_export_error=str(exc))
        write_json(root/'result.json',record)
        raise
    write_json(root/'result.json',record)
    from structure_viewer import open_generated
    record['viewer_open']=open_generated(record.get('structure_viewer'),record.get('viewer_auto_open',True))
    write_json(root/'viewer_open.json',record['viewer_open']);write_json(root/'result.json',record)
    print(json.dumps({'status':record['status'],'zip':str(archive),'official_counts':record['official']['counts'],'structure_viewer':record.get('structure_viewer'),'viewer_open':record['viewer_open'],'customer_delivery':record['customer_delivery'],'customer_notice':record['customer_notice']},ensure_ascii=False));return 0

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('run')
    for k in ['input','output','notes','platon','pdftoppm']:p.add_argument('--'+k,required=True)
    p.add_argument('--data-dir',help='Original specimen directory; customer copies go into its Cairystal folder')
    p.add_argument('--stem',default='model');p.add_argument('--renderer',choices=['word','libreoffice'],required=True);p.add_argument('--soffice')
    p.add_argument('--powershell',help='Approved host PowerShell executable for Word COM; never changes execution policy')
    p.add_argument('--authorize-iucr-upload',action='store_true');p.add_argument('--official-cache');p.add_argument('--timeout',type=float,default=180)
    p.add_argument('--no-open-viewer',action='store_true',help='Generate the viewer but do not request a browser window')
    p.add_argument('--metadata-source');p.add_argument('--pairing-evidence');p.add_argument('--local-cache',help='Reuse only a complete exact-hash local validation for these CIF/FCF and executable')
    p.add_argument('--render-cache',help='Explicit same-job QA directory; reuse only unchanged bilingual DOCX and render environment. Never searches old jobs.')
    p=sub.add_parser('finalize');p.add_argument('--run',required=True);p.add_argument('--review-note',required=True)
    p.add_argument('--expected-hkl');p.add_argument('--cif',help='Exact selected CIF paired with --expected-hkl')
    p.add_argument('--data-dir',help='Original specimen directory; overrides the recorded delivery input directory')
    p.add_argument('--automatic-qa',help='Exact-file automated QA report; never asserts human/AI visual inspection')
    for k in ['zh','en','official']:p.add_argument('--reviewed-'+k,action='store_true')
    p=sub.add_parser('continue',help='Inspect or continue a CIF/HKL-bound official delivery, without refining again')
    for name in ['run','expected-hkl','cif']:p.add_argument('--'+name,required=True)
    p.add_argument('--inspect-only',action='store_true');p.add_argument('--authorize-iucr-upload',action='store_true')
    p.add_argument('--profile');p.add_argument('--output');p.add_argument('--timeout',type=float,default=180)
    args=parser.parse_args()
    try:
        if args.action=='continue':
            from delivery_continue import run as continue_delivery
            sys.exit(continue_delivery(args))
        sys.exit(run(args) if args.action=='run' else finalize(args))
    except Exception as exc:print(json.dumps({'status':'failed','failure':str(exc)},ensure_ascii=False));sys.exit(1)
