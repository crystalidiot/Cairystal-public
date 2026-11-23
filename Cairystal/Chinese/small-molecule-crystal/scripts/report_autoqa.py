"""Measured PDF/DOCX layout and delivery checks. Not a visual-inspection claim."""
import json,re,unicodedata,time
from bisect import bisect_left,bisect_right
from pathlib import Path
from collections import Counter,defaultdict
from crystal_runtime import sha,write_json,utc_now,check_stem

def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKC',text).replace('\u00ad','') if not c.isspace())

def supported_script_overhang(a,b):
    """Unicode raised digits and low punctuation can overlap font advance boxes.

    Accept only separated origins and limited overlap; coincident/large overlap
    still fails. This is a typography rule, not a claim about arbitrary ink.
    """
    aw=a['x1']-a['x0'];bw=b['x1']-b['x0'];overlap=min(a['x1'],b['x1'])-max(a['x0'],b['x0'])
    return a['text'] in '⁰¹²³⁴⁵⁶⁷⁸⁹' and b['text'] in '.,;:' and min(aw,bw)>0 and b['x0']-a['x0']>=.5*aw and overlap<=.75*min(aw,bw)

def check_chars(chars,width,height):
    issues=[];groups=defaultdict(list)
    for c in chars:
        if not c.get('text','').strip():continue
        if c['x0']<1 or c['x1']>width-1 or c['top']<1 or c['bottom']>height-1:issues.append({'kind':'page_edge_overflow','text':c['text']})
        if '\ufffd' in c['text'] or '(cid:' in c['text']:issues.append({'kind':'unmapped_glyph','text':c['text']})
        groups[round(c['bottom']/2)].append(c)
    for group in groups.values():
        group.sort(key=lambda c:c['x0'])
        for a,b in zip(group,group[1:]):
            overlap=min(a['x1'],b['x1'])-max(a['x0'],b['x0']);minimum=min(a['x1']-a['x0'],b['x1']-b['x0'])
            if minimum>0 and overlap>.6*minimum and abs(a['top']-b['top'])<2 and not supported_script_overhang(a,b):issues.append({'kind':'major_text_overlap','text':a['text']+b['text'],'boxes':[[c['x0'],c['top'],c['x1'],c['bottom']] for c in (a,b)]})
    return issues

def source_text(docx):
    from zipfile import ZipFile
    from xml.etree import ElementTree as E
    with ZipFile(docx) as z:root=E.fromstring(z.read('word/document.xml'))
    return ''.join(x.text or '' for x in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))

def body_margins(docx):
    """Conservative common body area from section margins (DOCX twips -> points)."""
    from zipfile import ZipFile
    from xml.etree import ElementTree as E
    ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    with ZipFile(docx) as z:root=E.fromstring(z.read('word/document.xml'))
    margins=list(root.iter(ns+'pgMar'))
    if not margins:return 0.,0.
    # Minimum margin across sections avoids excluding real text in a wider section.
    return tuple(min(float(m.get(ns+side,'0'))/20 for m in margins) for side in ('top','bottom'))

def body_content(page,margins):
    top,bottom=margins;end=page.height-bottom
    def inside(item):return item['bottom']>top+1 and item['top']<end-1
    chars=[c for c in page.chars if c.get('text','').strip() and inside(c)]
    images=[im for im in page.images if inside(im)]
    # A vector-only structure diagram is content too; table rules are not figures.
    curves=[c for c in getattr(page,'curves',[]) if inside(c)]
    return {'body_characters':len(chars),'body_images':len(images),'body_curves':len(curves)}

def border_crossings(chars,edges):
    """Same strict geometry predicate, with a sorted x-coordinate broad phase.

    The index is page-local. No rounding, sampling, deduplication or changed
    tolerance: keep character order and at most one finding per character.
    """
    vertical=sorted((e for e in edges if e.get('orientation')=='v' and e['bottom']-e['top']>8),key=lambda e:e['x0'])
    xs=[e['x0'] for e in vertical];issues=[]
    for c in chars:
        if not c['text'].strip():continue
        left=bisect_right(xs,c['x0']+1.5)
        right=bisect_left(xs,c['x1']-1.5)
        if any(c['x0']+1.5<e['x0']<c['x1']-1.5 and e['top']+1<c['top'] and e['bottom']-1>c['bottom'] for e in vertical[left:right]):
            issues.append({'kind':'table_border_crosses_text','text':c['text']})
    return issues

def check_document(docx,pdf,page_images):
    import pdfplumber
    expected=Counter(normalize(source_text(docx)));texts=[];pages=[];margins=body_margins(docx)
    with pdfplumber.open(pdf) as doc:
        for i,p in enumerate(doc.pages,1):
            text=p.extract_text() or '';texts.append(text);issues=check_chars(p.chars,p.width,p.height)
            content=body_content(p,margins)
            if not any(content.values()):issues.append({'kind':'empty_body_page','note':'Header/footer/page number does not count as report content'})
            for im in p.images:
                if im['x0']<0 or im['x1']>p.width+1 or im['top']<0 or im['bottom']>p.height+1:issues.append({'kind':'image_outside_page'})
            # Edges are rendered table boundaries; a glyph must not be cut by an interior vertical border.
            issues.extend(border_crossings(p.chars,p.edges))
            pages.append({'number':i,'issues':issues,**content,'characters':len(p.chars),'image_count':len(p.images),'preview':page_images[i-1]['path'] if i<=len(page_images) else None})
            # Retain the audit, not a full PDF layout object for every page.
            p.close()
    missing=expected-Counter(normalize(''.join(texts)))
    global_issues=[]
    if missing:global_issues.append({'kind':'source_text_missing_after_render','characters':dict(missing)})
    if len(pages)!=len(page_images):global_issues.append({'kind':'page_count_mismatch'})
    return {'pages':pages,'global_issues':global_issues,'docx_sha256':sha(docx),'pdf_sha256':sha(pdf),'status':'needs_review' if global_issues or any(p['issues'] for p in pages) else 'automatic_checks_passed'}

def run(delivery_root,output):
    started=time.perf_counter();document_timings={}
    root=Path(delivery_root);read=lambda p:json.loads(Path(p).read_text('utf-8-sig'));record=read(root/'result.json');manifest=read(root/'qa/render_manifest.json');build=read(root/'qa/report_build.json')
    findings=[];results={}
    if not build.get('same_numeric_tables'):findings.append('Bilingual numerical table equality missing')
    for job in manifest['jobs']:
        for p in job['pages']:
            if sha(p['path'])!=p['sha256']:findings.append('Rendered page hash changed')
        if sha(job['pdf'])!=job['pdf_sha256']:findings.append('Rendered PDF hash changed')
        t=time.perf_counter()
        results[job['language']]=check_document(job['docx'],job['pdf'],job['pages'])
        document_timings[job['language']]=round(time.perf_counter()-t,6)
    if set(results)!={'zh','en'}:findings.append('Both languages required')
    from iucr_validation import parse_official_text
    from pypdf import PdfReader
    official_pdf=root/'delivery/IUCr_checkCIF.pdf'
    parsed=parse_official_text('\n'.join(p.extract_text() or '' for p in PdfReader(official_pdf).pages))
    if parsed['counts']!=record['official']['counts']:findings.append('Official alert counts differ')
    if parsed['counts']['A'] or parsed['counts']['B']:findings.append('Official A/B requires scientific review')
    stem=check_stem(record.get('stem','model'))
    if sha(root/'frozen'/f'{stem}.cif')!=record['official']['cif_sha256']:findings.append('Official result is not for the frozen CIF')
    for name,digest in record['delivery_seal'].items():
        if sha(root/'delivery'/name)!=digest:findings.append('Delivery changed: '+name)
    result={'status':'needs_review' if findings or any(r['status']!='automatic_checks_passed' for r in results.values()) else 'automatic_checks_passed','at':utc_now(),'findings':findings,'documents':results,'official_counts':parsed['counts'],'delivery_hashes':record['delivery_seal'],'render_manifest_sha256':sha(root/'qa/render_manifest.json'),'visual_review_performed':False,'AI_calls':0,'scope':'PDF glyph/page/image/table-edge geometry; DOCX source-character preservation; paired bilingual numerical tables; fresh official PDF structure-factor confirmation and A/B counts. This does not assess aesthetics, semantic correctness of figure labels or scientific identity.'}
    result.update(rule_version='20261106-02',implementation_sha256=sha(__file__),elapsed_s=round(time.perf_counter()-started,6),document_timings_s=document_timings,geometry_index='exact_x_range_v1')
    write_json(output,result);return result

def main():
    import argparse
    from pipeline_intake import unlinked
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,help='Existing delivery run with frozen CIF, official PDF and rendered bilingual Word')
    parser.add_argument('--output',required=True,help='New JSON audit path; source reports remain read-only')
    args=parser.parse_args()
    try:
        output=unlinked(args.output)
        if output.exists():raise ValueError('QA output already exists; preserve previous evidence')
        result=run(unlinked(args.run),output)
        print(json.dumps({'status':result['status'],'findings':result['findings'],'audit':str(output)},ensure_ascii=False))
        return 0 if result['status']=='automatic_checks_passed' else 2
    except (ValueError,OSError,KeyError) as exc:
        print(json.dumps({'status':'failed','reason':str(exc)},ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
