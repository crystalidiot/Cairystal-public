"""One reproducible local image pipeline; uncertainty becomes a compact handoff."""
import argparse,json,subprocess,time,os,sys
from pathlib import Path
from molscribe_local import sha,safe,write
def read(p):return json.loads(safe(p).read_text(encoding='utf-8-sig'))
def validate_manifest(path):
    m=read(path)
    if set(m)-{'schema','checkpoint_sha256','cases'}:raise ValueError('Image-only manifest required')
    for c in m['cases']:
        if set(c)-{'case_id','image','image_sha256','elements'}:raise ValueError('Chemical reference/answer fields forbidden')
        if not c['case_id'].isalnum() or not c['elements']:raise ValueError('Case ID and possible elements required')
        if sha(safe(c['image']))!=c['image_sha256']:raise ValueError('Source image changed')
    return m
def run(config,output):
    cfg=read(config)
    if set(cfg)!={'schema','manifests','mol_python','ocr_python','checkpoint','ocr_models'}:raise ValueError('Unexpected image-pipeline config')
    ids=set()
    for mf in cfg['manifests']:
        for row in validate_manifest(mf)['cases']:
            if row['case_id'] in ids:raise ValueError('Duplicate image ID')
            ids.add(row['case_id'])
    for record in cfg['ocr_models']:
        if sha(safe(record['path']))!=record['sha256']:raise ValueError('OCR model changed')
    if sha(safe(cfg['checkpoint']))!='6f0df56fa32b5ffc21f8c7f311ef333da522f590bf5622e966c6bcb1f2d9ea1d':raise ValueError('MolScribe checkpoint changed')
    root=safe(output)
    if root.exists():raise ValueError('New output directory required')
    root.mkdir(parents=True);(root/'logs').mkdir();write(root/'input_config.json',cfg)
    scripts=Path(__file__).parent;source_hashes={p.name:sha(p) for p in scripts.glob('*.py')}
    state={'status':'running','config_sha256':sha(config),'script_hashes':source_hashes,'stages':[],'external_LLM_calls':0};start=time.perf_counter()
    args=sum((['--manifest',m] for m in cfg['manifests']),[])
    stages=[('page_ocr',cfg['ocr_python'],'ocr_image_evidence.py',args+['--output',str(root/'page_ocr')]),
     ('segmentation',cfg['mol_python'],'diagram_regions.py',args+['--ocr',str(root/'page_ocr/result.json'),'--output',str(root/'regions')]),
     ('fragment_ocr',cfg['ocr_python'],'ocr_image_evidence.py',['--manifest',str(root/'regions/crop_ocr_manifest.json'),'--output',str(root/'fragment_ocr')]),
     ('label_ocr',cfg['ocr_python'],'ocr_label_checks.py',['--source',str(root/'fragment_ocr/result.json'),'--output',str(root/'label_ocr')]),
     ('multiview',cfg['mol_python'],'diagram_predict.py',['--regions',str(root/'regions/regions.json'),'--crop-ocr',str(root/'fragment_ocr/result.json'),'--checkpoint',cfg['checkpoint'],'--output',str(root/'multiview')]),
     ('consensus',cfg['mol_python'],'diagram_consensus.py',['--regions',str(root/'regions/regions.json'),'--raw',str(root/'multiview/raw_predictions.json'),'--labels',str(root/'label_ocr/result.json'),'--output',str(root/'consensus')])]
    env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',TEMP=str(root.parent/'tmp'),TMP=str(root.parent/'tmp'),MPLCONFIGDIR=str(root.parent/'cache/matplotlib'),TORCH_HOME=str(root.parent/'cache/torch'))
    for name,python,script,options in stages:
        command=[python,'-B',str(scripts/script),*options];log=root/'logs'/(name+'.log');clock=time.perf_counter()
        error=None
        with log.open('x',encoding='utf-8') as stream:
            try:
                proc=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=900);returncode=proc.returncode
            except subprocess.TimeoutExpired:
                returncode=-9;error='Stage exceeded the recorded 900-second execution guard; child was terminated. No automatic replay.'
            except OSError as exc:returncode=-1;error=str(exc)
        state['stages'].append({'name':name,'command':command,'seconds':time.perf_counter()-clock,'returncode':returncode,'error':error,'log':str(log)})
        write(root/'run.json',state);print(json.dumps({'stage':name,'seconds':state['stages'][-1]['seconds'],'returncode':returncode}),flush=True)
        if returncode:state['status']='failed';state['wall_seconds']=time.perf_counter()-start;write(root/'run.json',state);return state
    decision=read(root/'consensus/result.json');state['status']='complete';state['wall_seconds']=time.perf_counter()-start
    state['recognition_review_cases']=[c['case_id'] for c in decision['cases'] if c['recognition_status']=='needs_AI_review']
    state['ready_for_refinement_trial']=[c['case_id'] for c in decision['cases'] if c['pipeline_status']=='ready_for_refinement_trial']
    state['input_hashes_unchanged']=all(validate_manifest(mf) is not None for mf in cfg['manifests']);write(root/'run.json',state)
    write(root/'handoff.json',{'cases':[{'case_id':c['case_id'],'recognition_status':c['recognition_status'],'pipeline_status':c['pipeline_status'],'reasons':c['review_reasons']+c.get('downstream_review_reasons',[]),'crop_images':[r['source_crop'] for r in c['regions']]} for c in decision['cases'] if c['pipeline_status']=='needs_review'],
       'boundary':'Read the identified images and this-run evidence only. No scientific acceptance or permission to alter a crystal is implied by a transcript.'})
    return state
def validate_analysis(analysis,case_id):
    analysis=safe(analysis);data=read(analysis)
    if sha(analysis)!=read(analysis.parent/'seal.json')['result_sha256']:raise ValueError('Decision record changed')
    row=next(c for c in data['cases'] if c['case_id']==case_id)
    if row['pipeline_status']!='ready_for_refinement_trial' or row['recognition_status']!='supported_transcription':raise ValueError('Case still requires review')
    for pathkey,hashkey in [('raw_predictions','raw_sha256'),('regions','regions_sha256'),('labels','labels_sha256')]:
        if sha(safe(data[pathkey]))!=data[hashkey]:raise ValueError('Bound evidence changed')
    regions=read(data['regions']);source=next(c for c in regions['cases'] if c['case_id']==case_id)
    if sha(safe(source['image']))!=source['image_sha256']:raise ValueError('Source image changed')
    for region in source['regions']:
        if sha(safe(region['image']))!=region['image_sha256']:raise ValueError('Source crop changed')
    for region in row['regions']:
        for label in region.get('accepted_label_evidence',[]):
            if sha(safe(label['crop']))!=label['crop_sha256']:raise ValueError('Label evidence crop changed')
    graph=safe(row['graph_path'])
    if sha(graph)!=row['graph_sha256']:raise ValueError('Candidate graph changed')
    coordinator=read(analysis.parent.parent/'run.json')
    if coordinator['status']!='complete':raise ValueError('Image pipeline is not complete')
    for name,digest in coordinator['script_hashes'].items():
        if sha(safe(Path(__file__).parent/name))!=digest:raise ValueError('Image pipeline code changed')
    return data,row,source,graph
def promote(analysis,case_id,output):
    analysis=safe(analysis);data,row,source,graph=validate_analysis(analysis,case_id)
    dest=safe(output)
    if dest.exists():raise ValueError('Use new promotion directory')
    dest.mkdir();(dest/'chemical_graph.json').write_bytes(graph.read_bytes())
    receipt={'schema':2,'decision':'automatically_screened_chemical_prior','reviewer':'Cairystal experimental image evidence rules v2; no human or AI image correction during this run',
      'basis':'Supported image transcription, fragment inventory, literal-label checks and four-view graph agreement. Passed current bounded prior gate; fresh crystallographic refinement and validation still mandatory.',
      'approved_graph_sha256':sha(dest/'chemical_graph.json'),'source_image':source['image'],'source_image_sha256':source['image_sha256'],
      'raw_prediction_record':data['raw_predictions'],'raw_prediction_record_sha256':data['raw_sha256'],
      'automatic_analysis':str(analysis),'automatic_analysis_sha256':sha(analysis),'case_id':case_id,'correction_file':None,'scientific_structure_acceptance':False}
    write(dest/'recognition_review.json',receipt)
    return {'graph':str(dest/'chemical_graph.json'),'receipt':str(dest/'recognition_review.json')}
if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('run');a.add_argument('--config',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('promote');a.add_argument('--analysis',required=True);a.add_argument('--case-id',required=True);a.add_argument('--output',required=True)
    a=p.parse_args();r=run(a.config,a.output) if a.cmd=='run' else promote(a.analysis,a.case_id,a.output);print(json.dumps(r,ensure_ascii=False));sys.exit(1 if r.get('status')=='failed' else 0)
