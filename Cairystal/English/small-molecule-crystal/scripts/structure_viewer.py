"""Offline, read-only crystal viewer; visual assembly is not structure refinement."""
from __future__ import annotations
import argparse
import collections
import hashlib
import html
import itertools
import json
import math
import os
from pathlib import Path
import re
import webbrowser
import gemmi
from crystal_runtime import cif_tolerance
from structure_diagnostics import res_records

COLOURS = {'H':'#f4f6fa','C':'#536579','N':'#367bea','O':'#e74c56','F':'#74c943',
           'Cl':'#30ad5e','Br':'#a95536','I':'#8d59b5','S':'#e9bc28','P':'#ed8c30',
           'B':'#dc8a7b','Si':'#b39b7b','Bi':'#a55aa7','Rb':'#9064bf','In':'#9277af'}
UNKNOWN = {None, '', '.', '?'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def val(token):
    n = gemmi.cif.as_number(token or '?')
    if not math.isfinite(n):
        raise ValueError('缺失或非有限数值：' + str(token))
    return n


def plain(token):
    return gemmi.cif.as_string(token) if token else None


def cart(cell, frac):
    p = cell.orthogonalize(gemmi.Fractional(*frac))
    return [p.x, p.y, p.z]


def distance(a, b):
    return math.sqrt(sum((a[i]-b[i])**2 for i in range(3)))


def parse_model(cif, res=None):
    doc = gemmi.cif.read_file(str(cif))
    blocks = [b for b in doc if b.find_value('_cell_length_a') and b.find_values('_atom_site_label')]
    if len(blocks) != 1:
        raise ValueError('查看器需要唯一的结构数据块。')
    b = blocks[0]
    cell_tags = ['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']
    cell_values = [val(b.find_value('_cell_'+k)) for k in cell_tags]
    cell = gemmi.UnitCell(*cell_values)
    if cell.volume <= 0 or not math.isfinite(cell.volume):
        raise ValueError('无效晶胞。')
    operations = list(b.find_values('_space_group_symop_operation_xyz')) or list(b.find_values('_symmetry_equiv_pos_as_xyz'))
    if not operations:
        raise ValueError('缺少明确的 CIF 对称操作；不猜测空间群。')
    ops = [gemmi.Op(plain(x)) for x in operations]
    if not any(op.triplet() == 'x,y,z' for op in ops):
        raise ValueError('CIF 对称操作缺少恒等操作。')
    columns = {k:list(b.find_values('_atom_site_'+k)) for k in
               ['label','type_symbol','fract_x','fract_y','fract_z','occupancy','disorder_group','disorder_assembly']}
    count = len(columns['label'])
    if any(len(columns[k]) != count for k in ['type_symbol','fract_x','fract_y','fract_z','occupancy']):
        raise ValueError('原子坐标/元素/占有率字段不完整。')
    r = res_records(res) if res else None
    if r:
        rc = next((x for x in r['rows'] if x[0].upper() == 'CELL'), None)
        if not rc or any(abs(val(b.find_value('_cell_'+k))-float(v)) > cif_tolerance(b.find_value('_cell_'+k))
                         for k,v in zip(cell_tags,rc[2:8])):
            raise ValueError('CIF 与 RES 晶胞不匹配。')
    atoms, warnings, used, labels = [], [], set(), set()
    for i in range(count):
        label = plain(columns['label'][i])
        if label.upper() in labels:
            raise ValueError('重复 CIF 原子标签：'+label)
        labels.add(label.upper())
        symbol = plain(columns['type_symbol'][i])
        element = gemmi.Element(symbol)
        if element.atomic_number == 0:
            raise ValueError('无法识别元素：'+symbol)
        symbol = element.name
        coords = [val(columns[k][i]) for k in ['fract_x','fract_y','fract_z']]
        occ = val(columns['occupancy'][i])
        if occ < 0 or occ > 1.001:
            warnings.append(label+' 的 CIF 占有率超出常规 0–1 范围；未自动更改。')
        group = plain(columns['disorder_group'][i]) if columns['disorder_group'] else None
        assembly = plain(columns['disorder_assembly'][i]) if columns['disorder_assembly'] else None
        part, context = None, 'cif_only'
        if r:
            matches = []
            base = re.split(r'[_^]', label, 1)[0].upper()
            for j, a in enumerate(r['atoms']):
                if a['label'].upper() not in {label.upper(),base} or a['element'].upper() != symbol.upper():
                    continue
                d = [coords[k]-a['xyz'][k] for k in range(3)]
                if all(abs(v-round(v)) <= max(1e-7,cif_tolerance(columns[k][i]))
                       for v,k in zip(d,['fract_x','fract_y','fract_z'])):
                    matches.append((j,a))
            if len(matches) != 1 or matches[0][0] in used:
                raise ValueError('CIF/RES 标签、元素和坐标不能唯一配对：'+label)
            j, a = matches[0]; used.add(j); part = a['part']; context = 'paired_res'
        if part is not None:
            key, title = 'part:'+str(part), ('PART 0 · 共同位点' if part == 0 else 'PART '+str(part))
        elif group not in UNKNOWN:
            key, title = 'cif:'+str(assembly or '?')+':'+group, 'CIF 组 '+group+(' · 组合 '+assembly if assembly not in UNKNOWN else '')
        else:
            key, title = 'unassigned', 'CIF 未标注分组'
        atoms.append(dict(source_index=i,label=label,element=symbol,atomic_number=element.atomic_number,
                          frac=coords,occupancy=occ,part=part,group=group,assembly=assembly,
                          group_key=key,group_title=title,context=context,
                          radius=float(element.covalent_r),colour=COLOURS.get(symbol,'hsl('+str(element.atomic_number*47%360)+', 48%, 53%)')))
    if r and len(used) != len(r['atoms']):
        raise ValueError('RES 含未与 CIF 配对的原子。')
    if not res:
        warnings.append('未提供配对 RES，按 CIF 无序组显示；未标注的位点不擅自认定为 PART 0。')
    if r and any(x[0].upper() in {'BIND','FREE','CONN'} for x in r['rows']):
        warnings.append('RES 含自定义 BIND/FREE/CONN；本图连线仅为距离筛选，不复现这些精修连接指令。')
    return cell, ops, atoms, warnings, plain(b.find_value('_chemical_formula_sum'))


def compatible(a, b):
    if a['part'] is not None and b['part'] is not None:
        return not (a['part'] and b['part'] and a['part'] != b['part'])
    # Different assemblies can describe independent disorders. Unknown assembly
    # is treated conservatively, never joining different nonzero groups.
    if a['group'] not in UNKNOWN and b['group'] not in UNKNOWN:
        if a['assembly'] in UNKNOWN or b['assembly'] in UNKNOWN or a['assembly'] == b['assembly']:
            return a['group'] == b['group']
    return True


def limit(a, b):
    return 1.18*(a['radius']+b['radius'])+.10


def assemble(cell, ops, atoms, max_sites=6000):
    """One representative per connected component, using lattice/symmetry only.

    Periodic graphs are cut to a finite fragment and explicitly labelled.
    No atom coordinates are fitted or optimized; no intermolecular H bonds added.
    """
    nodes, seeds = [], {}
    for a in atoms:
        seen = {}
        for op in ops:
            if a['part'] is not None and a['part'] < 0 and op.triplet() != 'x,y,z':
                continue
            pos = [x%1 for x in op.apply_to_xyz(a['frac'])]
            key = tuple(round(x%1,6)%1 for x in pos)
            if key not in seen:
                seen[key] = len(nodes)
                nodes.append(dict(a, frac=pos, symmetry=op.triplet()))
            if op.triplet() == 'x,y,z':
                seeds[a['source_index']] = seen[key]
        if len(nodes) > max_sites:
            raise ValueError('对称展开超过 '+str(max_sites)+' 个位点，需选择局部片段，避免无限/巨大结构展开。')
    max_cut = min(7.0, 2.36*max(a['radius'] for a in atoms)+.10)
    lengths = [math.sqrt(sum(x*x for x in row)) for row in cell.frac.mat.tolist()]
    bins = [max(1,int(1/(max_cut*x))) for x in lengths]
    grid = collections.defaultdict(list)
    def bucket(p):return tuple(int(p[k]*bins[k])%bins[k] for k in range(3))
    for i,n in enumerate(nodes):grid[bucket(n['frac'])].append(i)
    edges, adjacency = [], collections.defaultdict(list)
    for i,a in enumerate(nodes):
        home = bucket(a['frac'])
        nearby = {tuple((home[k]+off[k])%bins[k] for k in range(3)) for off in itertools.product((-1,0,1),repeat=3)}
        for key in nearby:
            for j in grid.get(key,[]):
                if j < i:continue
                b = nodes[j]
                if not compatible(a,b) or (a['element'] in ('H','D') and b['element'] in ('H','D')):continue
                cutoff=min(7.0,limit(a,b));delta=[b['frac'][k]-a['frac'][k] for k in range(3)]
                ranges=[range(math.ceil(-delta[k]-cutoff*lengths[k]-1e-8),math.floor(-delta[k]+cutoff*lengths[k]+1e-8)+1) for k in range(3)]
                if math.prod(len(r) for r in ranges)>4096:raise ValueError('极小/倾斜晶胞导致邻近像过多；需要局部片段审查。')
                for rawshift in itertools.product(*ranges):
                    if i==j and rawshift <= (0,0,0):continue
                    shift=list(rawshift);actual=[delta[k]+shift[k] for k in range(3)]
                    d=distance(cart(cell,actual),[0,0,0])
                    if not .40 < d <= cutoff:continue
                    if (a['part'] is not None and a['part'] < 0) or (b['part'] is not None and b['part'] < 0):
                        if a['symmetry'] != 'x,y,z' or b['symmetry'] != 'x,y,z':continue
                        original = [atoms[b['source_index']]['frac'][k]-atoms[a['source_index']]['frac'][k] for k in range(3)]
                        if distance(cart(cell,actual),cart(cell,original)) > .001:continue
                    edges.append((i,j,shift,d));adjacency[i].append((j,shift));adjacency[j].append((i,[-v for v in shift]))
                    if len(edges) > 120000:raise ValueError('推定连线过多，需要局部片段审查。')
    selected, covered, shifts, component_ids, periodic = [], set(), {}, {}, False
    for a in atoms:
        if a['source_index'] in covered:continue
        seed = seeds[a['source_index']]
        start_shift = [round(a['frac'][k]-nodes[seed]['frac'][k]) for k in range(3)]
        q = collections.deque([seed]); shifts[seed] = start_shift; comp=[]
        while q:
            i=q.popleft();comp.append(i)
            for j,s in adjacency[i]:
                proposed=[shifts[i][k]+s[k] for k in range(3)]
                if j in shifts:
                    if shifts[j] != proposed:periodic=True
                else:shifts[j]=proposed;q.append(j)
        for i in comp:
            covered.add(nodes[i]['source_index']);component_ids[i]=len(selected)
        selected.append(comp)
    rendered=[]; lookup={}
    for comp_index,comp in enumerate(selected):
        for i in comp:
            lookup[i]=len(rendered)
            n=nodes[i]
            frac=[n['frac'][k]+shifts[i][k] for k in range(3)]
            rendered.append(dict(n, xyz=cart(cell,frac), display_fractional=frac,
                                 lattice_shift=shifts[i],component=comp_index))
    bonds=[];cut=0
    for i,j,s,d in edges:
        if i not in lookup or j not in lookup:continue
        if [shifts[i][k]+s[k] for k in range(3)] != shifts[j]:cut+=1;continue
        bonds.append(dict(i=lookup[i],j=lookup[j],length=round(d,5)))
    warnings=[]
    if periodic or cut:
        warnings.append('检测到可能的周期连接网络：显示有限片段，截断 '+str(cut)+' 条跨边界连线；不宣称这是完整独立分子。')
    return rendered,bonds,dict(symmetry_sites=len(nodes),display_sites=len(rendered),components=len(selected),
                               mode='finite_periodic_fragment' if periodic else 'assembled_components',cut_edges=cut),warnings


def build(cif, res, output, title=None, status='当前模型展示，科学准确性需结合验证结果审核', counts=None):
    cif=Path(cif).resolve();res=Path(res).resolve() if res else None;output=Path(output).absolute()
    before={'cif':digest(cif),'res':digest(res) if res else None}
    cell,ops,atoms,warnings,formula=parse_model(cif,res)
    shown,bonds,assembly,extra=assemble(cell,ops,atoms);warnings+=extra
    if not bonds:warnings.append('没有识别到距离筛选连线；保留全部位点，不编造连接。')
    groups={}
    for a in shown:
        g=groups.setdefault(a['group_key'],dict(key=a['group_key'],title=a['group_title'],count=0,occupancies=[]))
        g['count']+=1;g['occupancies'].append(a['occupancy'])
    for g in groups.values():g['occupancy_range']=[min(g.pop('occupancies')),max(a['occupancy'] for a in shown if a['group_key']==g['key'])]
    data=dict(schema=1,title=title or cif.stem,status=status,formula=formula,atoms=shown,bonds=bonds,
              groups=list(groups.values()),cell=list(cell.parameters),input_asu_sites=len(atoms),assembly=assembly,
              warnings=warnings,official_counts=counts,source={'cif_name':cif.name,'res_name':res.name if res else None,'sha256':before},
              notes=['原子颜色代表元素；占有率读取 CIF，不把 SHELX 编码占有率当作百分比。',
                     '连线按共价半径和距离筛选，不表示键级；不绘制推定氢键。球体不是热椭球。',
                     'PART 不同的互斥位置用于对照；全部显示不表示它们同时存在。'])
    template=Path(__file__).resolve().parent.parent/'assets/structure_viewer.html'
    payload=json.dumps(data,ensure_ascii=True,allow_nan=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    page=template.read_text(encoding='utf-8').replace('__CAIRYSTAL_TITLE__',html.escape(data['title'])).replace('__CAIRYSTAL_DATA__',payload)
    output.mkdir(parents=True,exist_ok=True)
    dest=output/'structure_viewer.html';metadata=output/'structure_viewer.json'
    if dest.exists() or metadata.exists():raise FileExistsError('查看器已存在；请使用新的输出目录。')
    if digest(cif)!=before['cif'] or (res and digest(res)!=before['res']):raise ValueError('查看器生成期间源模型发生变化。')
    dest.write_text(page,encoding='utf-8');metadata.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return dict(status='generated',path=str(dest),data=str(metadata),sha256=digest(dest),source_sha256=before,
                source_unchanged=True,assembly=assembly,groups=[g['title'] for g in groups.values()],warnings=warnings)


def prepare_delivery(cif,res,output,counts=None):
    """Viewer failure is explicit but must not discard the four validated artifacts."""
    try:return build(cif,res,output,title=Path(cif).stem+' · Cairystal 结构查看',counts=counts,
                     status='已生成验证报告的模型；仍需结合化学证据与 checkCIF 审核')
    except Exception as exc:return dict(status='failed',reason=str(exc),source_modified=False)


def open_generated(viewer, auto_open=True):
    if not viewer or viewer.get('status')!='generated':return dict(status='not_available')
    if not auto_open or os.environ.get('CAIRYSTAL_NO_OPEN','').lower() in ('1','true','yes'):
        return dict(status='disabled',path=viewer['path'])
    path=Path(viewer['path'])
    if not path.is_file() or digest(path)!=viewer['sha256']:
        return dict(status='failed',reason='查看器不存在或哈希改变。')
    try:
        requested=bool(webbrowser.open(path.resolve().as_uri(),new=2))
        return dict(status='open_requested' if requested else 'browser_not_available',path=str(path),visible_confirmed=False)
    except Exception as exc:return dict(status='failed',reason=str(exc),path=str(path))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cif',required=True);p.add_argument('--res');p.add_argument('--output',required=True)
    p.add_argument('--title');p.add_argument('--open',action='store_true')
    a=p.parse_args();result=build(a.cif,a.res,a.output,a.title)
    if a.open:result['browser']=open_generated(result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
