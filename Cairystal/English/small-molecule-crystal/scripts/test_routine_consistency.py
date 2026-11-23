import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gemmi
from routine_consistency import parse_formula, check_cif, check_instructions, audit_files, require_consistency, write_audit
from compare_ab_alerts import compare_reports, read_report, write_comparison
from crystal_runtime import sha


def cif(formula='H2 O',mr='18.0153',z='1',volume='1000',density='0.029915',f000='10'):
    return f'''data_synthetic
_chemical_formula_sum '{formula}'
_chemical_formula_weight {mr}
_cell_length_a 10.000(1)
_cell_length_b 10.000(1)
_cell_length_c 10.000(1)
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_cell_volume {volume}
_cell_formula_units_Z {z}
_exptl_crystal_density_diffrn {density}
_exptl_crystal_F_000 {f000}
_diffrn_ambient_temperature 293.15
_cell_measurement_temperature 293.15
'''

def check(text,native=''):
    return check_cif(gemmi.cif.read_string(text).sole_block(),native)

RES='''TITL Synthetic fixture, not a solved crystal
CELL .71073 10 10 10 90 90 90
ZERR 1 .001 .001 .001 .01 .01 .01
LATT -1
SFAC O H
UNIT 1 2
ACTA
TEMP 20
FVAR 1
O1 1 .2 .2 .2 11 .02
H1 2 .25 .2 .2 11 -1.2
H2 2 .2 .25 .2 11 -1.2
HKLF 4
END
WGHT .05 .7
'''


class Arithmetic(unittest.TestCase):
    def test_flat_fractional_and_compact_formula(self):
        self.assertEqual(parse_formula('C4 H16 Cl6 N2 Sn'),parse_formula('C4H16Cl6N2Sn'))
        self.assertEqual(parse_formula('C1.5 D2 C0.5'),{'C':2.,'D':2.})
    def test_unsupported_not_guessed(self):
        for f in ['?', '', 'C6 H6, H2 O', '(C2H5)2O', 'NH4+', 'C0', 'Xx2', 'CuSO4·5H2O', 'C 1 2']:
            with self.subTest(f=f),self.assertRaises(ValueError):parse_formula(f)
    def test_correct_arithmetic_has_no_findings(self):self.assertEqual(check(cif())['issues'],[])
    def test_table_inconsistency_detected(self):
        t=cif('C4H16Cl6N2Sn','423.58','2','777.14','2.113','480').replace('_cell_length_a 10.000(1)','_cell_length_a 7.2815(7)').replace('_cell_length_b 10.000(1)','_cell_length_b 7.3820(9)').replace('_cell_length_c 10.000(1)','_cell_length_c 14.458(2)')
        r=check(t);codes={i['code'] for i in r['issues']}
        self.assertIn('DENSITY',codes);self.assertIn('F000_ELECTRON_COUNT',codes)
        self.assertAlmostEqual(r['computed']['density_from_reported_Mr'],1.810153,places=5)
    def test_small_weight_table_difference_tolerated(self):self.assertNotIn('FORMULA_WEIGHT',{i['code'] for i in check(cif(mr='18.02'))['issues']})
    def test_real_formula_weight_error_flagged(self):self.assertIn('FORMULA_WEIGHT',{i['code'] for i in check(cif(mr='20'))['issues']})
    def test_missing_is_not_zero(self):
        r=check(cif(density='?'));self.assertIsNone(r['reported']['_exptl_crystal_density_diffrn']);self.assertIn('MISSING_VALUE',{i['code'] for i in r['issues']})
    def test_invalid_numeric_and_cell(self):
        for tag,value in [('_cell_volume','-1'),('_cell_angle_gamma','180'),('_cell_length_a','nan')]:
            import re
            t=re.sub(r'(?m)^'+tag+r' .+$',tag+' '+value,cif())
            self.assertTrue(any(i['severity']=='error' for i in check(t)['issues']))
    def test_mask_convention_not_false_error(self):
        r=check(cif(f000='12')+'\n_platon_squeeze_void_nr 1\n')
        self.assertIn('F000_CONVENTION',{i['code'] for i in r['issues']});self.assertNotIn('F000_ELECTRON_COUNT',{i['code'] for i in r['issues']})
    def test_special_scattering_convention(self):
        for card in ['ABIN','SWAT .1 3','DISP O 0.1 0.1','NEUT']:
            self.assertIn('F000_CONVENTION',{i['code'] for i in check(cif(),RES.replace('ACTA',card+'\nACTA'))['issues']})
    def test_formula_rescaling_preserves_density_and_f000(self):
        r=check(cif('H4 O2','36.0306','.5'))
        self.assertFalse(r['issues'])


class Instructions(unittest.TestCase):
    def test_acta_implies_list4(self):self.assertEqual(check_instructions(RES)['status'],'checks_passed')
    def test_list6_requires_review(self):self.assertIn('LIST4_REVIEW',{i['code'] for i in check_instructions(RES.replace('ACTA','ACTA\nLIST 6'))['issues']})
    def test_comment_and_post_end_not_active(self):
        t=RES.replace('ACTA','ACTA\nREM EXTI 1\n SWAT 1 2\n! EXTI 2')+'EXTI 1\nSWAT 1 2\n'
        self.assertNotIn('EXTI_SWAT_CONFLICT',{i['code'] for i in check_instructions(t)['issues']})
    def test_exti_swat_conflict(self):self.assertEqual(check_instructions(RES.replace('ACTA','ACTA\nEXTI .1\nSWAT .1 3'))['status'],'failed')
    def test_same_water_h_continuation(self):
        r=check_instructions(RES.replace('O1 1','SAME O1 H1 =\n  H2\nO1 1'))
        self.assertIn('SAME_IGNORES_H',{i['code'] for i in r['issues']})
    def test_duplicate_literal_omit_and_other_form(self):
        r=check_instructions(RES.replace('ACTA','ACTA\nOMIT 1 2 -3\nOMIT +1 2 -3\nOMIT -2 50'))
        self.assertEqual({i['code'] for i in r['issues']},{'DUPLICATE_OMIT','OMIT_SCOPE'})
        inv=next(c for c in r['checks'] if c['code']=='OMIT_INVENTORY');self.assertEqual(inv['distinct_literal_hkl'],1);self.assertTrue(inv['coverage_not_computed'])
    def test_external_include_not_read(self):self.assertIn('INCLUDE_NOT_READ',{i['code'] for i in check_instructions(RES.replace('ACTA','ACTA\n+answer.res'))['issues']})
    def test_unfinished_continuation(self):self.assertEqual(check_instructions('SAME C1 =')['status'],'failed')


class FilesAndGates(unittest.TestCase):
    def test_read_only_unicode_paths_and_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);c=p/'中文.cif';r=p/'本次.res';c.write_text(cif());r.write_text(RES)
            before=(sha(c),sha(r));result=audit_files(c,r);write_audit(result,p/'审计')
            self.assertEqual(result['status'],'checks_passed');self.assertEqual(before,(sha(c),sha(r)))
            self.assertEqual(json.loads((p/'审计/routine_consistency.json').read_text(encoding='utf-8'))['ai_calls'],0)
            with self.assertRaises(ValueError):write_audit(result,p/'审计')
    def test_multiblock_fails_not_first_block_chosen(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.cif';p.write_text(cif()+cif().replace('data_synthetic','data_other'));self.assertEqual(audit_files(p)['status'],'failed')
    def test_embedded_res_is_checked_without_reading_includes(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.cif';p.write_text(cif()+'\n_shelx_res_file\n;\n'+RES.replace('ACTA','ACTA\nEXTI .1\nSWAT .1 2')+';\n')
            result=audit_files(p);self.assertEqual(result['native_source'],'embedded_RES');self.assertEqual(result['status'],'failed')
    def test_uncertain_only_stops_automatic_acceptance(self):
        r={'issues':[{'code':'FORMULA_UNSUPPORTED','severity':'review'}]}
        require_consistency(r)
        with self.assertRaises(ValueError):require_consistency(r,automatic=True)
    def test_definite_errors_stop_all_paths(self):
        for auto in [True,False]:
            with self.assertRaises(ValueError):require_consistency({'issues':[{'code':'DENSITY','severity':'error'}]},automatic=auto)


def official(rows):
    counts={k:sum('_'+k+' ' in r for r in rows) for k in 'ABCG'}
    return 'Structure factors have been supplied for datablock synthetic\nNo syntax errors found\n'+'\n'.join(rows)+'\n'+'\n'.join(f'{counts[k]} ALERT level {k} = summary' for k in 'ABCG')+'\n'


class AlertComparison(unittest.TestCase):
    def pair(self,p,a,b):
        (p/'before.txt').write_text(a);(p/'after.txt').write_text(b)
        return compare_reports(p/'before.txt',p/'after.txt')
    def test_duplicate_alerts_and_downgrade_retained(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);row='PLAT972_ALERT_2_B negative peak'
            r=self.pair(p,official([row,row,'PLAT080_ALERT_2_A shift']),official([row,'PLAT080_ALERT_2_C shift']))
            self.assertEqual(sum(x['occurrences'] for x in r['unchanged_entries']),1)
            self.assertEqual(sum(x['occurrences'] for x in r['before_only_entries']),2)
            self.assertEqual(next(x for x in r['code_counts'] if x['code']=='080')['after']['C'],1)
            self.assertFalse(r['model_pairing_verified'])
    def test_changed_text_not_called_same_or_fixed(self):
        with tempfile.TemporaryDirectory() as td:
            r=self.pair(Path(td),official(['PLAT972_ALERT_2_B peak -2.0']),official(['PLAT972_ALERT_2_B peak -1.9']))
            self.assertEqual(len(r['before_only_entries']),1);self.assertEqual(len(r['after_only_entries']),1)
    def test_empty_truncated_and_mismatched_counts_rejected(self):
        for text in ['', 'PLAT972_ALERT_2_B peak', official([]).replace('0 ALERT level B','1 ALERT level B')]:
            with tempfile.TemporaryDirectory() as td:
                p=Path(td)/'bad.txt';p.write_text(text)
                with self.assertRaises(ValueError):read_report(p)
    def test_mixed_scope_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            local='ALERT_Level and ALERT_Type Summary\n0 ALERT_Level_A = none\n'
            with self.assertRaises(ValueError):self.pair(Path(td),local,official([]))
    def test_local_zero_and_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            head='ALERT_Level and ALERT_Type Summary\n'
            r=self.pair(Path(td),'972_ALERT_2_B peak\n'+head+'1 ALERT_Level_B = review\n',head+'0 ALERT_Level_A = none\n')
            self.assertEqual(r['before']['counts']['B'],1);self.assertEqual(r['after']['counts']['B'],0)
    def test_html_escape_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);r=self.pair(p,official(['PLAT972_ALERT_2_B <script>unsafe</script>']),official([]));write_comparison(r,p/'out')
            html=(p/'out/index.html').read_text(encoding='utf-8');self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
            with self.assertRaises(ValueError):write_comparison(r,p/'out')


class Integration(unittest.TestCase):
    def test_finish_stops_before_native_or_validation_on_arithmetic_error(self):
        import routine_finish
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);cfg=p/'config.json';bad={'issues':[{'code':'DENSITY','severity':'error'}],'status':'failed'}
            cfg.write_text(json.dumps({'candidate':str(p),'review':{'chemistry_and_h_reviewed':True,'basis':'synthetic test'}}))
            with patch.object(routine_finish,'paired_bundle',return_value={'routine_checks':bad,'gate':{'review_reasons':[]}}),patch.object(routine_finish,'native_run') as native,patch.object(routine_finish,'local_validation') as validator:
                state,out=routine_finish.finish(cfg,p/'run')
            self.assertEqual(state['status'],'failed');self.assertTrue((out/'routine_consistency.json').is_file());native.assert_not_called();validator.assert_not_called()
    def test_direct_delivery_stops_before_iucr_and_report_on_error(self):
        import crystal_delivery
        import contextlib,io
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);notes=p/'notes.json';notes.write_text('{}')
            bad={'issues':[{'code':'DENSITY','severity':'error'}],'status':'failed'}
            audit={'routine_checks':bad,'source_sha256':{},'files':{},'gate':{'metrics':{}}}
            a=argparse.Namespace(output=str(p/'run'),notes=str(notes),input=str(p),stem='model',metadata_source=None)
            with patch.object(crystal_delivery,'paired_bundle',return_value=audit),patch.object(crystal_delivery,'freeze_bundle'),patch('report_preflight.review_contacts',return_value={}),patch('cif_text_preflight.encode_narratives',return_value={}),patch('cif_text_preflight.add_assistance_comment',return_value={}),patch('iucr_validation.validate') as official_call,patch('bilingual_report.build_reports') as reports,contextlib.redirect_stdout(io.StringIO()):
                rc=crystal_delivery.run(a)
            self.assertEqual(rc,1);official_call.assert_not_called();reports.assert_not_called()
            self.assertEqual(json.loads((p/'run/routine_consistency.json').read_text())['status'],'failed')


if __name__=='__main__':unittest.main()
