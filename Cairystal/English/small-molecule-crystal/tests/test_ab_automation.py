import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ab_auto import generate_requests,load_policy,rank_rows
from cif_format_check import inspect,require

def packet(code='214',labels=('C1',)):
    atoms=[{'label':n,'res_label':n,'element':e,'part':0,'residue':'0','occupancy':1.,'res_context_status':'matched','adp_type':'ANI'} for n,e in [('C1','C'),('C2','C'),('O1','O'),('H1','H')]]
    neighbor={'label':'C2','element':'C','part_compatible':True,'within_covalent_radius_screen':True,'symmetry':'x,y,z','translation':[0,0,0],'distance':1.4}
    p={'all_atoms':atoms,'regions':[dict(a,neighbors=[neighbor] if a['label']=='C1' else [],nearby_reported_Q_peaks=[]) for a in atoms],
       'AB_alerts':[{'code':code,'level':'B','type':2,'text':'Synthetic alert','atom_labels':list(labels)}],'last_shifts':[]}
    parsed={'sfac':['C','O','N','H'],'atoms':[{'label':n,'element':e,'afix':147 if e=='H' else 0} for n,e in [('C1','C'),('C2','C'),('O1','O'),('H1','H')]]}
    return p,parsed

class RoutingTests(unittest.TestCase):
    def route(self,p,r):return generate_requests(p,r,load_policy())
    def test_single_adp_candidate(self):
        p,r=packet();req,findings=self.route(p,r);self.assertEqual(req[0]['parameters']['methods'],['ISOR']);self.assertEqual(findings[0]['status'],'hypothesis_ready')
    def test_partial_disorder_is_not_hidden_by_isor(self):
        p,r=packet();p['all_atoms'][0]['occupancy']=.4
        req,f=self.route(p,r);self.assertFalse(req);self.assertIn('Partial/disordered',f[0]['reason'])
    def test_residual_peak_redirects_disorder_review(self):
        p,r=packet();p['regions'][0]['nearby_reported_Q_peaks']=[{'height':.9,'distance':.7}]
        req,f=self.route(p,r);self.assertFalse(req);self.assertIn('residual',f[0]['reason'])
    def test_ambiguous_labels_do_not_pick_one(self):
        p,r=packet(labels=('C1','C2'));req,f=self.route(p,r);self.assertFalse(req)
    def test_rigu_simu_separate_trials(self):
        p,r=packet('234',('C1','C2'));req,f=self.route(p,r);self.assertEqual(req[0]['parameters']['methods'],['RIGU','SIMU'])
    def test_pair_requires_bond_evidence(self):
        p,r=packet('234',('C1','C2'));p['regions'][0]['neighbors']=[]
        self.assertFalse(self.route(p,r)[0])
    def test_type_issue_blocks_restraint_but_offers_type_candidates(self):
        p,r=packet();p['AB_alerts'].append(dict(p['AB_alerts'][0],code='242'))
        req,f=self.route(p,r);self.assertEqual([x['recipe'] for x in req],['element_scan'])
    def test_never_introduce_element_absent_from_sfac(self):
        p,r=packet('242');r['sfac']=['C','O','H'];req,_=self.route(p,r);self.assertEqual(req[0]['parameters']['elements'],['C','O'])
    def test_metadata_missing_is_not_fabricated(self):
        p,r=packet('183',());req,f=self.route(p,r);self.assertFalse(req);self.assertEqual(f[0]['category'],'experimental_metadata')
    def test_unknown_alert_is_retained(self):
        p,r=packet('999',());req,f=self.route(p,r);self.assertFalse(req);self.assertEqual(f[0]['status'],'needs_evidence')
    def test_omit_not_automatically_triggered_by_code(self):
        p,r=packet('934',());self.assertFalse(self.route(p,r)[0])
    def test_h_freeze_requires_actual_shift_target(self):
        p,r=packet('080',());self.assertFalse(self.route(p,r)[0]);p['last_shifts']=[['.1','.2','tors H1']]
        req,_=self.route(p,r);self.assertEqual(req[0]['parameters']['parent'],'O1')
    def test_nonconverged_heavy_atom_not_frozen(self):
        p,r=packet('080',());p['last_shifts']=[['.1','.2','U11 C1']];self.assertFalse(self.route(p,r)[0])
    def test_oh_anchor_must_be_explicit(self):
        p,r=packet('420',('O1','H1'));self.assertFalse(self.route(p,r)[0])
        p['regions'][2]['neighbors']=[{'label':'C1','element':'C','part_compatible':True,'within_covalent_radius_screen':True,'symmetry':'x,y,z','translation':[0,0,0],'distance':1.4}]
        req,_=self.route(p,r);self.assertEqual(req[0]['parameters']['parent'],'O1');self.assertEqual(len(req[0]['parameters']['angles']),5)
    def test_duplicate_alert_not_duplicate_native_plan(self):
        p,r=packet();p['AB_alerts']*=2;req,f=self.route(p,r);self.assertEqual(len(req),1);self.assertEqual(len(f),2)
    def test_policy_rejects_unsafe_or_unknown_overrides(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'p.json'
            for v in [{'allow_automatic_final_model_acceptance':True},{'max_hypotheses':True},{'adp_sigma':.00001},{'cycles':1000},{'oh_angles':[float('nan')]}]:
                p.write_text(json.dumps(v));self.assertRaises(ValueError,load_policy,p)
    def test_policy_can_limit_cost_without_changing_science(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'p.json';p.write_text(json.dumps({'max_hypotheses':3,'automatic_candidates':False}));v=load_policy(p);self.assertEqual(v['max_hypotheses'],3);self.assertFalse(v['automatic_candidates'])
    def test_bad_candidate_zero_ab_never_outranks_sound_candidate(self):
        good={'name':'good','status':'completed','comparison_context_verified':True,'flags':[],'source_unchanged':True,'AB':[{'level':'B'}]}
        bad=dict(good,name='bad',flags=['non_positive_definite_ADP'],AB=[])
        ordered=rank_rows([bad,good]);self.assertEqual(ordered[0]['name'],'good');self.assertFalse(ordered[1]['eligible_for_priority'])
    def test_A_first_then_B(self):
        common={'status':'completed','comparison_context_verified':True,'flags':[],'source_unchanged':True}
        a=dict(common,name='A',AB=[{'level':'A'}]);b=dict(common,name='B',AB=[{'level':'B'}]*3)
        self.assertEqual(rank_rows([a,b])[0]['name'],'B')
    def test_failed_candidate_metrics_not_zero(self):
        row=rank_rows([{'status':'failed','AB':None}])[0];self.assertIsNone(row['AB_priority']);self.assertFalse(row['eligible_for_priority'])
    def test_unmapped_warning_does_not_claim_a_tool_found(self):
        p,r=packet('000',());_,f=self.route(p,r);self.assertIn('No executable route',f[0]['reason'])
    def test_stale_validation_blocks_native_execution(self):
        from ab_auto import resolve
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'baseline';base.mkdir();v=root/'validation';v.mkdir()
            (base/'model.cif').write_text('data_a\n_x 1\n')
            (v/'local_validation.json').write_text(json.dumps({'official':False,'input_sha256':{'cif':'stale'}}))
            with patch('crystal_runtime.paired_bundle',return_value={}),patch('candidate_trials.run_plan') as runner:
                result=resolve(base,'model',v,root/'out',{})
                self.assertEqual(result['status'],'failed');self.assertIn('different model',result['error']);runner.assert_not_called()
    def test_control_failure_stops_batch(self):
        from candidate_trials import run_plan
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);job={'baseline':str(root/'base'),'output':str(root/'out'),'software':{},'trials':[{'name':'control'},{'name':'candidate'}],'stop_on_control_failure':True}
            (root/'base').mkdir();(root/'base/input.txt').write_text('synthetic')
            p=root/'plan.json';p.write_text(json.dumps(job))
            def stub(base,out,*args):
                out.mkdir();v={'name':'control','status':'failed','elapsed_s':0};(out/'result.json').write_text(json.dumps(v));return v
            with patch('candidate_trials.analyse',return_value={}),patch('candidate_trials.execute',side_effect=stub) as native:
                results=run_plan(p);self.assertEqual(len(results),1);native.assert_called_once()
    def test_policy_forwarded_through_autorun(self):
        from crystal_autorun import arguments
        state={'options':{'max_weight_updates':4,'timeout':180,'deliver':False,'ab_policy':'external-policy.json'}}
        # arguments reads the frozen interpreter binding, not a PATH guess.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'inputs').mkdir();(root/'inputs/profile.json').write_text(json.dumps({'python':'python'}))
            state['options']['profile']=str(root/'inputs/profile.json')
            argv=arguments(root,state,'finish','model')
            self.assertIn('--ab-policy',argv);self.assertEqual(argv[argv.index('--ab-policy')+1],'external-policy.json')

class CifTests(unittest.TestCase):
    def setUp(self):self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name)/'test.cif'
    def tearDown(self):self.t.cleanup()
    def check(self,text,**kwargs):self.p.write_bytes(text.encode('utf-8'));return inspect(self.p,**kwargs)
    def test_unknown_nulls_quotes_semicolon_unchanged(self):
        text='data_a\n_foo ?\n_bar .\n_baz \'a # quoted value\'\n_note\n;multi\nline\n;\nloop_\n_x\n_y\n1 2\n'
        self.assertEqual(self.check(text)['status'],'format_checked');self.assertEqual(self.p.read_text(),text)
    def test_case_insensitive_duplicate_rejected(self):self.assertEqual(self.check('data_a\n_Foo 1\n_foo 2\n')['status'],'invalid')
    def test_bad_loop_rejected(self):self.assertEqual(self.check('data_a\nloop_\n_x\n_y\n1 2 3\n')['status'],'invalid')
    def test_missing_value_rejected(self):self.assertEqual(self.check('data_a\n_foo\n_bar 1\n')['status'],'invalid')
    def test_multiple_blocks_require_explicit_choice(self):
        text='data_a\n_x 1\ndata_b\n_x 2\n';self.assertEqual(self.check(text)['status'],'format_checked');self.assertEqual(self.check(text,require_single=True)['status'],'invalid')
    def test_cif2_not_silently_treated_as_cif1(self):self.assertEqual(self.check('#\\#CIF_2.0\ndata_a\n_x 1\n')['status'],'invalid')
    def test_unicode_rejected_at_submission_boundary(self):self.assertEqual(self.check('data_a\n_x 中文\n')['status'],'invalid')
    def test_long_line_rejected(self):self.assertEqual(self.check('data_a\n#'+'x'*2048+'\n')['status'],'invalid')
    def test_null_not_converted_to_zero(self):self.check('data_a\n_x ?\n_y .\n');require(self.p);self.assertIn('_x ?',self.p.read_text())
    def test_empty_rejected(self):self.assertEqual(self.check('')['status'],'invalid')
    def test_dictionaries_not_accepted_as_model_files(self):self.assertEqual(self.check('data_a\nsave_foo\n_x 1\nsave_\n')['status'],'invalid')
    def test_repeated_atom_labels_rejected(self):self.assertEqual(self.check('data_a\nloop_\n_atom_site_label\nC1\nC1\n')['status'],'invalid')
    def test_invalid_before_any_network_request(self):
        import iucr_validation
        self.check('data_a\n_Foo 1\n_foo 2\n')
        with patch.object(iucr_validation,'fetch') as network:
            with self.assertRaises(ValueError):iucr_validation.validate(self.p,Path(self.t.name)/'official',True)
            network.assert_not_called()

class QuietTests(unittest.TestCase):
    def test_hidden_windows_startup(self):
        import os,subprocess
        from native_process import hidden_kwargs
        value=hidden_kwargs()
        if os.name=='nt':self.assertEqual(value['startupinfo'].wShowWindow,subprocess.SW_HIDE);self.assertTrue(value['creationflags']&subprocess.CREATE_NO_WINDOW)
        else:self.assertEqual(value,{})

if __name__=='__main__':unittest.main(verbosity=2)
