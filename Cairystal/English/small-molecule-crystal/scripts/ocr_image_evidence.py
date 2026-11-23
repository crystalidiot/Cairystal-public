"""Local OCR of source pixels; no chemical reference/identity lookup."""
import argparse,json,time,hashlib
from pathlib import Path
import cv2,numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(manifests,output):
    output=Path(output);assert not output.exists();output.mkdir(parents=True)
    start=time.perf_counter();engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2,use_cls=False)
    result={'engine':'rapidocr-onnxruntime 1.4.4','external_LLM_calls':0,'cases':[]}
    for mf in manifests:
        spec=json.loads(Path(mf).read_text(encoding='utf-8-sig'))
        for c in spec['cases']:
            assert sha(c['image'])==c['image_sha256'];image=np.array(Image.open(c['image']).convert('RGB'))[:,:,::-1]
            t=time.perf_counter();pred,_=engine(image,use_cls=False)
            row={'case_id':c['case_id'],'image':c['image'],'image_sha256':c['image_sha256'],'text':pred or [],'seconds':time.perf_counter()-t}
            result['cases'].append(row);print(json.dumps({'id':c['case_id'],'text':[x[1:] for x in row['text']]},ensure_ascii=False),flush=True)
            (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    result['wall_seconds']=time.perf_counter()-start
    (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'seal.json').write_text(json.dumps({'result_sha256':sha(output/'result.json')}),encoding='utf-8')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',action='append',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.manifest,a.output)
