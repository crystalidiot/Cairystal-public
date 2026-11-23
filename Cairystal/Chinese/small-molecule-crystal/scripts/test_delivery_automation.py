import argparse,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import gemmi
from crystal_runtime import *
from iucr_validation import parse_official_text,check_url,validate_saved,OPTIONS
from crystal_delivery import finalize
from bilingual_report import extract

INS='''TITL synthetic
CELL .71073 10 10 10 90 90 90
ZERR 1 .001 .001 .001 .01 .01 .01
LATT -1
SFAC C H
UNIT 1 0
FVAR 1
C1 1 .1 .2 .3 11 .02
HKLF 4
END
WGHT .2 .3
'''

def atom_cif(x='.10000',element='C',occ='1',u='.02000',adp='Uiso'):
    return gemmi.cif.read_string(f'''data_x
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
_atom_site_U_iso_or_equiv
_atom_site_adp_type
C1 {element} {x} .20000 .30000 {occ} {u} {adp}
''').sole_block()

OCC={'atoms':[{'label':'C1','element':'C','residue':'0','xyz':[.1,.2,.3],'inferred_cif_occupancy':1,'sof_serialization_rounding_bound':.000005}]}

class RuntimeTests(unittest.TestCase):
    def test_active_records_ignore_suggestions(self):
        self.assertEqual(canonical(INS),canonical(INS.replace('WGHT .2 .3','WGHT .5 .7')))
    def test_active_change_not_equal(self):self.assertNotEqual(canonical(INS),canonical(INS.replace('.02\nHKLF','.03\nHKLF')))
    def test_unit_before_sfac_rejected(self):
        with self.assertRaises(ValueError):check_instructions(INS.replace('SFAC C H\nUNIT 1 0','UNIT 1 0\nSFAC C H'))
    def test_hkl5_declined(self):
        with self.assertRaises(ValueError):check_instructions(INS.replace('HKLF 4','HKLF 5'))
    def test_include_declined(self):
        with self.assertRaises(ValueError):check_instructions(INS.replace('FVAR 1','+external.ins\nFVAR 1'))
    def test_negative_intensity_retained(self):
        line=f'{1:4}{0:4}{0:4}{-2.4:8.2f}{1.5:8.2f}{2:4}'
        self.assertEqual(read_hkl(line)[0],(1,0,0,-2.4,1.5,2))
    def test_hkl_batch_matters(self):
        base=f'{1:4}{0:4}{0:4}{10:8.2f}{1:8.2f}'
        self.assertNotEqual(read_hkl(base+'   1'),read_hkl(base+'   2'))
    def test_nan_intensity_rejected(self):
        with self.assertRaises(ValueError):read_hkl(f'{1:4}{0:4}{0:4}{"nan":>8}{1:8.2f}')
    def test_nan_cif_rejected(self):
        for val in ['?','.','nan']:
            with self.assertRaises(ValueError):number(val)
    def test_serialization_exponent_not_su_controls_tolerance(self):
        self.assertAlmostEqual(cif_tolerance('1.230(99)e-2'),cif_tolerance('0.01230(1)'))
        self.assertLess(cif_tolerance('1.230(99)e-2'),.000006)
    def test_existing_directory_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):new_directory(d)
    def test_correct_atom_matches(self):compare_atom_loop(atom_cif(),OCC,INS)
    def test_coordinate_mismatch(self):
        with self.assertRaises(ValueError):compare_atom_loop(atom_cif(x='.11'),OCC,INS)
    def test_legitimate_coordinate_rounding(self):
        altered=INS.replace('.1 .2 .3','.10049 .2 .3');occ=json.loads(json.dumps(OCC));occ['atoms'][0]['xyz'][0]=.10049
        compare_atom_loop(atom_cif(x='.100'),occ,altered)
    def test_symmetry_operation_mismatch_visible(self):
        a=gemmi.cif.read_string("data_x\nloop_\n_space_group_symop_operation_xyz\n'x,y,z'\n'-x,-y,-z'\n").sole_block()
        b=gemmi.cif.read_string("data_x\nloop_\n_space_group_symop_operation_xyz\n'x,y,z'\n").sole_block()
        self.assertNotEqual(symmetry_operations(a),symmetry_operations(b))
    def test_element_mismatch(self):
        with self.assertRaises(ValueError):compare_atom_loop(atom_cif(element='N'),OCC,INS)
    def test_occupancy_mismatch(self):
        with self.assertRaises(ValueError):compare_atom_loop(atom_cif(occ='.5'),OCC,INS)
    def test_iso_tensor_mismatch(self):
        with self.assertRaises(ValueError):compare_atom_loop(atom_cif(adp='Uani'),OCC,INS)
    def test_uiso_mismatch(self):
        with self.assertRaises(ValueError):compare_atom_loop(atom_cif(u='.09'),OCC,INS)
    def test_missing_adp_loop_rejected(self):
        b=atom_cif();b.find_loop('_atom_site_adp_type').erase()
        with self.assertRaises(ValueError):compare_atom_loop(b,OCC,INS)
    def test_cell_and_wavelength_match(self):
        b=gemmi.cif.read_string('data_x\n_diffrn_radiation_wavelength .71073\n_cell_length_a 10\n_cell_length_b 10\n_cell_length_c 10\n_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n').sole_block()
        compare_cell(b,INS)
        for tag in ['_cell_length_a','_diffrn_radiation_wavelength']:
            original=b.find_value(tag);b.set_pair(tag,'11.12345')
            with self.assertRaises(ValueError):compare_cell(b,INS)
            b.set_pair(tag,original)

REPORT='''Structure factors have been supplied for datablock x
No syntax errors found
PLAT972_ALERT_2_B negative peak one
PLAT972_ALERT_2_B negative peak two
0 ALERT level A = none
2 ALERT level B = review
0 ALERT level C = none
0 ALERT level G = none
'''
class OfficialTests(unittest.TestCase):
    def test_repeated_alert_codes_retained(self):self.assertEqual(len(parse_official_text(REPORT)['alerts']),2)
    def test_missing_footer_not_zero_alerts(self):
        with self.assertRaises(ValueError):parse_official_text(REPORT.split('0 ALERT level A')[0])
    def test_wrong_alert_count_rejected(self):
        with self.assertRaises(ValueError):parse_official_text(REPORT.replace('2 ALERT level B','1 ALERT level B'))
    def test_no_structure_factors_rejected(self):
        with self.assertRaises(ValueError):parse_official_text(REPORT.replace('Structure factors have been supplied','CIF only'))
    def test_unrelated_host_rejected(self):
        for url in ['http://checkcif.iucr.org/a','https://checkcif.iucr.org.example/a','file:///answer.cif']:
            with self.assertRaises(ValueError):check_url(url)
    def test_cache_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            write_json(Path(d)/'submission.json',{'schema':1,'cif_sha256':'old','options':OPTIONS})
            with self.assertRaisesRegex(ValueError,'hash'):validate_saved(d,'new')
    def test_no_qa_no_finalize(self):
        with tempfile.TemporaryDirectory() as d:
            write_json(Path(d)/'result.json',{'status':'awaiting_visual_review'})
            a=argparse.Namespace(run=d,reviewed_zh=False,reviewed_en=True,reviewed_official=True,review_note='incomplete')
            with self.assertRaises(ValueError):finalize(a)
            self.assertFalse((Path(d)/'structure_and_reports.zip').exists())
    def test_changed_delivery_blocks_finalize(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'delivery').mkdir();(p/'delivery/x').write_text('changed')
            write_json(p/'result.json',{'status':'awaiting_visual_review','delivery_seal':{'x':'originalhash'}})
            a=argparse.Namespace(run=d,reviewed_zh=True,reviewed_en=True,reviewed_official=True,review_note='reviewed')
            with self.assertRaisesRegex(ValueError,'changed'):finalize(a)

if __name__=='__main__':unittest.main()
