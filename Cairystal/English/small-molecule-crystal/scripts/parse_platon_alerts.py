"""Read-only PLATON .chk parser; missing levels are zero, *** is overflow."""
import argparse,json,re
from pathlib import Path

def parse(text):
    alerts=[{'code':m[1],'type':int(m[2]),'level':m[3],'text':m[4].strip()}
        for m in re.finditer(r'^\s*(\d+)_ALERT_(\d)_([ABCG])\s+(.*)$',text,re.M)]
    summary={m[2]:m[1] for m in re.finditer(r'^\s*(\d+|\*{3})\s+ALERT_Level_([ABCG])\s*=',text,re.M)}
    counts={level:sum(a['level']==level for a in alerts) for level in 'ABCG'}
    warnings=[]
    for level,value in summary.items():
        if value!='***' and int(value)!=counts[level]:warnings.append(f'Level {level}: summary and parsed alert count disagree')
        if value=='***' and counts[level]<1000:warnings.append(f'Level {level}: overflow summary but fewer than 1000 alert lines parsed')
    return {'counts':counts,'alerts':alerts,'printed_summary':summary,
        'report_footer_present':'ALERT_Level and ALERT_Type Summary' in text,
        'warnings':warnings,'official_iucr_report':False,
        'limitation':'This parses local alert text, not execution completion or scientific acceptance.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('chk',type=Path);a=p.parse_args()
    print(json.dumps(parse(a.chk.read_text(encoding='latin1')),ensure_ascii=False,indent=2))
