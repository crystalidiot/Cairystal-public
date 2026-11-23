import unittest,math,tempfile,json
from pathlib import Path
from resolution_shells import partition,summarize
from parameter_correlations import parse_lst,identify
from population_stability import context,edit,summarize as stability_summary
from restraint_strength import variants as strength_variants
from solver_fallback import header,configuration,make_ins,cascade,fallback_reason

def row(d,fo=100,fc=81,sigma=5,status='o',weighted=2):
    return dict(d_A=d,Fo2=fo,Fc2=fc,sigma_Fo2=sigma,status=status,delta_over_sigmaW=weighted)

class ShellTests(unittest.TestCase):
    def test_endpoint_count_conservation(self):
        rows=[row(4),row(2),row(1),row(.5,status='x')];v=partition(rows,3)
        self.assertEqual(sum(x['FCF_rows'] for x in v),4);self.assertEqual(sum(x['active_rows'] for x in v),3)
        self.assertEqual(v[-1]['excluded_rows'],1)
    def test_empty_shells_and_missing_weights_stay_null(self):
        v=partition([row(4,weighted=None),row(1,weighted=None)],6)
        empty=next(x for x in v if not x['FCF_rows']);self.assertIsNone(empty['weighted_rms'])
        self.assertIsNone(v[0]['weighted_gt10_count']);self.assertIsNone(v[0]['theoretical_completeness'])
    def test_negative_intensities_and_excluded_outliers(self):
        v=summarize([row(2,fo=-10,fc=4),row(1,fo=1000,status='x',weighted=100)])
        self.assertEqual(v['negative_intensity_fraction'],1);self.assertEqual(v['mean_I_over_sigma'],-2)
        self.assertEqual(v['weighted_gt10_count'],0);self.assertIsNone(v['R1_all_available_FCF'])
    def test_shell_R1_definition(self):self.assertAlmostEqual(summarize([row(1)])['R1_all_available_FCF'],.1)
    def test_single_resolution_and_invalid_bins(self):
        self.assertEqual(len(partition([row(1),row(1)],6)),1)
        for n in [True,0,30,2.5]:
            with self.assertRaises(ValueError):partition([row(1)],n)
        with self.assertRaises(ValueError):partition([],6)

class CorrelationTests(unittest.TestCase):
    def test_all_printed_columns_are_read(self):
        v=parse_lst('Largest correlation matrix elements\n\n 0.51 x C1 / y C1    -0.97 FVAR 2 / U11 C2    0.55 z C2 / y C2\n\nOther output\n')
        self.assertEqual(len(v['pairs']),3);self.assertEqual(v['max_absolute'],.97)
        self.assertEqual(v['pairs'][0]['coefficient'],-.97);self.assertEqual(v['pairs'][0]['left'],'FVAR 2')
    def test_last_section_and_unknown_are_distinct(self):
        self.assertIsNone(parse_lst('no section')['max_absolute'])
        v=parse_lst('Largest correlation matrix elements\n0.99 x C1 / y C1\n\nLargest correlation matrix elements\n0.51 x C2 / z C2\n\n')
        self.assertEqual(v['max_absolute'],.51)
    def test_malformed_and_out_of_range_not_zero(self):
        for text in [' 0.99 broken',' 1.2 x C1 / y C1']:
            self.assertEqual(parse_lst('Largest correlation matrix elements\n'+text)['status'],'partial_parse')
    def test_duplicate_atom_context_not_guessed(self):
        parsed={'atoms':[dict(label='C1',part=p,residue='0',element='C') for p in [1,2]]}
        v=identify('x C1',parsed);self.assertEqual(v['identity'],'ambiguous_atom');self.assertEqual(v['category'],'coordinate')
    def test_secondary_column_blocks_unsafe_continuation(self):
        from convergence_trend import analyse,ONLY_REASON
        text='\n'.join('Mean shift/esd = 0 Maximum = '+str(v)+' for x C1' for v in [.16,.12,.08,.04])
        text+='\nLargest correlation matrix elements\n 0.51 x C1 / y C1     -0.99 z C1 / y C1\n\n'
        gate=dict(execution_complete=True,failures=[],metrics={'NPD_atoms':0,'last_abs_max_shift_esd':.04},review_reasons=[ONLY_REASON])
        v=analyse(text,gate,'L.S. 20');self.assertFalse(v['eligible']);self.assertEqual(v['max_reported_correlation'],.99)

class PopulationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.d=Path(self.temp.name)
        from test_repair_plan import fixture
        fixture(self.d);p=self.d/'case.res';t=p.read_text('ascii')
        t=t.replace('FVAR 1','FVAR 1 .5').replace('C1 1 .2 .2 .2 11 .04 .04 .04 0 0 0','PART 1\nC1A 1 .2 .2 .2 21 .04\nPART 2\nC1B 1 .25 .23 .21 -21 .04\nPART 0')
        p.write_text(t,'ascii');self.text=t
    def test_only_requested_FVAR_changes(self):
        out,changes=edit(self.d,dict(fvar_index=2,value=.2,basis='Current two-site model'))
        from crystal_runtime import records
        self.assertEqual([r for r in records(out) if r[0]!='FVAR'],[r for r in records(self.text) if r[0]!='FVAR'])
        self.assertIn('FVAR 1 0.2',out);self.assertEqual(changes[0]['population_start']['current_value'],.5)
        self.assertEqual((self.d/'case.res').read_text('ascii'),self.text)
    def test_reject_unbalanced_and_special_coefficients(self):
        for token in ['C1B 2 .25 .23 .21 -21','C1B 1 .25 .23 .21 -20.5']:
            (self.d/'case.res').write_text(self.text.replace('C1B 1 .25 .23 .21 -21',token),'ascii')
            with self.assertRaises(ValueError):context(self.d,2)
    def test_coordinate_or_ADP_shared_variable_rejected(self):
        (self.d/'case.res').write_text(self.text.replace('N1 3 .3 .4 .5 11','N1 3 20.3 .4 .5 11'),'ascii')
        with self.assertRaises(ValueError):context(self.d,2)
    def test_global_population_coupling_rejected(self):
        (self.d/'case.res').write_text(self.text.replace('FVAR 1','SUMP 1 .01 1 2\nFVAR 1'),'ascii')
        with self.assertRaises(ValueError):context(self.d,2)
    def test_implicit_PART_population_override_not_ignored(self):
        (self.d/'case.res').write_text(self.text.replace('PART 1','PART 1 21'),'ascii')
        with self.assertRaises(ValueError):context(self.d,2)
    def test_incomplete_runs_not_stable(self):
        v=stability_summary([{'name':'control','status':'failed'}],self.d,2)
        self.assertEqual(v['status'],'needs_review');self.assertIsNone(v['population_range'])
        self.assertFalse(v['model_adopted'])

class StrengthTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.d=Path(self.temp.name)
        from test_repair_plan import fixture
        fixture(self.d)
    def add(self,card):
        p=self.d/'case.res';p.write_text(p.read_text('ascii').replace('FVAR 1',card+'\nFVAR 1'),'ascii')
    def test_distance_target_and_atoms_do_not_change(self):
        self.add('DFIX 1.40 .02 C1 O1');v=strength_variants(self.d,'DFIX 1.40 .02 C1 O1',[.5,2])
        self.assertEqual(v[0]['replacement'],'DFIX 1.4 0.01 C1 O1');self.assertEqual(v[1]['replacement'],'DFIX 1.4 0.04 C1 O1')
    def test_SIMU_cutoff_unchanged_both_sigmas_scale(self):
        self.add('SIMU .04 .08 1.7 C1 C2');v=strength_variants(self.d,'SIMU .04 .08 1.7 C1 C2',[.5,2])
        self.assertEqual(v[0]['replacement'],'SIMU 0.02 0.04 1.7 C1 C2')
        self.assertEqual(v[1]['replacement'],'SIMU 0.08 0.16 1.7 C1 C2')
    def test_implicit_sigmas_and_global_selectors_rejected(self):
        for card in ['SIMU C1 C2','SIMU .04 .08 1.7 $C','DFIX 1.4 C1 O1']:
            self.add(card)
            with self.assertRaises(ValueError):strength_variants(self.d,card,[.5,2])
    def test_one_sided_tightening_or_extreme_sigma_rejected(self):
        self.add('DFIX 1.4 .005 C1 O1')
        for factors in [[.5,.75],[.5,2],[1,2],[.1,2]]:
            with self.assertRaises(ValueError):strength_variants(self.d,'DFIX 1.4 .005 C1 O1',factors)
    def test_multiple_identical_cards_do_not_remove_all(self):
        self.add('SADI .02 C1 O1 C2 N1');self.add('SADI .02 C1 O1 C2 N1')
        with self.assertRaises(ValueError):strength_variants(self.d,'SADI .02 C1 O1 C2 N1',[.5,2])
    def test_compiled_trial_preserves_data_and_atom_records(self):
        from repair_plan import compile_trials
        from candidate_trials import build,controls,IMMUTABLE
        self.add('DFIX 1.4 .02 C1 O1');before=(self.d/'case.res').read_text('ascii')
        req=dict(recipe='restraint_strength',parameters={'instruction':'DFIX 1.4 .02 C1 O1','factors':[.5,2],'basis':'Test existing chemical hypothesis'},reason='Test sigma variation',evidence=['Synthetic fixture'])
        plans=compile_trials(self.d,req);after,_=build(self.d,plans[1],self.d)
        self.assertEqual(controls(before,IMMUTABLE),controls(after,IMMUTABLE));self.assertIn('DFIX 1.4 0.01 C1 O1',after)

class FallbackTests(unittest.TestCase):
    TEXT='TITL synthetic header\nCELL .71073 8 9 10 90 98 90\nZERR 1 .001 .001 .001 .01 .01 .01\nLATT -1\nSFAC C N O\nUNIT 4 1 1\nTREF\nHKLF 4\nEND\n'
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.d=Path(self.temp.name)
        (self.d/'raw.ins').write_text(self.TEXT,'ascii');(self.d/'raw.hkl').write_text('raw input placeholder for mocked runner','ascii')
        (self.d/'shelxd.exe').write_bytes(b'not executable; mocked native runner')
        self.hyp=dict(space_group='P 1',find=6,ntry=10,basis='Synthetic known setting and declared count hypothesis')
    def runner(self,primary_success=False,environment_error=False):
        def run(a):
            d=Path(a.output);d.mkdir();is_t=Path(a.executable).stem=='shelxt'
            ok=not is_t or primary_success
            result=dict(success=ok,returncode=0,process_state='finished',candidate_outputs=[])
            if environment_error and is_t:result.update(success=False,error='Synthetic missing DLL')
            elif ok:
                (d/'model.res').write_text(self.TEXT.replace('TREF','C1 1 .23 .34 .45 11 .04'),'ascii');result['candidate_outputs']=['model.res']
            (d/'attempt.json').write_text(json.dumps(result),'utf8');return 0 if ok else 1
        return run
    def test_failed_T_runs_D_preserving_inputs(self):
        v=cascade(self.d/'raw.ins',self.d/'raw.hkl','shelxt.exe',self.d/'shelxd.exe',self.d/'run',{'hypotheses':[self.hyp]},self.runner())
        self.assertEqual(v['candidates'][0]['program'],'SHELXD');self.assertEqual(len(v['fallback']['attempts']),1)
        self.assertTrue(v['source_unchanged']);self.assertEqual((self.d/'raw.ins').read_text('ascii'),self.TEXT)
    def test_successful_T_does_not_run_D(self):
        v=cascade(self.d/'raw.ins',self.d/'raw.hkl','shelxt.exe',self.d/'shelxd.exe',self.d/'run',{'hypotheses':[self.hyp]},self.runner(True))
        self.assertNotIn('fallback',v);self.assertEqual(v['candidates'][0]['program'],'SHELXT')
    def test_environment_error_stops_futile_fallback(self):
        v=cascade(self.d/'raw.ins',self.d/'raw.hkl','shelxt.exe',self.d/'shelxd.exe',self.d/'run',{'hypotheses':[self.hyp]},self.runner(environment_error=True))
        self.assertEqual(v['status'],'software_environment_failure');self.assertNotIn('fallback',v)
        self.assertEqual(fallback_reason({'returncode':-1073741515},0),'blocked_environment_or_input')
    def test_default_higher_symmetry_needs_hypothesis_not_guessed(self):
        cfg=configuration(self.TEXT.replace('LATT -1','LATT 1\nSYMM -X,Y+1/2,-Z+1/2'))
        self.assertEqual(cfg['hypotheses'],[])
    def test_coordinate_input_is_rejected(self):
        with self.assertRaises(ValueError):header(self.TEXT.replace('TREF','C1 1 .2 .3 .4 11 .04'))
    def test_nonphysical_cell_rejected(self):
        with self.assertRaises(ValueError):header(self.TEXT.replace('8 9 10 90 98 90','-8 -9 10 90 98 90'))
    def test_elements_preserve_order_and_counts_are_explicit(self):
        t=make_ins(self.TEXT,self.hyp);self.assertIn('SFAC C N O',t);self.assertIn('UNIT 4 1 1',t)
        self.assertIn('FIND 6',t);self.assertIn('NTRY 10',t);self.assertNotIn('SHEL ',t)
    def test_incompatible_group_or_unbounded_search_rejected(self):
        for fields in [dict(space_group='P m -3 m'),dict(ntry=0),dict(find=True),dict(unit=[1,1]),dict(basis='')]:
            with self.assertRaises(ValueError):make_ins(self.TEXT,dict(self.hyp,**fields))
    def test_unsupported_output_does_not_count_as_model(self):
        from solver_fallback import candidate
        p=self.d/'empty.res';p.write_text(self.TEXT,'ascii');v=candidate(p,header(self.TEXT)['cell'],['C','N','O'])
        self.assertEqual(v['status'],'unusable_output')
    def test_timeout_allows_bounded_alternative(self):
        self.assertEqual(fallback_reason({'returncode':-1,'process_state':'timeout'},0),'try_supported_SHELXD_hypotheses')
    def test_mainline_hands_SHELXD_peaks_to_assignment_not_final_refinement(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        import contextlib,io
        from crystal_session import start
        for name in ['shelxt.exe','shelxl.exe']:(self.d/name).write_bytes(b'mocked executable')
        p4p=self.d/'raw.p4p';p4p.write_text('FILEID SYNTHETIC REGRESSION\nCELL 8 9 10 90 98 90\nCELLSD .001 .001 .001 .01 .01 .01\nSOURCE Mo .71073\nBRAVAIS Triclinic P\n','ascii')
        def failed_t(root,name,*args,**kwargs):
            self.assertEqual(kwargs['timeout'],123)
            stage=root/'stages'/name;stage.mkdir();(stage/'attempt.json').write_text(json.dumps({'success':False,'returncode':0,'process_state':'finished','candidate_outputs':[]}),'utf8')
            raise ValueError('Synthetic primary no-result')
        fallback={'status':'candidates_require_refinement_and_review','candidates':[{'path':'synthetic-peak.res','program':'SHELXD'}]}
        a=SimpleNamespace(hkl=str(self.d/'raw.hkl'),p4p=str(p4p),output=str(self.d/'session'),elements=['C','N','O'],shelxt=str(self.d/'shelxt.exe'),shelxl=str(self.d/'shelxl.exe'),shelxd=str(self.d/'shelxd.exe'),prior_conversation_exposure=False)
        config=self.d/'search.json';config.write_text(json.dumps({'primary_timeout_seconds':123,'timeout_seconds':234,'hypotheses':[self.hyp]}),'utf8');a.solver_fallback=str(config)
        with patch('crystal_session.execute',side_effect=failed_t),patch('solver_fallback.run_fallback',return_value=fallback) as execute_d,contextlib.redirect_stdout(io.StringIO()):start(a)
        self.assertEqual(execute_d.call_count,1)
        self.assertEqual(execute_d.call_args.args[-1]['timeout_seconds'],234)
        summary=json.loads((self.d/'session/start_summary.json').read_text('utf8'))
        self.assertEqual(summary['candidates'],[]);self.assertEqual(len(summary['solver_handoff']['unrefined_candidates']),1)
        self.assertEqual(json.loads((self.d/'session/session.json').read_text('utf8'))['solution_program'],'SHELXD')

if __name__=='__main__':unittest.main()
