import copy,json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
from model_strategy import classify,handoff_routes
from initial_model_review import build_review
from initial_decisions import decision_queue,element_options
from chemistry_handoff import propose_changes

def atom(label,element,u=.04):
    return {'label':label,'element':element,'part':0,'occupancy':1.,'Ueq':u,
        'res_context_status':'matched','non_positive_definite':False,'principal_rms_axis_ratio':1.,
        'nearby_reported_Q_peaks':[],'neighbors':[]}
def contact(a,b):
    a['neighbors'].append({'label':b['label'],'element':b['element'],'part':0,'occupancy':1.,'Ueq':b['Ueq'],
        'part_compatible':True,'within_covalent_radius_screen':True,'distance':1.8,'symmetry':'x,y,z','translation':[0,0,0]})
def make_packet(atoms):
    return {'all_atoms':atoms,'regions':atoms,'source_hashes':{},'source_directory':'synthetic',
        'space_group':'P 1','gate':{'metrics':{}},'difference_density':{'max':None,'min':None}}
def cage():
    # Synthetic dense graph solely for routing, not coordinates or a real compound.
    sites=[atom('C1','C',.01)]+[atom('B'+str(i),'B') for i in range(1,6)]
    for a in sites:
        for b in sites:
            if a!=b:contact(a,b)
    return make_packet(sites)

class ModelStrategyTests(unittest.TestCase):
    def test_cage_is_a_hypothesis_not_a_formula_or_assignment(self):
        out=classify(cage(),['B','C'])
        self.assertEqual(len(out['possible_cage_sites']),6)
        self.assertFalse(out['automatic_B_C_assignment']);self.assertFalse(out['scientific_acceptance'])
        self.assertFalse(out['graph_required_to_continue'])

    def test_cage_carbon_does_not_get_ordinary_valence_warning(self):
        out=build_review(cage(),['B','C'])
        c=next(x for x in out['sites'] if x['label']=='C1')
        self.assertNotIn('too_many_close_nonmetal_contacts_review_connectivity',c['flags'])
        self.assertEqual(c['chemical_context'],'possible_multicenter_cage')
        self.assertEqual(set(c['candidate_elements_to_review']),{'B','C'})
        self.assertEqual(len(out['sites']),6) # B vertices no longer invisible.

    def test_metal_bound_oxygen_not_called_isolated(self):
        o=atom('O1','O');ti=atom('Ti1','Ti');contact(o,ti);contact(ti,o)
        out=build_review(make_packet([o,ti]),['O','Ti'])
        site=out['sites'][0]
        self.assertNotIn('isolated_site_check_symmetry_coordination_or_solvent',site['flags'])
        self.assertEqual(site['coordination_contacts'][0]['label'],'Ti1')
        self.assertFalse(out['model_strategy']['graph_required_to_continue'])

    def test_actual_isolated_oxygen_still_flagged(self):
        site=build_review(make_packet([atom('O1','O')]),['O'])['sites'][0]
        self.assertIn('isolated_site_check_symmetry_coordination_or_solvent',site['flags'])

    def test_boronic_fragment_is_not_automatically_a_cage(self):
        b=atom('B1','B');neighbors=[atom('O1','O'),atom('O2','O'),atom('C1','C')]
        for n in neighbors:contact(b,n);contact(n,b)
        out=classify(make_packet([b,*neighbors]),['B','C','O'])
        self.assertEqual(out['possible_cage_components'],[])

    def test_missing_allowed_B_does_not_create_B_sites(self):
        out=classify(make_packet([atom('C1','C')]),['B','C'])
        self.assertTrue(out['allowed_B_absent_from_model']);self.assertEqual(out['boron_sites'],[])
        self.assertFalse(out['automatic_model_edit'])

    def test_unrelated_organic_site_keeps_geometry_warning(self):
        c=atom('C1','C');nn=[atom('N'+str(i),'N') for i in range(5)]
        for n in nn:contact(c,n)
        out=build_review(make_packet([c,*nn]),['C','N'])
        self.assertIn('too_many_close_nonmetal_contacts_review_connectivity',out['sites'][0]['flags'])

    def test_pairing_failure_still_precedes_native_suggestions(self):
        p=cage();p['all_atoms'][0]['res_context_status']='unmatched'
        queue=decision_queue(build_review(p,['B','C']))
        self.assertEqual(len(queue),1);self.assertEqual(queue[0]['problem'],'input_pairing')

    def test_no_graph_handoff_provides_native_tools_not_consent(self):
        packet=handoff_routes(Path('run'),'chemical_graph_required',[{'stage':'new','model':str(Path('run/pipeline/session/stages/new/model.res'))}])
        self.assertEqual(packet['owner'],'assistant');self.assertTrue(packet['complete_organic_graph_is_optional'])
        entry=packet['candidates'][0];self.assertEqual(entry['trial']['tool'],'stage');self.assertEqual(entry['finish']['tool'],'complete')
        self.assertNotIn('--authorize-iucr-upload',entry['finish']['arguments'])
        self.assertIsNone(handoff_routes(Path('run'),'integrity_error',[]))

    def test_ordinary_CNO_batch_excludes_cage_but_keeps_other_C(self):
        p=cage();outside=atom('C9','C');p['all_atoms'].append(outside)
        near={a['label']:{n['label'] for n in a['neighbors']} for a in p['all_atoms']}
        view={'atoms':[{'label':a['label'],'neighbors':[]} for a in p['all_atoms']]}
        plans,_=propose_changes(p['all_atoms'],near,view,['B','C','N','O'],'light')
        targets={k for row in plans for k in row['element_changes']}
        self.assertEqual(targets,{'C9'})

    def test_BC_context_does_not_autorun_CNO_retyping(self):
        out=build_review(cage(),['B','C','N','O'])
        parsed={'atoms':[{'label':a['label'],'element':a['element'],'part':0,'residue':'0','encoded_sof':11,'afix':0} for a in cage()['all_atoms']], 'rows':[], 'sfac':['B','C','N','O']}
        plans,deferred=element_options(out,parsed)
        self.assertFalse(plans);self.assertTrue(any('cage_B_C_requires_fragment_context_use_native_branch' in d['reasons'] for d in deferred))

    def test_cage_hint_does_not_absorb_phenyl_substituent(self):
        p=cage();ring=[atom('C'+str(i),'C') for i in range(10,16)]
        for a,b in zip(ring,ring[1:]+ring[:1]):contact(a,b);contact(b,a)
        contact(p['all_atoms'][0],ring[0]);contact(ring[0],p['all_atoms'][0])
        p['all_atoms']=p['all_atoms']+ring;p['regions']=p['all_atoms']
        hint=classify(p,['B','C'])
        self.assertEqual(set(hint['possible_cage_sites']),{'C1','B1','B2','B3','B4','B5'})

    def test_lowercase_cage_labels_also_excluded_from_CNO_trial(self):
        p=cage();atoms=copy.deepcopy(p['all_atoms'])
        near={a['label'].upper():{n['label'].upper() for n in a['neighbors']} for a in atoms}
        for a in atoms:a['label']=a['label'].lower()
        proposals,_=propose_changes(atoms,near,{'atoms':[dict(a,neighbors=[]) for a in atoms]},['B','C','N','O'],'light')
        self.assertEqual(proposals,[])

    def test_coordinator_missing_graph_hands_off_actual_model_and_profile(self):
        import crystal_autorun as ar
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'pipeline/session/stages/solution_a';folder.mkdir(parents=True)
            (folder/'model.res').write_text('Synthetic path-only fixture; not a crystal')
            profile=str(root/'inputs/machine_specific_profile.json')
            state={'actions':[],'options':{'profile':profile},'interventions':[]}
            with patch.object(ar,'specimen_identity',return_value={'name':'synthetic'}),patch('support_report.try_record',return_value=None),patch.dict('os.environ',{'CAIRYSTAL_KNOWLEDGE_INDEX':''}):
                ar.stop(root,state,'chemical_graph_required','No complete organic graph',{'candidates':[{'stage':'solution_a'}]})
            packet=json.loads((root/'handoff.json').read_text('utf-8'))
            entry=packet['native_continuation']['candidates'][0]
            self.assertEqual(entry['model'],str(folder/'model.res'))
            args=entry['finish']['arguments'];self.assertEqual(args[args.index('--profile')+1],profile)
            self.assertFalse(entry['finish']['upload_authorization_added'])
            self.assertEqual(packet['next_step']['owner'],'assistant')

if __name__=='__main__':unittest.main()
