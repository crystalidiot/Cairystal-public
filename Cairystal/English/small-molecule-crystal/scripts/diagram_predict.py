"""Fresh multi-view fragment predictions; image-only input, no scoring truth."""
import argparse,json,time,os,hashlib
from pathlib import Path
import numpy as np,cv2
from PIL import Image
import torch
from molscribe import MolScribe
from molscribe_local import sha,write,safe
def read(p):return json.loads(safe(p).read_text(encoding='utf-8-sig'))
def main():
    p=argparse.ArgumentParser();p.add_argument('--regions',required=True);p.add_argument('--crop-ocr',required=True);p.add_argument('--checkpoint',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    out=safe(a.output);assert not out.exists();out.mkdir();start=time.perf_counter()
    assert sha(a.checkpoint)=='6f0df56fa32b5ffc21f8c7f311ef333da522f590bf5622e966c6bcb1f2d9ea1d'
    spec=read(a.regions);ocr={c['case_id']:c for c in read(a.crop_ocr)['cases']};torch.set_num_threads(4)
    assert torch.cuda.is_available();load=time.perf_counter();model=MolScribe(a.checkpoint,device=torch.device('cuda'),num_workers=1);torch.cuda.synchronize()
    result={'source_regions':a.regions,'regions_sha256':sha(a.regions),'checkpoint_sha256':sha(a.checkpoint),'model_load_seconds':time.perf_counter()-load,'external_LLM_calls':0,'cases':[],'view_policy':['native','2x_cubic','threshold160','threshold210']}
    for c in spec['cases']:
        case_start=time.perf_counter();row={'case_id':c['case_id'],'image_sha256':c['image_sha256'],'regions':[]}
        assert sha(c['image'])==c['image_sha256']
        for region in c['regions']:
            assert sha(region['image'])==region['image_sha256'];key=c['case_id']+region['region_id'];rr={'region_id':region['region_id'],'image_sha256':region['image_sha256']}
            texts=ocr[key]['text'];numbers=[t for _,t,s in texts if t.isdigit() and s>.95]
            if len(texts)==1 and len(numbers)==1:
                rr.update(role='standalone_numeric_annotation',value=int(numbers[0]),views=[]);row['regions'].append(rr);continue
            im=np.asarray(Image.open(region['image']).convert('RGB'));views=[im,cv2.resize(im,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC),np.where(im<160,0,255).astype(np.uint8),np.where(im<210,0,255).astype(np.uint8)]
            t=time.perf_counter();preds=model.predict_images(views,return_atoms_bonds=True,return_confidence=True,batch_size=4);torch.cuda.synchronize()
            rr['seconds']=time.perf_counter()-t;rr['views']=[]
            for name,v,pred in zip(result['view_policy'],views,preds):
                yy,xx=np.nonzero(np.any(v!=255,axis=2));box=[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)]
                rr['views'].append({'view':name,'scale':2 if name=='2x_cubic' else 1,'tight_box':box,'prediction':pred})
            row['regions'].append(rr)
        row['seconds']=time.perf_counter()-case_start;result['cases'].append(row);write(out/'raw_predictions.json',result)
        print(json.dumps({'case_id':c['case_id'],'fragments':len(row['regions']),'seconds':round(row['seconds'],2)},ensure_ascii=False),flush=True)
    result['wall_seconds']=time.perf_counter()-start;result['peak_gpu_MiB']=torch.cuda.max_memory_allocated()/1024**2;write(out/'raw_predictions.json',result);write(out/'seal.json',{'raw_predictions_sha256':sha(out/'raw_predictions.json'),'reference_answers_read':False})
if __name__=='__main__':main()
