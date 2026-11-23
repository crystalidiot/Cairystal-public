"""Synthetic graph fixtures only: no crystallographic reference models."""
import copy,unittest,tempfile
from pathlib import Path
from graph_assignment import enumerate_assignments,select_trial,propose
from hydrogen_plan import plan_from_decisions

def fixture():
    graph={'atoms':[{'id':'n','element':'N','formal_charge':1,'hydrogens':0},
        *[{'id':k,'element':'C','formal_charge':0,'hydrogens':3} for k in ('a','b','c')],
        {'id':'o','element':'O','formal_charge':-1,'hydrogens':0}],
        'bonds':[['n',k,1] for k in ('a','b','c','o')]}
    atoms=[{'label':k,'element':'C','inferred_cif_occupancy':1,'geometric_site_multiplicity':1,'general_multiplicity':1} for k in ('Z9','A7','Q3','X6','M2')]
    near={a['label']:set() for a in atoms}
    for k in ('A7','Q3','X6','M2'):near['Z9'].add(k);near[k].add('Z9')
    return graph,atoms,near,{}

def trial(name,r,**kwargs):
    result={'id':name,'stage':name,'execution_complete':True,'review_reasons':[],
        'graph_H_check':'ready_for_refinement',
        'metrics':{'R1_observed':r,'wR2':r*2,'GooF':1,'unique':1200,'NPD_atoms':0,'last_abs_max_shift_esd':.001}}
    result.update(kwargs);return result

class Matching(unittest.TestCase):
    def test_sfac_uppercase_multiletter_element_is_same_anchor(self):
        g={'atoms':[{'id':'c','element':'C','formal_charge':0,'hydrogens':3},{'id':'x','element':'Cl','formal_charge':0,'hydrogens':0}],'bonds':[['c','x',1]]}
        atoms=[{'label':'Z9','element':'C'},{'label':'CL07','element':'CL'}]
        r=enumerate_assignments(g,atoms,{'Z9':{'CL07'},'CL07':{'Z9'}},{})
        self.assertEqual(r['assignment_classes'],1)
        self.assertEqual(r['candidates'][0]['plan']['element_changes'],{})
    def test_real_parser_and_periodic_geometry_on_synthetic_sites(self):
        graph={'atoms':[{'id':'m','element':'C','formal_charge':0,'hydrogens':3},{'id':'o','element':'O','formal_charge':0,'hydrogens':1}],'bonds':[['m','o',1]]}
        res='TITL synthetic only\nCELL 0.71073 20 21 22 90 90 90\nLATT -1\nSFAC C H O\nUNIT 1 0 1\nTEMP -173\nFVAR 1\nC8 1 .200 .250 .300 11 .03\nO4 3 .2715 .250 .300 11 .03\nHKLF 4\nEND\n'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'model.res';p.write_text(res)
            r=propose(p,graph);self.assertEqual(r['assignment_classes'],2)
            self.assertEqual(r['neighbors'],{'C8':['O4'],'O4':['C8']})
            p.write_text(res.replace('.2715','.2865'))
            with self.assertRaisesRegex(ValueError,'near radius cutoff'):propose(p,graph)
    def test_enumerates_chemical_choices_collapses_names(self):
        r=enumerate_assignments(*fixture())
        self.assertEqual(r['status'],'candidates_ready');self.assertEqual(r['assignment_classes'],4)
        self.assertEqual(r['complete_label_mappings'],24)
        self.assertTrue(all(x['label_permutations']==6 for x in r['candidates']))
        self.assertEqual({c['original_mapping']['o'] for c in r['candidates']},{'A7','Q3','X6','M2'})
        self.assertTrue(all(c['original_mapping']['n']=='Z9' for c in r['candidates']))
    def test_shuffled_model_order_does_not_change_choices(self):
        f=list(fixture());first=enumerate_assignments(*f);f[1].reverse()
        self.assertEqual(first,enumerate_assignments(*f))
    def test_no_missing_site_invention(self):
        f=list(fixture());f[1].pop();self.assertEqual(enumerate_assignments(*f)['status'],'needs_review')
    def test_non_light_elements_remain_anchors(self):
        f=list(fixture());f[1][0]['element']='Br'
        self.assertEqual(enumerate_assignments(*f)['status'],'needs_review')
    def test_disorder_and_special_positions_stop(self):
        for key,value in [('part',1),('inferred_cif_occupancy',.5),('geometric_site_multiplicity',2)]:
            f=list(fixture());f[1][0][key]=value
            self.assertEqual(enumerate_assignments(*f)['status'],'needs_review')
    def test_stereo_stops(self):
        f=list(fixture());f[0]['smiles']='F/C=C/F'
        self.assertEqual(enumerate_assignments(*f)['status'],'needs_review')
    def test_incomplete_search_is_never_accepted(self):
        for kw in ({'max_classes':2},{'max_nodes':2}):
            r=enumerate_assignments(*fixture(),**kw)
            self.assertEqual(r['status'],'needs_review');self.assertTrue(r['search_truncated']);self.assertEqual(r['candidates'],[])
    def test_non_edges_are_checked(self):
        f=list(fixture());f[2]['A7'].add('Q3');f[2]['Q3'].add('A7')
        self.assertEqual(enumerate_assignments(*f)['status'],'needs_review')
    def test_clear_candidate_is_provisional(self):
        r=select_trial([trial('a',.04),trial('b',.07)])
        self.assertEqual(r['status'],'ready_for_model_review');self.assertEqual(r['selected_id'],'a')
    def test_tied_or_missing_trials_require_review(self):
        for trials in ([trial('a',.04),trial('b',.041)], [trial('a',.04),trial('b',.07,execution_complete=False)],[]):
            self.assertEqual(select_trial(trials)['status'],'needs_review')
    def test_npd_missing_convergence_and_nan_cannot_win(self):
        for field,value in [('NPD_atoms',1),('last_abs_max_shift_esd',.1),('R1_observed',float('nan')),('GooF',3)]:
            t=trial('a',.04);t['metrics'][field]=value
            self.assertEqual(select_trial([t])['status'],'needs_review')
        t=trial('a',.04);del t['metrics']['last_abs_max_shift_esd']
        self.assertEqual(select_trial([t])['status'],'needs_review')
    def test_low_r_invalid_competitor_blocks_automatic_choice(self):
        self.assertEqual(select_trial([trial('a',.04,review_reasons=['bad ADP']),trial('b',.07)])['status'],'needs_review')
    def test_reflection_counts_must_agree(self):
        a,b=trial('a',.04),trial('b',.07);b['metrics']['unique']=1199
        self.assertEqual(select_trial([a,b])['status'],'needs_review')
    def test_unresolved_h_cannot_produce_plan(self):
        with self.assertRaises(ValueError):plan_from_decisions({'status':'needs_review','commands':['HFIX 23 C1']})

if __name__=='__main__':unittest.main()
