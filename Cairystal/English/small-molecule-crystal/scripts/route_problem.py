"""Retrieve evidence-based problem routes; does not execute repair or upload."""
import argparse
import json
from pathlib import Path
import re
import sys
from toolbox import ROOT, load_catalog

from checkcif_identifiers import ALERT_TOKEN, test_code


def pasted_alerts(text):
    """Keep distinct full alert IDs in report order; leave prose and totals alone."""
    alerts = {}
    matches=list(ALERT_TOKEN.finditer(text))
    for index,match in enumerate(matches):
        token = match.group().upper()
        item=alerts.setdefault(token,{'id':token,'test':normalize_alert(token),'level':match[3].upper(),'occurrences':[]})
        end=matches[index+1].start() if index+1<len(matches) else len(text)
        tail=text[match.end():end].splitlines()
        item['occurrences'].append(tail[0].strip() if tail else '')
    if not alerts:
        raise ValueError('Paste full checkCIF alert IDs such as PLAT306_ALERT_2_B, or use --alerts PLAT306.')
    return list(alerts.values())


def normalize_alert(value):
    value=str(value).upper().strip()
    token=ALERT_TOKEN.fullmatch(value)
    if token:
        return test_code(token[1])
    value=re.sub(r'_ALERT_\d_[ABCG]$', '', value)
    match=re.fullmatch(r'(?:PLAT)?(\d{3})',value)
    if match:return match[1]
    match=re.fullmatch(r'([A-Z]{3,10})_?(\d{2,3})',value)
    if match:return match[1]+match[2]
    raise ValueError('Use PLAT242, 242_ALERT_2_B, SHFSU01 or a named checkCIF test: '+str(value))

def select_routes(data, alerts=(), query='', review=None, list_all=False):
    codes = {normalize_alert(v) for v in alerts}
    route_ids = {x.get('route') for x in (review or {}).get('findings', []) if x.get('route')}
    if review is not None and review.get('stage') != '02_post_solution':
        raise ValueError('Expected an initial-review packet, not an arbitrary report.')
    matched = []
    for route in data['branches']:
        search_text = ' '.join(str(route.get(k, '')) for k in ['id', 'title', 'trigger', 'actions', 'keywords'])
        if list_all or codes.intersection(route.get('alerts', [])) or route['id'] in route_ids or (query and query.casefold() in search_text.casefold()):
            matched.append(route)
    covered = set().union(*(set(r.get('alerts', [])) for r in matched)) if matched else set()
    unknown = sorted(codes - covered)
    return {'schema': 1, 'status': 'routes_found' if matched else 'needs_review_no_matching_route',
            'routes': matched, 'unmapped_alerts': unknown,
            'documented_alerts': [{'code':c,'source_pages':data['reference_pages'][c], 'official_url':('https://journals.iucr.org/services/cif/checking/PLAT'+c+'.html') if c.isdigit() else None, 'scope':'Reference index only; no automatic repair or source text copied.'} for c in sorted(codes) if c in data.get('reference_pages',{})],
            'criteria': {'alerts': sorted(codes), 'query': query, 'initial_review_routes': sorted(route_ids)},
            'automatic_repairs_performed': False, 'scientific_acceptance': False,
            'note': 'Routes guide diagnosis; a matching alert does not establish its cause. Missing routes go to review, not arbitrary model edits.'}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--alerts', nargs='*', default=[])
    p.add_argument('--alert-text', help='Paste checkCIF lines, or pass - to read pasted text from stdin')
    p.add_argument('--query', default='')
    p.add_argument('--initial-review', type=Path)
    p.add_argument('--list', action='store_true')
    p.add_argument('--json', action='store_true')
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if not (a.alerts or a.alert_text is not None or a.query or a.initial_review or a.list):
        p.error('Provide --alerts, --query, --initial-review or --list.')
    try:
        pasted = pasted_alerts(sys.stdin.read() if a.alert_text == '-' else a.alert_text) if a.alert_text is not None else []
    except ValueError as exc:
        if a.json:
            print(json.dumps({'status':'invalid_alert_text','error':str(exc)}),file=sys.stderr)
            return 2
        p.error(str(exc))
    data = json.loads((ROOT / 'assets/console/workflow-data.json').read_text('utf-8'))
    packet = json.loads(a.initial_review.read_text('utf-8-sig')) if a.initial_review else None
    result = select_routes(data, [*a.alerts, *(item['id'] for item in pasted)], a.query, packet, a.list)
    if pasted:
        result['pasted_alerts'] = pasted
    catalog = load_catalog()
    result['release'] = catalog['release']
    tools = {t['id']: t for t in catalog['tools']}
    for route in result['routes']:
        route['tool_examples'] = [{'id': name, 'example': 'python -B cairystal.py run ' + name + ' -- ' + tools[name]['example']} for name in route['tools']]
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        with a.output.open('x', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write('\n')
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if pasted:
            for item in pasted:
                for description in item['occurrences']:
                    print(item['id']+'  '+description)
        for route in result['routes']:
            print('\n' + route['id'] + ' — ' + route['title'])
            print('触发：' + route['trigger'])
            print('能力：' + route['availability'])
            for i, action in enumerate(route['actions'], 1):
                print(str(i) + '. ' + action)
            print('验收：' + route['validation'])
            print('↶ ' + route['return_label'])
            print('边界：' + route['stop'])
            print('工具：' + ', '.join(route['tools']))
        if result['unmapped_alerts']:
            print('尚无对应路线，转人工复核：' + ', '.join(result['unmapped_alerts']))
        for ref in result['documented_alerts']:
            print('原资料索引 '+('PLAT' if ref['code'].isdigit() else '')+ref['code']+'，页码 '+','.join(map(str,ref['source_pages']))+('；官方解释：'+ref['official_url'] if ref['official_url'] else '；官方链接未核实'))
        print('\n仅检索处理路线；未运行修复、未修改原子、未上传数据。')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
