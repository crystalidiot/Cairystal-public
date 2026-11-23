"""Audited pixel segmentation, captions and small disconnected labels are retained."""
import argparse,json,re,hashlib,time
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def rect(points,w,h,pad=0):
    a=np.asarray(points);return [max(0,int(a[:,0].min())-pad),max(0,int(a[:,1].min())-pad),min(w,int(a[:,0].max())+1+pad),min(h,int(a[:,1].max())+1+pad)]
def caption(text):
    if 'formula' in text.lower():return True
    if re.search('[a-z]{4,}',text):return True
    if re.fullmatch(r'\([A-Za-z0-9\-,]+\)',text):return True
    return False
def water_text(text):return re.sub(r'\s+','',text).replace('₂','2') in {'H2O','H20','OH2','0H2'}
def segment(image,texts):
    clean=image.copy();h,w=clean.shape[:2];removed=[];water=[]
    _,source_components,source_stats,_=cv2.connectedComponentsWithStats((cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)<210).astype(np.uint8),8)
    for poly,text,confidence in texts:
        box=rect(poly,w,h,1);x0,y0,x1,y1=box
        if caption(text) and confidence>=.8:
            removed.append({'box':box,'text':text,'confidence':confidence,'reason':'Caption text retained as metadata; never used to identify a structure'});clean[y0:y1,x0:x1]=255
        elif water_text(text) and confidence>=.9:
            # Explicit label is detached into its own crop; it is NOT silently turned into O.
            ids=np.unique(source_components[y0:y1,x0:x1]);detached=True
            for cid in ids:
                if cid==0:continue
                sx,sy,sw,sh,_=source_stats[cid]
                if sx<x0 or sy<y0 or sx+sw>x1 or sy+sh>y1:detached=False
            if detached:
                water.append({'box':box,'text':text,'confidence':confidence,'role':'explicit_water_label','source_detached':True});clean[y0:y1,x0:x1]=255
    grey=cv2.cvtColor(clean,cv2.COLOR_RGB2GRAY);ink=(grey<210).astype(np.uint8)
    n,labels,stats,cents=cv2.connectedComponentsWithStats(ink,8)
    heights=[s[3] for s in stats[1:] if s[4]>=5 and 4<=s[3]<=max(12,h*.13) and s[2]>=2]
    text_h=float(np.median(heights)) if heights else 12
    kernel=max(5,min(25,int(text_h*.7)//2*2+1))
    joined=cv2.dilate(ink,np.ones((kernel,kernel),np.uint8))
    n,labs,stats,cents=cv2.connectedComponentsWithStats(joined,8);regions=[]
    for i,s in enumerate(stats[1:],1):
        yy,xx=np.nonzero((labs==i)&(ink>0))
        if len(xx)<3:continue
        box=[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)]
        region={'box':box,'ink_pixels':len(xx),'role':'unclassified_fragment'}
        regions.append(region)
    # A detached letter can lie inside its molecule's rectangular crop. Merge
    # overlapping boxes before prediction, otherwise that atom would be duplicated.
    changed=True
    while changed:
        changed=False
        for i in range(len(regions)):
            for j in range(i+1,len(regions)):
                a=regions[i]['box'];b=regions[j]['box']
                if min(a[2],b[2])>max(a[0],b[0]) and min(a[3],b[3])>max(a[1],b[1]):
                    regions[i]['box']=[min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3])]
                    regions[i]['ink_pixels']+=regions[j]['ink_pixels'];regions.pop(j);changed=True;break
            if changed:break
    regions.extend(water);regions.sort(key=lambda b:(b['box'][1]//max(25,int(text_h*3)),b['box'][0]))
    return clean,regions,removed,{'kernel':kernel,'estimated_text_height':text_h,'foreground_pixels':int(ink.sum()),'layout':'multi_panel' if len(removed)>=3 else 'single_diagram_or_composition'}

def run(manifests,ocr,output):
    output=Path(output);assert not output.exists();output.mkdir(parents=True);(output/'crops').mkdir();(output/'overlays').mkdir()
    evidence=read(ocr);lookup={c['case_id']:c for c in evidence['cases']};result={'cases':[],'source_ocr':str(ocr),'source_ocr_sha256':sha(ocr),'algorithm':'caption/explicit-label inventory and connected ink grouping; all fragments retained'}
    for mf in manifests:
        for c in read(mf)['cases']:
            assert sha(c['image'])==c['image_sha256'];o=lookup[c['case_id']];assert o['image_sha256']==c['image_sha256']
            image=np.asarray(Image.open(c['image']).convert('RGB'));clean,regions,removed,meta=segment(image,o['text'])
            overlay=Image.fromarray(image);draw=ImageDraw.Draw(overlay);row={**c,'regions':[],'captions':removed,'segmentation':meta}
            for i,region in enumerate(regions,1):
                box=region['box'];x0,y0,x1,y1=box
                # Region pixels retained exactly, with white padding added around derived crop.
                source=image if region['role']=='explicit_water_label' else clean
                crop=Image.fromarray(source[y0:y1,x0:x1]);padded=Image.new('RGB',(crop.width+24,crop.height+24),'white');padded.paste(crop,(12,12))
                path=output/'crops'/f'{c["case_id"]}_r{i:02d}.png';padded.save(path)
                row['regions'].append({**region,'region_id':f'r{i:02d}','image':str(path),'image_sha256':sha(path),'source_crop_padding':12})
                draw.rectangle(box,outline='red',width=2);draw.text((x0,max(0,y0-13)),f'{i}',fill='blue')
            for b in removed:draw.rectangle(b['box'],outline='green',width=1)
            overlay.save(output/'overlays'/f'{c["case_id"]}.png');result['cases'].append(row)
            print(json.dumps({'case':c['case_id'],'fragments':len(regions),'captions':len(removed),'kernel':meta['kernel']},ensure_ascii=False),flush=True)
    write(output/'regions.json',result)
    # OCR every derived fragment; no chemical answers are passed.
    crop_manifest={'schema':1,'cases':[{'case_id':c['case_id']+r['region_id'],'image':r['image'],'image_sha256':r['image_sha256'],'elements':c['elements']} for c in result['cases'] for r in c['regions']]}
    write(output/'crop_ocr_manifest.json',crop_manifest)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',action='append',required=True);p.add_argument('--ocr',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.manifest,a.ocr,a.output)
