"""Synthetic behavior checks: no experimental structures or reference answers."""
from pathlib import Path
import copy, hashlib, json, math, tempfile, unittest
from unittest.mock import patch
import gemmi
from test_initial_model_review import packet, write_fixture
from initial_model_review import build_review, review
from initial_decisions import decision_queue, element_options, prepare_element_trials
from structure_diagnostics import res_records
from workflow_observability import record_wait, close_wait, summarize_waits
from common_disorder_fixtures import fixture
from common_disorder import detect
from density_disorder import screen_decisions, run

class DecisionFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_all_sites_reach_queue_not_first_three_only(self):
        r=build_review(packet(),['C','N','O']);r['sites']=[dict(r['sites'][0],label='C'+str(n)) for n in range(7)]
        q=decision_queue(r);self.assertEqual(len(q),7);self.assertEqual(q[-1]['atoms'],['C6'])
    def test_unpaired_input_does_not_recommend_edits(self):
        p=packet();p['all_atoms'][0]['res_context_status']='unmatched'
        q=decision_queue(build_review(p,['C','N','O']))
        self.assertEqual(len(q),1);self.assertEqual(q[0]['problem'],'input_pairing')
    def test_absence_of_flags_not_chemical_acceptance(self):
        q=decision_queue({'status':'screened_requires_chemical_review','findings':[],'sites':[]})
        self.assertFalse(q[0]['scientific_acceptance']);self.assertEqual(q[0]['execution'],'assistant_review')
    def test_unknown_element_has_explicit_decision(self):
        q=decision_queue({'findings':[{'code':'element_outside_input','atom':'X1','element':'F'}]})
        self.assertEqual(q[0]['problem'],'element_outside_input')
    def test_current_files_prepare_types_keep_data_controls(self):
        d=self.root/'base';write_fixture(d)
        original={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in d.iterdir()}
        r=review(d,'model',['C','N','O']);p=self.root/'profile.json'
        p.write_text(json.dumps({'tools':{k:{'path':__file__} for k in ['shelxl','platon']}}))
        with patch('crystal_runtime.paired_bundle',return_value={'files':{ext:str(d/('model.'+ext)) for ext in ['res','cif']}}):
            out=prepare_element_trials(d,'model',r,self.root/'plan',p)
        self.assertEqual(out['trial_count'],2)
        plan=json.loads(Path(out['plan']).read_text());self.assertEqual(plan['trials'][0]['kind'],'baseline')
        from candidate_trials import controls,IMMUTABLE
        ins=(self.root/'plan/prepared/type_1_N/case.ins').read_text()
        self.assertEqual(controls((d/'model.res').read_text(),IMMUTABLE),controls(ins,IMMUTABLE))
        self.assertIn('C1 2 ',ins)
        self.assertEqual(original,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in d.iterdir()})
    def test_stale_review_cannot_prepare_trial(self):
        d=self.root/'base';write_fixture(d);r=review(d,'model',['C','N','O'])
        with (d/'model.res').open('a') as f:f.write('REM changed\n')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            prepare_element_trials(d,'model',r,self.root/'plan','unused')
        self.assertFalse((self.root/'plan').exists())
    def test_allowed_elements_do_not_imply_formula_or_add_SFAC(self):
        d=self.root/'base';write_fixture(d);r=review(d,'model',['C','N'])
        choices,_=element_options(r,res_records(d/'model.res'))
        self.assertEqual([t['element_changes'] for t in choices],[{'C1':'N'}])
    def test_partial_or_existing_H_is_deferred_explicitly(self):
        d=self.root/'base';write_fixture(d);r=review(d,'model',['C','N','O']);p=res_records(d/'model.res')
        p['atoms'].append({'label':'H1','element':'H'})
        trials,deferred=element_options(r,p)
        self.assertEqual(trials,[]);self.assertIn('existing_H_requires_parent_and_protonation_review',deferred[0]['reasons'])
        p['atoms'].pop();p['atoms'][0]['part']=1
        self.assertEqual(element_options(r,p)[0],[])
    def test_candidate_budget_records_unrun_options(self):
        d=self.root/'base';write_fixture(d);r=review(d,'model',['C','N','O'])
        trials,deferred=element_options(r,res_records(d/'model.res'),max_trials=1)
        self.assertEqual(len(trials),1);self.assertEqual(deferred[-1]['reasons'],['trial_budget'])
    def test_failed_geometry_precedes_type_trials(self):
        d=self.root/'base';write_fixture(d);r=review(d,'model',['C','N','O']);r['sites'][0]['flags'].append('very_short_contact')
        self.assertEqual(element_options(r,res_records(d/'model.res'))[0],[])

class HandoffTimingTests(unittest.TestCase):
    def packet(self):return {'category':'chemical_graph_required','reason':'Unknown graph','next_step':{'owner':'assistant'}}
    def test_duplicate_observation_does_not_restart_clock(self):
        state={};record_wait(state,self.packet(),'2026-01-01T00:00:00+00:00')
        record_wait(state,self.packet(),'2026-01-01T00:00:10+00:00');close_wait(state,'match','2026-01-01T00:00:20+00:00')
        s=summarize_waits(state);self.assertEqual(len(s['episodes']),1)
        self.assertEqual(s['by_reason'][0]['closed_seconds'],20);self.assertIsNone(s['AI_time_s'])
    def test_changed_evidence_creates_separate_interval(self):
        state={};record_wait(state,self.packet(),'2026-01-01T00:00:00+00:00')
        p=self.packet();p['first_models']=[{'review_sha256':'new'}]
        record_wait(state,p,'2026-01-01T00:00:10+00:00')
        self.assertEqual(len(state['wait_episodes']),2);self.assertEqual(state['wait_episodes'][0]['duration_s'],10)
    def test_changed_reason_in_same_category_is_not_lost(self):
        state={};record_wait(state,self.packet(),'2026-01-01T00:00:00+00:00')
        p=self.packet();p['reason']='Graph supplied; protonation evidence still missing'
        record_wait(state,p,'2026-01-01T00:00:10+00:00')
        self.assertEqual(len(state['wait_episodes']),2);self.assertEqual(state['wait_episodes'][-1]['detail'],p['reason'])
    def test_open_wait_is_not_zero_or_closed_time(self):
        state={};record_wait(state,self.packet(),'2026-01-01T00:00:00+00:00')
        s=summarize_waits(state,'2026-01-01T00:00:07+00:00')
        self.assertIsNone(s['episodes'][0]['duration_s']);self.assertEqual(s['episodes'][0]['open_age_s'],7)
        self.assertEqual(s['by_reason'][0]['open_episodes'],1)
    def test_clock_reversal_is_unknown(self):
        state={};record_wait(state,self.packet(),'2026-01-01T00:00:10+00:00')
        close_wait(state,'resume','2026-01-01T00:00:00+00:00')
        self.assertIsNone(state['wait_episodes'][0]['duration_s'])
    def test_legacy_run_not_backfilled_as_AI_time(self):
        self.assertEqual(summarize_waits({'actions':[{'seconds':10}]})['status'],'not_recorded')

class DisorderDecisionTests(unittest.TestCase):
    def test_nonfinite_R_not_promoted(self):
        trials=[{'name':str(v),'status':'screen_complete','metrics':{'R1_observed':v}} for v in [float('nan'),float('inf'),-1,True,None]]
        chosen,decisions=screen_decisions(trials,1)
        self.assertEqual(chosen,[]);self.assertEqual(len(decisions),5)
    def test_chemistry_conflict_precedes_lower_R(self):
        bad={'name':'bad','status':'screen_complete','metrics':{'R1_observed':.01},'bond_review':{'findings':['short bond']}}
        good={'name':'good','status':'screen_complete','metrics':{'R1_observed':.06},'bond_review':{'findings':[]}}
        chosen,decisions=screen_decisions([bad,good],1)
        self.assertEqual(chosen[0]['name'],'good');self.assertEqual(decisions[-1]['decision'],'deferred_budget')
        self.assertTrue(all(d['AB'] is None for d in decisions))
    def test_internal_chain_axes_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            base=fixture(Path(td)/'chain','alkyl_chain',True)
            sites=[s for s in detect(base)['sites'] if s['family']=='alkyl_chain']
            self.assertTrue(any(len(s['atoms'])==3 for s in sites));self.assertTrue(any(len(s['atoms'])==2 for s in sites))
    def test_special_position_evidence_contains_operators(self):
        with tempfile.TemporaryDirectory() as td:
            base=fixture(Path(td)/'cf3');p=base/'case.res'
            # Move the assembled whole fragment so its axis carbon sits on inversion centre.
            doc=gemmi.cif.read_file(str(base/'case.cif'));b=doc.sole_block()
            shift=[float(b.find_values('_atom_site_fract_'+k)[1]) for k in 'xyz']
            parsed=res_records(p);text=p.read_text()
            for a in parsed['atoms']:
                old=' '.join(a['row']);new=list(a['row'])
                for i in range(3):new[2+i]=str(float(new[2+i])-shift[i])
                text=text.replace(old,' '.join(new))
            p.write_text(text)
            for i,k in enumerate('xyz'):
                values=b.find_values('_atom_site_fract_'+k)
                for j in range(len(values)):values[j]=str(float(values[j])-shift[i])
            doc.write_file(str(base/'case.cif'))
            s=next(x for x in detect(base)['sites'] if x['family']=='cf3')
            self.assertEqual(s['status'],'needs_review');self.assertEqual(s['next_tool'],'occupancy')
            self.assertTrue(any(x['stabilizer_order']==2 for x in s['special_position_evidence']))
    def test_no_finalist_skips_redundant_full_native_run(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base=root/'base';base.mkdir();out=root/'out';out.mkdir()
            plan={'output':str(out),'baseline':str(base),'settings':{},'software':{'shelxl':__file__,'platon':__file__},
                'software_hashes':{k:hashlib.sha256(Path(__file__).read_bytes()).hexdigest() for k in ['shelxl','platon']},
                'input_hashes':{},'implementation_hashes':{},'proposals':[],'sites':[],'native_resources':{},'preparation_seconds':.1}
            p=root/'plan.json';p.write_text(json.dumps(plan))
            with patch('density_disorder.run_plan') as native:
                result=run(p);native.assert_not_called()
            self.assertEqual(result['full_count'],0);self.assertIsNone(result['AB']);self.assertFalse(result['model_adopted'])

if __name__=='__main__':unittest.main()
