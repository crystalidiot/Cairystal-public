"""Evidence-bound transcription candidates, preserving uncertainty and every raw trial."""
import argparse,json,re,copy,collections,time
from pathlib import Path
from PIL import Image
import numpy as np,cv2
from rdkit import Chem
from molscribe.chemistry import convert_graph_to_smiles
from molscribe_local import sha,write,safe,chemical_graph

def read(p):return json.loads(safe(p).read_text(encoding='utf-8-sig'))
def canonical(s):
    m=Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m,isomericSmiles=True) if m else None
def normalize_label(text,upright,elements):
    text=re.sub(r'\s+','',text).replace('−','-')
    match=re.fullmatch(r'(Cl|Cu|CI|C1|C/)([1-9]?[+-])',text)
    if not match:return None
    element,charge=match.groups()
    if element in {'CI','C1','C/'}:
        if not upright or 'Cl' not in elements or 'I' in elements:return None
        element='Cl'
    if element not in elements:return None
    q=int(charge[:-1] or '1')*(1 if charge[-1]=='+' else -1)
    return element,q
def label_evidence(labels,elements):
    accepted=[];ambiguous=[]
    for label in labels:
        samples=[('detected',label['original_text'],label['original_score'])]
        for row in label['reads']:
            for value in row['result'] or []:
                if len(value)==2 and isinstance(value[0],str):samples.append((row['view'],value[0],float(value[1])))
        grouped=collections.defaultdict(list)
        for view,text,score in samples:
            value=normalize_label(text,label['upright_after_round_letter'],elements)
            if value and score>=.75:grouped[value].append({'view':view,'text':text,'score':score})
        ranked=sorted(grouped.items(),key=lambda item:(-len(item[1]),-max(x['score'] for x in item[1])))
        if not ranked:continue
        key,ev=ranked[0]
        strong=len(ev)>=2 and (max(x['score'] for x in ev)>=.9 or sum(x['score']>=.8 for x in ev)>=3)
        conflicts=[k for k,v in ranked[1:] if len(v)>=2]
        item={'element':key[0],'charge':key[1],'box':label['box'],'crop':label['crop'],'crop_sha256':label['crop_sha256'],'readings':ev,'upright_evidence':label['upright_after_round_letter']}
        (accepted if strong and not conflicts else ambiguous).append(item)
    return accepted,ambiguous
def correct(pred,view,evidence,image):
    pred=copy.deepcopy(pred);changes=[];supports=[]
    for ev in evidence:
        x0,y0,x1,y1=ev['box'];found=[]
        for i,a in enumerate(pred.get('atoms',[])):
            bx,by,br,bb=view['tight_box'];scale=view['scale']
            x=(a['x']*(br-bx+10)+bx-5)/scale;y=(a['y']*(bb-by+10)+by-5)/scale
            if x0-5<=x<=x1+5 and y0-5<=y<=y1+5 and re.match(r'^\[?(Cl|Cu|C)(?![a-z])',a['atom_symbol']):found.append(i)
        if len(found)!=1:continue
        i=found[0];a=pred['atoms'][i];q=ev['charge'];symbol='['+ev['element']+('+' if q>0 else '-')+(str(abs(q)) if abs(q)>1 else '')+']'
        supports.append({'atom_index':i,'label':symbol,'evidence':ev})
        if a['atom_symbol']!=symbol:
            changes.append({'atom_index':i,'from':a['atom_symbol'],'to':symbol,'basis':'Local OCR agreement plus glyph/element checks on bound source pixels','evidence':ev});a['atom_symbol']=symbol
    if changes:
        n=len(pred['atoms']);edges=[[0]*n for _ in range(n)];types=['','single','double','triple','aromatic','solid wedge','dashed wedge']
        for b in pred['bonds']:
            i,j=b['endpoint_atoms'];edges[i][j]=edges[j][i]=types.index(b['bond_type'])
        coords=[[a['x'],a['y']] for a in pred['atoms']];symbols=[a['atom_symbol'] for a in pred['atoms']]
        s,m,ok=convert_graph_to_smiles([coords],[symbols],[edges],images=[image],num_workers=1)
        pred['smiles']=s[0];pred['molfile']=m[0]
    return pred,changes,supports

def assess(smiles,elements):
    m=Chem.MolFromSmiles(smiles) if smiles else None;issues=[]
    if m is None:return ['invalid_graph']
    for a in m.GetAtoms():
        if a.GetAtomicNum()==0:issues.append('undefined_R_group_or_abbreviation')
        if a.GetSymbol() not in elements:issues.append('element_outside_user_set')
        if a.GetNumRadicalElectrons():issues.append('radical')
    return sorted(set(issues))

def fragment_scope_issues(smiles):
    """Conservative scope boundary, not an answer-based graph correction.

    Short isolated fragments have little independent topology evidence. A common
    neural error can survive every resize/threshold view; require image review
    until atom/edge pixels have an independently validated verifier. Explicit
    printed H2O follows its separate audited literal-formula rule.
    """
    mol=Chem.MolFromSmiles(smiles) if smiles else None
    if mol is not None and mol.GetNumHeavyAtoms()<=4:
        return ['Small fragment (<=4 heavy atoms) lacks an independently validated atom/bond pixel check; correlated model agreement is insufficient']
    return []

def explicit_water(region,labels,elements):
    if region.get('role')!='explicit_water_label' or not region.get('source_detached') or not {'H','O'}<=set(elements):return None
    image=np.asarray(Image.open(region['image']).convert('RGB'));ink=(cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)<160).astype(np.uint8)
    n,cc,stats,ct=cv2.connectedComponentsWithStats(ink,8)
    glyphs=sorted([s.tolist() for s in stats[1:] if s[4]>=5],key=lambda s:s[0])
    if len(glyphs)!=3:return None
    h,two,o=glyphs;midheight=(h[3]+o[3])/2
    # A literal H2O has H and O on the main baseline; the 2 is lower and smaller.
    # H20 with both digits subscript does not satisfy this shape test.
    if not (.8<=o[3]/h[3]<=1.25 and .35*midheight<=two[3]<=.85*midheight and two[1]>min(h[1],o[1])+midheight*.25):return None
    evidence=[]
    for label in labels:
        for view,text,score in [('detected',label['original_text'],label['original_score'])]+[(x['view'],v[0],v[1]) for x in label['reads'] for v in x['result'] or [] if len(v)==2 and isinstance(v[0],str)]:
            if re.sub(r'\s+','',text).replace('₂','2') in {'H2O','H20'} and score>=.75:evidence.append({'view':view,'text':text,'score':score})
    if len(evidence)<2 or region.get('confidence',0)<.9:return None
    return {'smiles':'O','basis':'Explicit H2O text, lower subscript 2 and full-height terminal O; multiple OCR contexts. Not inferred from an isolated oxygen site. Raw neural outputs retained and rejected.','glyphs':glyphs,'readings':evidence,'source_text':region['text']}

def run(regions,raw,labels,output):
    output=safe(output);assert not output.exists();output.mkdir();start=time.perf_counter()
    assert sha(raw)==read(Path(raw).parent/'seal.json')['raw_predictions_sha256']
    rr=read(raw);spec=read(regions);assert sha(regions)==rr['regions_sha256']
    inventory={c['case_id']:c for c in spec['cases']};ll={c['case_id']:c['labels'] for c in read(labels)['cases']}
    result={'raw_predictions':str(raw),'raw_sha256':sha(raw),'regions':str(regions),'regions_sha256':sha(regions),'labels':str(labels),'labels_sha256':sha(labels),
      'rule_parameters':{'min_agreeing_views':3,'views':4,'local_label_min_score':.75,'local_label_min_reads':2,'strong_label_rule':'one >=0.90 or three >=0.80; glyph disambiguation for CI/C1/C/; no substitution on chemistry alone'},
      'external_LLM_calls':0,'cases':[],'scientific_structure_acceptance':False}
    for c in rr['cases']:
        inp=inventory[c['case_id']];region_byid={x['region_id']:x for x in inp['regions']};row={'case_id':c['case_id'],'image_sha256':inp['image_sha256'],'regions':[],'review_reasons':[]}
        chosen=[];all_consensus=True
        for rawregion in c['regions']:
            region=region_byid[rawregion['region_id']];key=c['case_id']+region['region_id'];record={'region_id':region['region_id'],'source_box':region['box'],'source_crop':region['image']}
            if rawregion.get('role')=='standalone_numeric_annotation':
                record.update(rawregion);row['regions'].append(record);row['review_reasons'].append('Numeric coefficient must be assigned to the intended component; do not discard or infer from total formula');all_consensus=False;continue
            water=explicit_water(region,ll.get(key,[]),inp['elements'])
            if water:
                record.update(candidate_smiles='O',agreeing_views=0,consensus_mode='explicit_formula_rule',formula_evidence=water,raw_neural_views=rawregion['views'])
                chosen.append('O');row['regions'].append(record);continue
            evidence,weak=label_evidence(ll.get(key,[]),inp['elements']);record['accepted_label_evidence']=evidence;record['weak_label_evidence']=weak;trials=[]
            image=np.asarray(Image.open(region['image']).convert('RGB'))
            for v in rawregion['views']:
                pred,changes,supports=correct(v['prediction'],v,evidence,image);s=canonical(pred.get('smiles',''))
                trials.append({'view':v['view'],'raw_smiles':v['prediction'].get('smiles'),'smiles':s,'changes':changes,'label_supports':supports,'confidence':pred.get('confidence',0),'issues':assess(s,inp['elements'])})
            counts=collections.Counter(t['smiles'] for t in trials if t['smiles'] and not t['issues'])
            ranked=sorted(counts,key=lambda s:(-counts[s],-max(t['confidence'] for t in trials if t['smiles']==s)))
            selected=ranked[0] if ranked else None;agreement=counts.get(selected,0);record.update(trials=trials,candidate_smiles=selected,agreeing_views=agreement)
            if selected:
                chosen.append(selected)
                scope_issues=fragment_scope_issues(selected);record['scope_issues']=scope_issues
                if scope_issues:
                    row['review_reasons'].extend(f'{region["region_id"]}: {reason}' for reason in scope_issues);all_consensus=False
            if agreement<3 or len(ranked)>1 and counts[ranked[1]]==agreement:
                row['review_reasons'].append(f'{region["region_id"]}: insufficient or tied graph consensus');all_consensus=False
            if selected and any(t['issues'] for t in trials if t['smiles']==selected):all_consensus=False
            # Charged, multiply bonded chlorine requires label confirmation, even
            # when several views of the same neural model make the same mistake.
            if selected:
                mol=Chem.MolFromSmiles(selected);charged_cl=[a for a in mol.GetAtoms() if a.GetSymbol()=='Cl' and a.GetDegree()>1 and a.GetFormalCharge()!=0]
                if charged_cl and not evidence:row['review_reasons'].append(f'{region["region_id"]}: chlorine charge lacks sufficient pixel-label support');all_consensus=False
            if region['role']=='explicit_water_label':
                record['explicit_water_text']=region['text']
                if selected!='O':row['review_reasons'].append('Explicit water label is not consistently represented');all_consensus=False
            row['regions'].append(record)
        panels=inp['segmentation']['layout']=='multi_panel'
        complete=len(chosen)==sum(r.get('role')!='standalone_numeric_annotation' for r in c['regions'])
        combined=canonical('.'.join(chosen)) if complete and not panels else None
        row['candidate_smiles']=combined;row['panel_candidates']=[r.get('candidate_smiles') for r in row['regions']] if panels else None
        if panels:row['review_reasons'].append('Multiple named panels are separate molecules, not a single sample formula');all_consensus=False
        if not complete:row['review_reasons'].append('One or more fragment graphs missing');all_consensus=False
        if min(Image.open(inp['image']).size)<150:row['review_reasons'].append('Low-resolution source requires image review');all_consensus=False
        if combined:
            screen=chemical_graph({'smiles':combined,'confidence':1},inp['elements']);row['graph']=screen['graph'];row['formula']=screen.get('formula')
            special=[x for x in screen['issues'] if any(y in x for y in ['Isotope','Explicit H','stereochemistry','Radical','R-group','outside'])]
            row['downstream_review_reasons']=special
            mol=Chem.MolFromSmiles(combined)
            if {a.GetSymbol() for a in mol.GetAtoms()}-{'C','N','O','F','Cl'}:row['downstream_review_reasons'].append('Outside existing bounded C/N/O/F/Cl automatic scientific-review scope')
            if sum(a.GetFormalCharge() for a in mol.GetAtoms())!=0:row['downstream_review_reasons'].append('Nonneutral pictured component: complete counterion/stoichiometry information required before crystal matching')
            if any(len(f)==1 and mol.GetAtomWithIdx(f[0]).GetSymbol()=='O' and mol.GetAtomWithIdx(f[0]).GetTotalNumHs()==2 for f in Chem.GetMolFrags(mol)):
                row['downstream_review_reasons'].append('Water recognized; its crystallographic H orientation remains a dedicated task')
            row['recognition_status']='supported_transcription' if all_consensus else 'needs_AI_review'
            row['pipeline_status']='ready_for_refinement_trial' if all_consensus and not row['downstream_review_reasons'] else 'needs_review'
            if row['graph']:
                row['graph']['source']='Local image segmentation, four-view graph agreement and auditable text-label checks; chemical prior only.';row['graph']['local_recognition']=True
                path=output/(c['case_id']+'_candidate_graph.json');write(path,row['graph']);row['graph_path']=str(path);row['graph_sha256']=sha(path)
        else:row['recognition_status']='needs_AI_review';row['pipeline_status']='needs_review'
        result['cases'].append(row);write(output/'result.json',result)
        print(json.dumps({'case_id':c['case_id'],'smiles':combined,'recognition':row['recognition_status'],'pipeline':row['pipeline_status'],'agreement':[x.get('agreeing_views') for x in row['regions']],'reasons':row['review_reasons']},ensure_ascii=False),flush=True)
    result['wall_seconds']=time.perf_counter()-start;write(output/'result.json',result);write(output/'seal.json',{'result_sha256':sha(output/'result.json'),'reference_answers_read':False})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--regions',required=True);p.add_argument('--raw',required=True);p.add_argument('--labels',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.regions,a.raw,a.labels,a.output)
