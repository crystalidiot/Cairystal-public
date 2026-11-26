"""Classify tool applicability from the current model, not chemical identity.

Read-only hints for cluster/coordination/native continuation. A contact graph is
not a bond-order graph. This module never authorizes masking or changes atoms.
"""
import argparse
import json
from pathlib import Path
import gemmi

def contact_blocks(adjacency):
    """Biconnected blocks keep a cage hint out of singly attached substituents."""
    order={};low={};edges=[];blocks=[]
    def visit(v,parent=None):
        order[v]=low[v]=len(order)
        for w in sorted(adjacency[v]):
            if w not in order:
                edges.append((v,w));visit(w,v);low[v]=min(low[v],low[w])
                if low[w]>=order[v]:
                    block=set()
                    while edges:
                        edge=edges.pop();block.update(edge)
                        if edge==(v,w):break
                    blocks.append(block)
            elif w!=parent and order[w]<order[v]:
                edges.append((v,w));low[v]=min(low[v],order[w])
    for v in sorted(adjacency):
        if v not in order:visit(v)
    return blocks

def close_contacts(atom):
    return [n for n in atom.get('neighbors',[]) if n.get('part_compatible') is True
            and n.get('within_covalent_radius_screen') is True
            and n.get('element') not in ('H','D')]

def classify(packet, allowed):
    atoms=packet.get('all_atoms',[]);by={a['label']:a for a in atoms}
    elements={a['element'] for a in atoms};allowed=set(allowed)
    regions={a['label']:a for a in packet.get('regions',[])}
    metals=sorted(a['label'] for a in atoms if gemmi.Element(a['element']).is_metal)
    boron=sorted(a['label'] for a in atoms if a['element']=='B')
    # A cyclic, B-rich B/C contact component is a routing hint. It does not
    # assign a closo/nido identity, vertex count, charges or cage B/C positions.
    adjacency={a['label']:set() for a in atoms if a['element'] in {'B','C'}}
    for label,row in regions.items():
        if label not in adjacency:continue
        for n in close_contacts(row):
            other=n['label']
            if other in adjacency and other!=label:
                adjacency[label].add(other);adjacency[other].add(label)
    components=[]
    for group in contact_blocks(adjacency):
        nb=sum(by[x]['element']=='B' for x in group);edges=sum(len(adjacency[x]&group) for x in group)//2
        if len(group)>=4 and nb>=2 and edges>=len(group):
            components.append({'atoms':sorted(group),'B_sites':nb,'contact_edges':edges,
                               'classification':'possible_multicenter_B_C_fragment','chemical_identity_confirmed':False})
    cage_sites=sorted({x for c in components for x in c['atoms']})
    coordination_sites=sorted(label for label,row in regions.items()
                              if any(gemmi.Element(n['element']).is_metal for n in close_contacts(row)))
    missing_b='B' in allowed and 'B' not in elements
    special=bool(metals or boron or missing_b)
    return {'schema':1,'owner':'assistant','route':'native_candidate_comparison' if special else 'graph_or_native_candidate_comparison',
            'graph_required_to_continue':False,'metal_sites':metals,'coordination_sites':coordination_sites,
            'boron_sites':boron,'possible_cage_components':components,'possible_cage_sites':cage_sites,
            'allowed_B_absent_from_model':missing_b,
            'ordinary_organic_valence_not_applicable_to':cage_sites,
            'automatic_B_C_assignment':False,'automatic_H_generation_for_cage':False,
            'automatic_model_edit':False,'scientific_acceptance':False,
            'tools':['stage','diagnose','occupancy','complete'],
            'reference':'references/adaptive-science.md',
            'next_actions':[
                'Check the current scattering types against all allowed elements; a missing allowed element is a hypothesis to investigate, not proof it must be present.',
                'Use current full fragments, symmetry, signed density and ADP to compare supported identities. B/C cage contacts are not ordinary carbon valence counts.',
                'Keep a baseline and prepare an explicit native INS in a new directory when graph/H templates do not apply; stage runs SHELXL without requiring a complete organic graph.',
                'Use complete with a current-model review after choosing a candidate. It retains refinement, local AB, authorized exact-CIF IUCr and bilingual Word.',
                'If the host is supported and separate diffuse solvent remains difficult, assess SQUEEZE in parallel; reuse existing case authorization or ask once. Zero AB is not a prerequisite.'],
            'solvent_branch':{'tool':'squeeze','requires_zero_AB':False,'automatic_masking':False,
                'eligibility':'Current host/mask separation, charge/composition, low-order data and evidence review; never infer missing cage atoms are solvent from Q peaks alone.'},
            'limits':['Contact-component thresholds route work; they do not recognize a compound or validate a cage.',
                      'B/C, disorder, solvent identity and hydrogen chemistry remain current-data decisions.']}

def handoff_routes(root, category, first_models):
    """Concrete fallback from the existing coordinator's current model checkpoint."""
    if category not in {'chemical_graph_required','scientific_decision','initial_model_review_unavailable'}:
        return None
    root=Path(root)
    result={'owner':'assistant','script_limitation_is_not_structure_failure':True,
            'complete_organic_graph_is_optional':True,'reference':'references/adaptive-science.md','candidates':[],
            'return_to_coordinator':{'tool':'autorun','arguments':['continue-native','--run',str(root),
                '--candidate','SELECTED_CURRENT_CANDIDATE','--review','CURRENT_MODEL_REVIEW.json','--name','UNIQUE_BRANCH_NAME'],
                'placeholders_require_preparation':True,'reuses_current_specimen_and_consent':True,'replays_solution_or_graph':False}}
    for entry in first_models or []:
        model=entry.get('model')
        if not model:continue
        p=Path(model);folder=p.parent
        result['candidates'].append({'stage':entry.get('stage'),'model':model,
            'strategy':entry.get('model_strategy'),
            'trial':{'tool':'stage','arguments':['--executable','SHELXL_FROM_PROFILE','--ins','NEW_CURRENT_CANDIDATE.ins','--hkl',str(folder/'model.hkl'),'--output','NEW_TRIAL_DIRECTORY','--reason','CURRENT_EVIDENCE_BASIS'],
                     'placeholders_require_preparation':True},
            'finish':{'tool':'complete','arguments':['--input','SELECTED_CURRENT_TRIAL','--profile',str(root/'inputs/profile.json'),'--review','CURRENT_MODEL_REVIEW.json','--output','NEW_COMPLETION_DIRECTORY'],
                      'profile_lookup':'Use the coordinator options.profile binding; do not assume this illustrative profile path exists.',
                      'upload_authorization_added':False,'placeholders_require_preparation':True}})
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',required=True,type=Path);p.add_argument('--stem',default='model')
    p.add_argument('--elements',nargs='+',required=True);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    from initial_model_review import review
    if a.output.exists():p.error('Choose a new output file')
    result=review(a.directory,a.stem,a.elements)['model_strategy']
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(result,ensure_ascii=False));return 0

if __name__=='__main__':raise SystemExit(main())
