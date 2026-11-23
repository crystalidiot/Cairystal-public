"""Bounded current-run consistency review and bilingual explanations; no LLM."""
import json,math,re
from pathlib import Path
from collections import Counter
from crystal_runtime import sha,records,write_json
from hydrogen_plan import parse_graph,rule,hydrogen_scope,acceptor_exclusion

def excluded_acceptors(graph,mapping):
    atoms,adj=parse_graph(graph);excluded={}
    for k,a in atoms.items():
        reason=acceptor_exclusion(a,adj[k],atoms)
        if reason:excluded[mapping[k].upper()]=reason
    return excluded

def moiety(graph):
    atoms,adj=parse_graph(graph);remaining=set(atoms);parts=[]
    while remaining:
        pending=[min(remaining)];component=set()
        while pending:
            k=pending.pop()
            if k in component:continue
            component.add(k);pending.extend(adj[k])
        remaining-=component;counts=Counter();charge=0
        for k in component:
            a=atoms[k];counts[a['element']]+=1;counts['H']+=rule(a,list(adj[k].values()),'explicit graph')[1];charge+=a['formal_charge']
        order=(['C','H'] if counts['C'] else [])+sorted(e for e in counts if e not in ({'C','H'} if counts['C'] else set()))
        formula=' '.join(e+(str(counts[e]) if counts[e]!=1 else '') for e in order if counts[e])
        if charge:formula+=' '+(str(abs(charge)) if abs(charge)>1 else '')+('+' if charge>0 else '-')
        parts.append(formula)
    values=Counter(parts)
    return ', '.join((f'{n}({f})' if n>1 else f) for f,n in sorted(values.items(),key=lambda p:(not p[0].startswith('C'),p[0])))

def basic_findings(metrics,packet,graph):
    findings=[]
    if type(metrics.get('NPD_atoms')) is not int or metrics['NPD_atoms']!=0:findings.append('NPD count missing or nonzero')
    shift=metrics.get('last_abs_max_shift_esd')
    if type(shift) not in (float,int) or not math.isfinite(shift) or not 0<=shift<=.01:
        findings.append('Maximum absolute shift/esd missing, invalid or above 0.01')
    for key,low,high in [('R1_observed',0,.10),('GooF',.5,2)]:
        value=metrics.get(key)
        if type(value) not in (float,int) or not math.isfinite(value) or not low<=value<=high:findings.append(key+' outside bounded review range')
    if packet.get('local_adp_flags'):findings.append('Local ADP anomalies require interpretation')
    density=packet.get('residual_density')
    import gemmi
    if isinstance(density,(list,tuple)) and len(density)==2:
        density=[gemmi.cif.as_number(str(x)) for x in density]
    else:
        density=[]
    if not density or not all(math.isfinite(x) and abs(x)<=1 for x in density) or density[0]<density[1]:
        findings.append('Residual-density extrema missing, invalid, reversed or outside 1 e/A3 for supported light-element scope')
    if {a['element'] for a in graph['atoms']}-{'C','N','O','F','Cl'}:findings.append('Chemistry outside current C/N/O/F/Cl rule-review scope')
    if sum(a['formal_charge'] for a in graph['atoms'])!=0:findings.append('Supplied complete graph has nonzero total charge')
    return findings

def review_current(root,state,source,output):
    import gemmi
    from audit_occupancy import audit
    from refinement_gate import assess
    from candidate_packet import make_packet
    from report_method_templates import hydrogen_method_notes
    read=lambda p:json.loads(Path(p).read_text('utf-8-sig'))
    gm=state.get('graph_matching',{});finding=[]
    if gm.get('status')!='ready_for_model_review':raise ValueError('No unambiguous graph-match result in this run')
    folder=Path(gm['record']).parent;graph=read(folder/'chemical_graph.json');mapping=read(folder/'mapping.json')
    if gm.get('hydrogen_handling')=='none_in_complete_graph':
        if source!=gm.get('finish_stage') or source!=gm.get('selected_stage') or hydrogen_scope(graph)[0]!=0:
            raise ValueError('H-free finish requires the selected element-refinement stage and a checked H-free graph')
    elif source!=gm.get('hydrogen_stage'):
        raise ValueError('Automatic review only accepts the recorded new graph/H stage')
    model=root/'session/stages'/source/'model.res';stage=model.parent;gate=assess(stage,'model');view=read(stage/'model_review.json')
    start=read(root/'session/start_summary.json')
    if len(start['candidates'])!=1:finding.append('Multiple native space-group candidates need comparison')
    if not gate['execution_complete']:finding.extend(gate['failures'])
    finding.extend(gate['review_reasons']);packet=make_packet(root/'session',{'candidates':[{'stage':str(stage),'review':view,'metrics':gate['metrics']}]})['candidates'][0]
    finding+=basic_findings(gate['metrics'],packet,graph)
    from routine_consistency import audit_files
    routine_checks=audit_files(stage/'model.cif',model)
    write_json(output/'routine_consistency.json',routine_checks)
    finding.extend('Routine consistency: '+i['code'] for i in routine_checks['issues'])
    text=model.read_text('latin1');rows=records(text);controls={r[0].upper() for r in rows}
    forbidden={'OMIT','TWIN','BASF','DFIX','DANG','SADI','SAME','SIMU','RIGU','ISOR','EADP','EXYZ','SUMP','BLOC','DAMP','XNPD'}
    if controls&forbidden:finding.append('Special controls need contextual review: '+str(sorted(controls&forbidden)))
    sg=gemmi.SpaceGroup(view['space_group'])
    if not sg.is_centrosymmetric():finding.append('Noncentrosymmetric absolute-structure/chemical configuration needs a dedicated review')
    a=audit(model,gemmi);atoms=a['atoms'];heavy=[x for x in atoms if x['element'].upper() not in {'H','D'}];hs=[x for x in atoms if x['element'].upper() in {'H','D'}]
    if a['unit_discrepancies'] or a['overlapping_orbit_groups']:finding.append('UNIT or orbit audit failed')
    if any(x['part']!=0 or abs(x['inferred_cif_occupancy']-1)>1e-5 or x['geometric_site_multiplicity']!=x['general_multiplicity'] for x in atoms):finding.append('Disorder/population/special-site review required')
    bylabel={x['label'].upper():x for x in heavy};g,adj=parse_graph(graph)
    if set(mapping.values())!=set(bylabel):finding.append('Heavy-atom mapping does not match current model')
    cell=gemmi.UnitCell(*map(float,next(r[2:] for r in rows if r[0].upper()=='CELL')));ops=sg.operations()
    def distance(x,y):return min(cell.find_nearest_pbc_image(gemmi.Fractional(*x['xyz']),gemmi.Fractional(*op.apply_to_xyz(y['xyz'])),0).dist() for op in ops)
    bonds=[];hcounts=Counter()
    for h in hs:
        neighbors=sorted((distance(h,x),x['label'].upper()) for x in heavy)
        d,parent=neighbors[0];hcounts[parent]+=1
        if not .65<=d<=1.15 or (len(neighbors)>1 and neighbors[1][0]<1.1):finding.append('H parent/short-contact ambiguity: '+h['label'])
    if set(mapping.values())==set(bylabel):
        for k,atom in g.items():
            label=mapping[k];site=bylabel[label]
            if site['element'].upper()!=atom['element'].upper():finding.append('Element mismatch: '+label)
            expected=rule(atom,list(adj[k].values()),'explicit graph')[1]
            if hcounts[label]!=expected:finding.append('H count differs at '+label)
            actual={j for j,t in bylabel.items() if j!=label and distance(site,t)<gemmi.Element(site['element']).covalent_r+gemmi.Element(t['element']).covalent_r+.35}
            if actual!={mapping[j] for j in adj[k]}:finding.append('Current heavy-atom connectivity mismatch: '+label)
            for j in adj[k]:
                if k<j:
                    d=distance(site,bylabel[mapping[j]]);radius=gemmi.Element(atom['element']).covalent_r+gemmi.Element(g[j]['element']).covalent_r
                    bonds.append({'a':label,'b':mapping[j],'distance':d})
                    if not .75*radius<=d<=radius+.25:finding.append('Bond-distance outlier: '+label+' '+mapping[j])
    hn=hydrogen_method_notes(text)
    if hn['evidence']['unsupported']:finding.append('Unsupported H controls: '+str(hn['evidence']['unsupported']))
    evidence={'status':'needs_review' if finding else 'bounded_rules_passed','findings':finding,'metrics':gate['metrics'],'bond_distances':bonds,'H_counts_by_parent':dict(hcounts),'model_sha256':sha(model),'graph_sha256':sha(folder/'chemical_graph.json'),'mapping_sha256':sha(folder/'mapping.json'),'AI_calls':0,'not_established':['independent chemical identity','correctness of supplied chemical prior','complete absence of unmodelled disorder','original absorption processing validity']}
    evidence.update(rule_version='20261028-01',implementation_sha256=sha(__file__),routine_checks=routine_checks)
    write_json(output/'scientific_rules.json',evidence)
    if finding:return evidence,None
    notes={'zh':{'summary':'二维图与本次新模型的连接、元素、氢数及常规精修指标通过限定范围的自动一致性检查。','limitations':'化学身份以所给二维图为前提，未经独立鉴定；自动规则通过不证明结构正确，也不证明不存在未建模无序。供氢接触由几何规则生成，较弱接触不单独证明质子化。'},
           'en':{'summary':'Connectivity, element assignments, H counts and routine refinement metrics passed bounded automatic consistency checks against the supplied graph.','limitations':'Chemical identity is conditional on the supplied 2D graph and lacks independent confirmation. Passing rules proves neither structural correctness nor absence of unmodelled disorder. Geometric donor contacts, including weak contacts, do not independently establish protonation.'}}
    review={'chemistry_and_h_reviewed':True,'review_mode':'bounded_automatic_rules','basis':'Bounded automated consistency review of the current-run graph/H stage: same graph connectivity and elemental/H counts, neutral complete graph, regular full populations, converged light-element model, positive ADPs and bounded residual density. No manual review claimed. Structural correctness and original processing validity are not established. See scientific_rules.json.','annotations':{'_chemical_formula_moiety':moiety(graph)},'bilingual_notes':notes}
    write_json(output/'review.json',review);return evidence,output/'review.json'
