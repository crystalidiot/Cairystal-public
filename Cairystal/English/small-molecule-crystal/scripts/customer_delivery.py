"""Publish verified deliverables to the specimen folder without changing model bytes."""
import argparse,json,shutil,sys,uuid
from datetime import datetime
from pathlib import Path
from crystal_runtime import sha,write_json,utc_now,check_stem
from pipeline_intake import unlinked

def checked_directory(path):
    p=unlinked(path)
    if not p.is_dir():raise ValueError('Data directory does not exist: '+str(p))
    return p

def publish(run,data_dir):
    root=checked_directory(run);data=checked_directory(data_dir);source=unlinked(root/'delivery')
    if data==root or root in data.parents or data==source or source in data.parents:
        raise ValueError('Customer data directory must not be inside the delivery work directory')
    record=json.loads((root/'result.json').read_text('utf-8-sig'))
    if record.get('status') not in {'delivery_complete_needs_scientific_review','customer_export_failed'}:
        raise ValueError('Finalize and review the delivery before customer export')
    from delivery_contract import require
    stem=check_stem(record.get('stem','model'));require(root,stem)
    sealed=record.get('delivery_seal') or {}
    required=[f'{stem}.cif','IUCr_checkCIF.pdf','晶体学报表_中文.docx','Crystallographic_Report_EN.docx']
    if any(n not in sealed for n in required):raise ValueError('Required final files are not sealed')
    hashes={}
    for name,digest in sealed.items():
        if Path(name).name!=name or name in {'.','..'}:raise ValueError('Invalid sealed filename')
        p=unlinked(source/name)
        if not p.is_file() or sha(p)!=digest:raise ValueError('Sealed delivery changed: '+name)
        hashes[name]=digest
    sums=unlinked(source/'SHA256SUMS.json')
    if json.loads(sums.read_text('utf-8'))!=sealed:raise ValueError('Delivery checksum manifest differs')
    hashes[sums.name]=sha(sums)
    receipt_path=root/'customer_delivery.json'
    def completed(info):
        record.update(status='delivery_complete_needs_scientific_review',customer_delivery=info,customer_notice=info['notice'])
        record.pop('customer_export_error',None)
        write_json(root/'result.json',record)
        return info
    if receipt_path.exists():
        old=json.loads(receipt_path.read_text('utf-8'))
        if old.get('status')=='exported':
            if old['data_directory']!=str(data) or old['source_hashes']!=hashes:raise ValueError('Existing export belongs to a different destination or file set')
            target=checked_directory(old['directory'])
            for n,h in old['exported_hashes'].items():
                if sha(unlinked(target/n))!=h:raise ValueError('Existing customer copy changed: '+n)
            return completed(old)
    base=unlinked(data/'Cairystal')
    if base.exists() and not base.is_dir():raise ValueError('Cairystal exists but is not a directory')
    suffix=datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
    target=base/('运行_'+suffix) if base.exists() else base
    pending=unlinked(data/('.Cairystal_pending_'+suffix));pending.mkdir()
    info={'schema':1,'status':'copying','created_at':utc_now(),'data_directory':str(data),'directory':str(target),
          'source_run':str(root),'source_directory':str(source),'source_hashes':hashes,
          'scientific_acceptance':record.get('scientific_acceptance','not_established'),
          'official_counts':record.get('official',{}).get('counts'),'AB_alerts':record.get('AB_alerts',[])}
    write_json(root/'customer_delivery_attempt.json',info)
    try:
        for name,digest in hashes.items():
            shutil.copy2(source/name,pending/name)
            if sha(pending/name)!=digest or sha(source/name)!=digest:raise ValueError('Copy hash mismatch: '+name)
        info['files']={key:str(target/name) for key,name in zip(['final_cif','official_checkcif_pdf','word_zh','word_en'],required)}
        info['notice']='最终 CIF、IUCr 官网 checkCIF PDF 和中英文 Word 晶体学表已保存至：'+str(target)+'。'
        if info['AB_alerts']:info['notice']+=' 仍有 A/B 警告，具体内容请查看官网报告。'
        info.update(status='exported',finished_at=utc_now())
        write_json(pending/'Cairystal_delivery.json',info)
        (pending/'交付说明.txt').write_text(info['notice']+'\n\n文件：\n'+'\n'.join(required)+'\n\n成品与已验证版本逐字节一致。文件齐全不等于结构已经科学确证。\n完整运行和审计记录：'+str(root)+'\n',encoding='utf-8')
        info['exported_hashes']={p.name:sha(p) for p in pending.iterdir() if p.is_file()}
        unlinked(target)
        if target.exists():raise ValueError('Destination appeared during export; retained pending copy, no overwrite')
        pending.rename(target)
        write_json(receipt_path,info)
        return completed(info)
    except Exception as exc:
        write_json(root/'customer_delivery_attempt.json',dict(info,status='failed',error=str(exc),retained_pending=str(pending)))
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);p.add_argument('--data-dir',required=True);a=p.parse_args()
    try:r=publish(a.run,a.data_dir);print(json.dumps(r,ensure_ascii=False));return 0
    except Exception as exc:print(json.dumps({'status':'export_failed','error':str(exc)},ensure_ascii=False));return 2

if __name__=='__main__':sys.exit(main())
