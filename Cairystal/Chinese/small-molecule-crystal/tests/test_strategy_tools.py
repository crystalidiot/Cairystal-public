import copy,json,math,tempfile,unittest
from pathlib import Path
import gemmi
from geometry_audit import inspect,scalar_error
from parameter_budget import audit as budget
from refinement_controls import analyse,edit
from candidate_trials import build,controls,IMMUTABLE
from repair_plan import compile_trials
from route_problem import select_routes,normalize_alert
from ab_auto import generate_requests,load_policy
from test_repair_plan import fixture
from test_ab_automation import packet
from unittest.mock import patch
from repair_plan import run

ROOT=Path(__file__).resolve().parents[1]
class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.d=Path(self.temp.name);fixture(self.d)
    def block(self,extra=''):
        return gemmi.cif.read_string((self.d/'case.cif').read_text('ascii')+extra).sole_block()
    def write_extra(self,extra):
        p=self.d/'case.cif';p.write_text(p.read_text('ascii')+extra,encoding='ascii')
    def res_extra(self,extra):
        p=self.d/'case.res';p.write_text(p.read_text('ascii').replace('FVAR 1',extra+'\nFVAR 1'),encoding='ascii')
    def test_named_checks_normalize_and_resolve(self):
        data=json.loads((ROOT/'assets/console/workflow-data.json').read_text('utf8'))
        self.assertEqual(normalize_alert('SHFSU_01_ALERT_2_A'),'SHFSU01')
        for code,strategy in [('SHFSU01','convergence'),('REFNR01','parameter_budget'),('711','labels'),('WEIGH01','weights')]:
            got=select_routes(data,[code]);self.assertIn(strategy,{r.get('strategy_id') for r in got['routes']})
    def test_088_is_not_hydrogen_freeze_even_with_a_large_H_shift(self):
        p,r=packet('088');p['last_shifts']=[[.1,.2,'H1 z']]
        req,findings=generate_requests(p,r,load_policy())
        self.assertEqual(req,[]);self.assertIn('parameter-budget',findings[0]['tools'])
    def test_native_ratio_not_claimed_as_PLAT_ratio(self):
        self.write_extra('_refine_ls_number_parameters 20\n_refine_ls_number_reflns 140\n_refine_ls_number_restraints 8\n')
        v=budget(self.d);self.assertEqual(v['native_reflection_parameter_ratio'],7)
        self.assertIsNone(v['exact_PLAT_ratio']);self.assertEqual(v['reference_PLAT_target'],7)
        self.assertEqual(v['counts']['native_refined_parameters'],20)
    def test_missing_counts_stay_null(self):
        v=budget(self.d);self.assertIsNone(v['native_reflection_parameter_ratio'])
    def test_partial_H_without_PART_is_not_a_generic_free_H(self):
        p=self.d/'case.res';p.write_text(p.read_text('ascii').replace('AFIX 147','AFIX 0').replace('H1 4 .368 .279196 .2 11','H1 4 .368 .279196 .2 10.5'),'ascii')
        v=budget(self.d);self.assertEqual(v['free_general_H'],[])
        self.assertEqual([h['label'] for h in v['H_requiring_special_review']],['H1'])
    def test_negative_parameter_count_rejected(self):
        self.write_extra('_refine_ls_number_parameters -1\n')
        with self.assertRaises(ValueError):budget(self.d)
    def test_H0A_label_is_not_automatically_illegal(self):
        cif=(self.d/'case.cif').read_text('ascii').replace('H1 H','H0A H')
        b=gemmi.cif.read_string(cif+'loop_\n_geom_bond_atom_site_label_1\n_geom_bond_atom_site_label_2\n_geom_bond_distance\nO1 H0A 0.840\n').sole_block()
        self.assertEqual(inspect(b)['findings'],[])
    def test_reports_bond_mismatch_without_edit(self):
        b=self.block('loop_\n_geom_bond_atom_site_label_1\n_geom_bond_atom_site_label_2\n_geom_bond_distance\nC1 O1 9.00\n');before=b.as_string();v=inspect(b)
        self.assertEqual(v['checked_values'][0]['status'],'mismatch');self.assertAlmostEqual(v['checked_values'][0]['calculated'],1.4)
        self.assertEqual(before,b.as_string())
    def test_does_not_rename_unknown_geometry_label(self):
        v=inspect(self.block('loop_\n_geom_bond_atom_site_label_1\n_geom_bond_atom_site_label_2\n_geom_bond_distance\nC1 O99 1.4\n'))
        self.assertEqual(v['findings'][0]['kind'],'unresolved_geometry_identity')
    def test_question_symmetry_not_treated_as_identity(self):
        v=inspect(self.block('loop_\n_geom_bond_atom_site_label_1\n_geom_bond_atom_site_label_2\n_geom_bond_site_symmetry_2\n_geom_bond_distance\nC1 O1 ? 1.4\n'))
        self.assertIn('Unknown symmetry',v['findings'][0]['reason'])
    def test_explicit_translation_not_replaced_by_nearest_image(self):
        v=inspect(self.block('loop_\n_geom_bond_atom_site_label_1\n_geom_bond_atom_site_label_2\n_geom_bond_site_symmetry_2\n_geom_bond_distance\nC1 O1 1_655 1.4\n'))
        self.assertAlmostEqual(v['checked_values'][0]['calculated'],11.4)
        self.assertEqual(v['checked_values'][0]['status'],'mismatch')
    def test_degenerate_angle_is_unknown_not_zero(self):
        v=inspect(self.block('loop_\n_geom_angle_atom_site_label_1\n_geom_angle_atom_site_label_2\n_geom_angle_atom_site_label_3\n_geom_angle\nC1 C1 O1 0\n'))
        self.assertEqual(v['findings'][0]['kind'],'degenerate_geometry')
    def test_core_angle_and_torsion_tags_read_the_reported_values(self):
        from geometry_audit import read_context,point,measure
        b=self.block();cell,atoms,ops=read_context(b)
        angle=measure([point(n,None,cell,atoms,ops) for n in ['C1','O1','H1']])
        torsion=measure([point(n,None,cell,atoms,ops) for n in ['C2','C1','O1','H1']])
        extra='loop_\n_geom_angle_atom_site_label_1\n_geom_angle_atom_site_label_2\n_geom_angle_atom_site_label_3\n_geom_angle\nC1 O1 H1 '+str(angle)+'\n'
        extra+='loop_\n_geom_torsion_atom_site_label_1\n_geom_torsion_atom_site_label_2\n_geom_torsion_atom_site_label_3\n_geom_torsion_atom_site_label_4\n_geom_torsion\nC2 C1 O1 H1 '+str(torsion)+'\n'
        v=inspect(self.block(extra));self.assertEqual(v['checked_value_count'],2)
        self.assertEqual(v['findings'],[]);self.assertAlmostEqual(v['checked_values'][0]['reported'],angle)
        self.assertAlmostEqual(v['checked_values'][1]['reported'],torsion)
    def test_missing_geometry_value_stays_unknown(self):
        v=inspect(self.block('loop_\n_geom_bond_atom_site_label_1\n_geom_bond_atom_site_label_2\n_geom_bond_distance\nC1 O1 ?\n'))
        self.assertIsNone(v['checked_values'][0]['reported'])
    def test_standard_uncertainty_not_trailing_digits(self):
        self.assertAlmostEqual(scalar_error('1.234(12)e-2'),.00012)
        self.assertIsNone(scalar_error('?'))
    def test_missing_EXTI_su_not_zero(self):
        v=analyse('EXTI .001\nEND\n',gemmi.cif.read_string('data_t\n_refine_ls_extinction_coef .001\n').sole_block())
        self.assertIsNone(v['extinction']['absolute_value_over_su']);self.assertFalse(v['extinction']['remove_trial_supported'])
    def test_weak_EXTI_removal_only_changes_EXTI(self):
        self.res_extra('EXTI .001');self.write_extra('_refine_ls_extinction_coef 0.001(2)\n')
        req={'recipe':'remove_extinction','parameters':{'basis':'Synthetic weak coefficient'},'reason':'Compare model control','evidence':['Synthetic paired coefficient']}
        plans=compile_trials(self.d,req);before=(self.d/'case.res').read_text('ascii');after,changes=build(self.d,plans[1],self.d)
        self.assertNotIn('EXTI',after);self.assertEqual(controls(before,IMMUTABLE-{'EXTI'}),controls(after,IMMUTABLE-{'EXTI'}))
        self.assertEqual((self.d/'case.res').read_text('ascii'),before)
    def test_significant_EXTI_not_removed(self):
        self.res_extra('EXTI .1');self.write_extra('_refine_ls_extinction_coef 0.100(1)\n')
        with self.assertRaises(ValueError):edit(self.d,{'mode':'remove_extinction','basis':'synthetic'})
    def test_final_damping_removed_but_coordinates_unchanged(self):
        self.res_extra('DAMP .5 10');before=(self.d/'case.res').read_text('ascii')
        after,changes=edit(self.d,{'mode':'release_damping','basis':'Check final undamped fit'})
        self.assertEqual(after,before.replace('DAMP .5 10\n',''));self.assertEqual(len(changes),1)
    def test_no_arbitrary_SIZE_ZERR_WGHT_removal(self):
        for mode in ['SIZE','ZERR','WGHT','remove_extinction\nOMIT 1 2 3']:
            with self.assertRaises(ValueError):edit(self.d,{'mode':mode,'basis':'not permitted'})
    def test_subset_or_mask_not_misrepresented_as_full_final_refinement(self):
        self.res_extra('DAMP .5\nBLOC 1 2')
        with self.assertRaises(ValueError):edit(self.d,{'mode':'release_damping','basis':'test'})
    def test_resolution_preserves_raw_HKL_and_reports_information_loss(self):
        p=self.d/'case.hkl';p.write_text(''.join(f'{h:4d}{0:4d}{0:4d}{100:8.2f}{5:8.2f}\n' for h in [5,10,20,0]),encoding='ascii');before=p.read_bytes()
        after,changes=edit(self.d,{'mode':'resolution_window','d_min_A':.84,'basis':'Synthetic cutoff comparison'})
        self.assertIn('SHEL 999 0.840000',after);self.assertEqual(p.read_bytes(),before)
        evidence=changes[0]['resolution_inventory'];self.assertEqual(evidence['high_angle_records_outside_window'],1)
        self.assertEqual(evidence['within_requested_window'],2);self.assertIsNone(evidence['theoretical_completeness'])
        self.assertFalse(changes[0]['ranking_allowed'])
    def test_stacked_SHEL_not_silently_overwritten(self):
        self.res_extra('SHEL 999 .8')
        with self.assertRaises(ValueError):edit(self.d,{'mode':'resolution_window','d_min_A':.9,'basis':'test'})
    def test_resolution_request_rejects_nan(self):
        with self.assertRaises(ValueError):edit(self.d,{'mode':'resolution_window','d_min_A':float('nan'),'basis':'test'})
    def test_resolution_completed_trials_write_summary_without_fixed_hkls(self):
        request={'recipe':'resolution_window','parameters':{'d_min_A':.84,'basis':'Synthetic cutoff comparison'},'reason':'Test completion summary','evidence':['Synthetic engineering fixture']}
        output=self.d/'trials';output.mkdir()
        job={'schema':1,'recipe':'resolution_window','baseline':str(self.d),'output':str(output),'baseline_sha256':{},'implementation_sha256':{},'software':{},'trials':compile_trials(self.d,request)}
        path=self.d/'plan.json';path.write_text(json.dumps(job),'utf8');(self.d/'request.json').write_text(json.dumps(request),'utf8')
        results=[{'name':n,'status':'completed'} for n in ['control','resolution_window']]
        with patch('repair_plan.run_plan',return_value=results),patch('compare_diagnostic_trials.compare',return_value={'status':'completed'}):
            summary=run(path)
        saved=json.loads((output/'comparison.json').read_text('utf8'))
        self.assertEqual(saved,summary);e=summary['reflection_selection_comparison']
        self.assertIsNone(e['fixed_hkls']);self.assertEqual(e['d_min_A'],.84);self.assertFalse(e['ranking_allowed'])
        self.assertFalse(e['raw_HKL_changed']);self.assertEqual(len(e['cases']),2)

if __name__=='__main__':unittest.main()
