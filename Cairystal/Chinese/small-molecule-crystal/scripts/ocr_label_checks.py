"""Multiple OCR reads of bounded atomic labels; preserve pixel crops and disagreement."""
import argparse,json,re,time
from pathlib import Path
import numpy as np,cv2
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
from diagram_regions import rect,read,write,sha
def run(source,output):
    output=Path(output);assert not output.exists();output.mkdir(parents=True);(output/'labels').mkdir()
    engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2,use_cls=False);result={'source':str(source),'source_sha256':sha(source),'cases':[]};start=time.perf_counter()
    for c in read(source)['cases']:
        rgb=np.asarray(Image.open(c['image']).convert('RGB'));h,w=rgb.shape[:2];row={'case_id':c['case_id'],'image_sha256':c['image_sha256'],'labels':[]}
        texts=list(c['text'])
        # OCR sometimes separates a superscript charge from its immediately
        # preceding element. Join only that local text box, not molecular regions.
        for poly,text,score in list(texts):
            if not re.fullmatch(r'[1-9]?[+−-]',text):continue
            b=rect(poly,w,h)
            candidates=[]
            for ap,at,asc in c['text']:
                if at not in {'Cl','CI','C/','Cu','N','O','B','S'}:continue
                ab=rect(ap,w,h)
                if -.5*(ab[2]-ab[0])<=b[0]-ab[2]<=max(12,b[3]-b[1]) and b[0]>ab[0] and abs(b[1]-ab[1])<=max(ab[3]-ab[1],b[3]-b[1]):candidates.append((abs(b[0]-ab[2]),ab,at,asc))
            if len(candidates)==1:
                _,ab,at,asc=candidates[0];bb=[min(ab[0],b[0]),min(ab[1],b[1]),max(ab[2],b[2]),max(ab[3],b[3])]
                texts.append(([[bb[0],bb[1]],[bb[2],bb[1]],[bb[2],bb[3]],[bb[0],bb[3]]],at+text,min(score,asc)))
        for i,(poly,text,score) in enumerate(texts):
            if not (re.search(r'[+−-]|^H[2₂][O0]$|^[1-9][0-9]?$',text) or re.match(r'^C[luI1/]',text)):continue
            # Detection boxes can clip superscripts. Include surrounding pixels
            # before removing line fragments at the outer edge.
            box=rect(poly,w,h,6);x0,y0,x1,y1=box;patch=rgb[y0:y1,x0:x1];name=c['case_id']+'_'+str(i)+'.png';Image.fromarray(patch).save(output/'labels'/name)
            ink=(cv2.cvtColor(patch,cv2.COLOR_RGB2GRAY)<160).astype(np.uint8);n,l,stats,ct=cv2.connectedComponentsWithStats(ink,8)
            cleaned=patch.copy();removed=[]
            for ci,s in enumerate(stats[1:],1):
                x,y,bw,bh,area=map(int,s)
                if x<=1 or y<=1 or x+bw>=patch.shape[1]-1 or y+bh>=patch.shape[0]-1:
                    cleaned[l==ci]=255;removed.append(s.tolist())
            Image.fromarray(cleaned).save(output/'labels'/name.replace('.png','_clean.png'))
            reads=[]
            for mode in ['native','clean','clean_upscale','clean_binary']:
                arr=patch if mode=='native' else cleaned
                if mode in {'clean_upscale','clean_binary'}:arr=cv2.resize(arr,None,fx=3,fy=3,interpolation=cv2.INTER_CUBIC)
                if mode=='clean_binary':arr=np.where(arr<170,0,255).astype(np.uint8)
                arr=cv2.copyMakeBorder(arr,6,6,6,6,cv2.BORDER_CONSTANT,value=(255,255,255))
                value,_=engine(arr[:,:,::-1],use_det=False,use_cls=False)
                reads.append({'view':mode,'result':value})
            components=sorted([s.tolist() for s in stats[1:] if s[4]>=3],key=lambda s:s[0])
            # Pixel evidence of an l-like upright immediately following a C-sized glyph.
            upright=False
            if len(components)>=2:
                for left in components:
                  for right in components:
                    x,y,bw,bh,area=left;rx,ry,rw,rh,ra=right
                    if bw>=5 and bh>=10 and .5*bh<=rh<=1.5*bh and rw<=.28*rh and rx>=x+bw-1 and rx-(x+bw)<=max(6,bh*.45) and abs(ry-y)<=bh*.35:
                        upright=True
            row['labels'].append({'original_text':text,'original_score':score,'box':box,'crop':str(output/'labels'/name),'crop_sha256':sha(output/'labels'/name),'reads':reads,'upright_after_round_letter':upright,'components':components,'removed_border_fragments':removed})
        result['cases'].append(row)
        print(json.dumps({'case_id':c['case_id'],'labels':[(a['original_text'],a['reads'],a['upright_after_round_letter']) for a in row['labels']]},ensure_ascii=False),flush=True)
    result['wall_seconds']=time.perf_counter()-start;write(output/'result.json',result)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.source,a.output)
