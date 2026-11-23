"""Presentation-only scientific notation. Never change CIF, atom labels or values."""
import re
from pathlib import Path
import json

RULE_VERSION='2026-10-30.1'
TOKEN=re.compile(r'(?<![A-Za-z0-9_])(?:wR2|R1|R int|Rint|Ueq|Uiso|Uani|Uij|U11|U22|U33|U23|U13|U12|F000)(?![A-Za-z0-9_])|[αβγθλμρ]')

def contact():
    data=json.loads((Path(__file__).resolve().parent.parent/'assets/support_contact.json').read_text(encoding='utf-8'))
    return {k:str(data.get(k,'')).strip() for k in ['name','email','wechat']}

def contact_text(zh=True):
    c=contact()
    return ('联系与问题反馈：邮箱 ' if zh else 'Contact and feedback: email ')+c['email']+('；微信 ' if zh else '; WeChat ')+c['wechat']

def piece(p,text,italic=False,sub=False,sup=False):
    r=p.add_run(text);r.italic=italic;r.font.subscript=sub;r.font.superscript=sup
    return r

def notation(p,token):
    if token=='F000':piece(p,'F',True);piece(p,'(000)')
    elif token.startswith('U'):
        piece(p,'U',True);piece(p,token[1:],italic=token[1:]=='ij',sub=True)
    elif token in {'R int','Rint'}:piece(p,'R',True);piece(p,'int',sub=True)
    elif token in {'R1','wR2'}:piece(p,token[:-1],True);piece(p,token[-1],sub=True)
    else:piece(p,token,True)

def scientific(p,text,label=False):
    """Context-aware tokenization: labels can have scalar letters; prose cannot."""
    pattern=TOKEN
    if label:
        pattern=re.compile(TOKEN.pattern+r'|(?<![A-Za-z0-9_])[abcxyzVZ](?![A-Za-z0-9_])')
    cursor=0
    for m in pattern.finditer(text):
        piece(p,text[cursor:m.start()]);notation(p,m.group());cursor=m.end()
    piece(p,text[cursor:])
    if label:
        # min/max are descriptive indices; leave the wording intact and upright.
        pass

def formula(p,text):
    """Only subscripts unambiguous element counts; never infer charge or identity."""
    cursor=0
    for m in re.finditer(r'([A-Z][a-z]?)(\d+(?:\.\d+)?)',text):
        piece(p,text[cursor:m.start()]);piece(p,m[1]);piece(p,m[2],sub=True);cursor=m.end()
    piece(p,text[cursor:])

def space_group(p,text):
    # Gemmi validates notation; we retain setting, case, spacing and digits.
    import gemmi
    if gemmi.find_spacegroup_by_name(text) is None:
        piece(p,text);return False
    i=0
    while i<len(text):
        ch=text[i]
        if ch=='-' and i+1<len(text) and text[i+1] in '1346':
            piece(p,text[i+1]+'\u0305');i+=2;continue
        if ch in '2346' and i+1<len(text):
            j=i+1
            if text[j]=='_':j+=1
            if j<len(text) and text[j].isdigit() and 0<int(text[j])<int(ch):
                piece(p,ch);piece(p,text[j],sub=True);i=j+1;continue
        piece(p,ch,italic=ch.isalpha());i+=1
    return True

def apply(doc):
    """Format table labels by role; all atom/coordinate/tensor rows stay untouched."""
    counts={'rule_version':RULE_VERSION,'formatted_labels':0,'space_group_supported':None,'formula_formatted':False}
    def rewrite(p,fn):
        old=p.runs[0] if p.runs else None
        size=old.font.size if old else None;bold=old.bold if old else None
        p.clear();result=fn()
        for r in p.runs:r.font.size=size;r.bold=bold
        return result
    for para in doc.paragraphs:
        if para.style.name.startswith(('Title','Heading')):continue
        text=para.text
        if TOKEN.search(text):rewrite(para,lambda:scientific(para,text))
    for ti,t in enumerate(doc.tables):
        for cell in t.rows[0].cells:
            p=cell.paragraphs[0];text=p.text;rewrite(p,lambda:scientific(p,text,label=True))
        if ti!=0:continue
        for row in t.rows[1:]:
            label=row.cells[0].text;value=row.cells[1].text
            p=row.cells[0].paragraphs[0];rewrite(p,lambda:scientific(p,label,label=True));counts['formatted_labels']+=1
            p=row.cells[1].paragraphs[0]
            if label in {'化学式','Chemical formula','当前模型计数式','Current model atom-count formula'}:
                rewrite(p,lambda:formula(p,value));counts['formula_formatted']=True
            elif label in {'空间群','Space group'}:
                counts['space_group_supported']=rewrite(p,lambda:space_group(p,value))
    return counts
