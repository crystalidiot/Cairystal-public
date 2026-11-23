"""Deterministic numerical controls plus optional real-case audit."""
import unittest,tempfile,sys,json
from pathlib import Path

if '--dependency-dir' in sys.argv:
    index=sys.argv.index('--dependency-dir');sys.path.insert(0,sys.argv[index+1]);del sys.argv[index:index+2]
import gemmi
from audit_occupancy import audit,decode_sof,matches_cif_precision,check_cell_metric

class OccupancyTests(unittest.TestCase):
    def result(self,atoms,unit='2 0',extras=''):
        text='TITL numerical control\nCELL 0.71073 10 10 10 90 90 90\nZERR 1 0.01 0.01 0.01 0 0 0\nLATT -1\nSYMM x,-y,z\nSFAC C H\nUNIT '+unit+'\nFVAR 1 0.6\n'+extras+atoms+'\nHKLF 4\nEND\n'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.ins';path.write_text(text,encoding='ascii')
            return audit(path,gemmi)
    def test_complementary_free_variables(self):
        self.assertAlmostEqual(decode_sof(21,[1,.6439]),.6439)
        self.assertAlmostEqual(decode_sof(-21,[1,.6439]),.3561)
        self.assertAlmostEqual(decode_sof(20.5,[1,.6]),.3)
        self.assertAlmostEqual(decode_sof(-20.5,[1,.6]),.2)
    def test_special_site_vs_general_disorder(self):
        r=self.result('C1 1 0.1 0 0.3 10.5 0.04\nPART -1\nC2 1 0.2 0.2 0.3 10.5 0.04')
        self.assertEqual([a['label'] for a in r['atoms']],['C1','C2'])
        self.assertEqual([a['geometric_site_multiplicity'] for a in r['atoms']],[1,2])
        self.assertEqual([a['inferred_cif_occupancy'] for a in r['atoms']],[1,.5])
        self.assertEqual(r['modeled_unit_cell_composition']['C'],2)
    def test_partial_special_site(self):
        r=self.result('PART 1\nC1 1 0.1 0 0.3 20.5 0.04\nPART 2\nC2 1 0.1 0 0.3 -20.5 0.04',unit='1 0')
        self.assertAlmostEqual(r['atoms'][0]['inferred_cif_occupancy'],.6)
        self.assertAlmostEqual(r['atoms'][1]['inferred_cif_occupancy'],.4)
        self.assertAlmostEqual(r['modeled_unit_cell_composition']['C'],1)
    def test_part_override(self):
        r=self.result('PART 1 21\nC1 1 0.1 0.2 0.3 11 0.04\nPART 2 -21\nC2 1 0.1 0.3 0.3 11 0.04')
        self.assertAlmostEqual(r['atoms'][0]['decoded_shelx_sof'],.6)
        self.assertAlmostEqual(r['atoms'][1]['decoded_shelx_sof'],.4)
    def test_overoccupied_site_is_flagged(self):
        r=self.result('C1 1 0.1 0 0.3 11 0.04')
        self.assertTrue(any('outside' in w for w in r['warnings']))
    def test_missing_free_variable_fails(self):
        with self.assertRaises(ValueError):decode_sof(31,[1,.6])
    def test_generated_punctuation_labels_fail_closed(self):
        for label in ('H00$', 'H00:'):
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError,'Unsupported atom label'):
                    self.result(f'C1 1 .1 .2 .3 11 .04\n{label} 2 .2 .3 .4 11 -.12')
    def test_layered_marginal_populations_not_one_part_fraction(self):
        # Abstract P1 accounting only: two CH2 skeletons at half population,
        # four terminal pockets with 3/4 C and 1/4 Cl. No private coordinates.
        text='CELL .71073 20 20 20 90 90 90\nLATT -1\nSFAC C Cl N\nUNIT 7 1 1\nFVAR 1\nN1 3 .1 .1 .1 11 .04\n'
        for i in range(8):
            text+=f'PART {1+i//4}\nC{i+1} 1 .{i+1} .2 .3 10.5 .04\n'
        for i in range(4):
            text+=f'PART 1\nT{i+1} 1 .{i+1} .4 .5 10.75 .04\nPART 2\nCl{i+1} 2 .{i+1} .6 .7 10.25 .04\n'
        text+='HKLF 4\nEND\n'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.ins';path.write_text(text,encoding='ascii');r=audit(path,gemmi)
        self.assertEqual(r['modeled_unit_cell_composition'],{'N':1,'C':7,'Cl':1})
        # PART labels do not multiply or replace explicit site populations.
        self.assertEqual(sorted({x['decoded_shelx_sof'] for x in r['atoms']}),[.25,.5,.75,1])
    def test_repeated_fvar_cards_are_concatenated(self):
        r=self.result('C1 1 .1 .2 .3 31 .04\nC2 1 .2 .3 .4 -41 .04',
                      extras='FVAR .2 .7\n',unit='1 0')
        self.assertAlmostEqual(r['atoms'][0]['decoded_shelx_sof'],.2)
        self.assertAlmostEqual(r['atoms'][1]['decoded_shelx_sof'],.3)
        self.assertAlmostEqual(r['modeled_unit_cell_composition']['C'],1)
    def test_fvar_after_atoms_and_continuation_preserve_order(self):
        r=self.result('C1 1 .1 .2 .3 51 .04\nC2 1 .2 .3 .4 -41 .04\nFVAR .1 =\n .25 .8 ! appended values',unit='3.1 0')
        self.assertAlmostEqual(r['atoms'][0]['decoded_shelx_sof'],.8)
        self.assertAlmostEqual(r['atoms'][1]['decoded_shelx_sof'],.75)
        self.assertAlmostEqual(r['modeled_unit_cell_composition']['C'],3.1)
    def test_split_fvar_equivalent_to_one_card_without_mutation(self):
        prefix='CELL .71073 10 10 10 90 90 90\nLATT -1\nSFAC C\nUNIT .7\n'
        suffix='C1 1 .1 .2 .3 81 .04\nHKLF 4\nEND\nFVAR .99\n'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.res'
            results=[]
            for cards in ['FVAR 1 .1 .2 .3 .4 .5 .6 .7\n',
                          'FVAR 1 .1 .2\nfvar .3 .4\nFVAR .5 .6 .7\n']:
                path.write_text(prefix+cards+suffix,encoding='ascii');before=path.read_bytes()
                results.append(audit(path,gemmi))
                self.assertEqual(path.read_bytes(),before)
            self.assertEqual(results[0]['atoms'],results[1]['atoms'])
            self.assertAlmostEqual(results[1]['atoms'][0]['decoded_shelx_sof'],.7)
    def test_combined_occupancy_on_shared_orbit(self):
        r=self.result('C1 1 0.1 0 0.3 10.5 0.04\nC2 1 0.1 0 0.3 10.5 0.04')
        self.assertEqual(r['overlapping_orbit_groups'][0]['summed_occupancy'],2)
        self.assertTrue(any('orbit overoccupied' in w for w in r['warnings']))
    def test_encoded_coordinates_are_not_silently_interpreted(self):
        with self.assertRaises(ValueError):self.result('C1 1 21 0 0.3 10.5 0.04')
    def test_fixed_plus_ten_coordinates(self):
        r=self.result('C1 1 10.1 10 10.3 10.5 0.04')
        self.assertAlmostEqual(r['atoms'][0]['xyz'][0],.1)
        self.assertAlmostEqual(r['atoms'][0]['inferred_cif_occupancy'],1)
    def test_cif_rounding_is_not_a_model_mismatch(self):
        self.assertTrue(matches_cif_precision(.34847,'0.348(7)'))
        self.assertTrue(matches_cif_precision(.35542,'0.36(2)'))
        self.assertFalse(matches_cif_precision(.375,'0.36(2)'))
        self.assertFalse(matches_cif_precision(.5,'1'))
    def test_rhombohedral_solved_model_different_meanings_of_one_sixth(self):
        text='TITL anonymized learned orbit control\nCELL .71073 14.9748 14.9748 23.5406 90 90 120\nZERR 3 .001 .001 .001 0 0 0\nLATT 3\nSYMM -y,x-y,z\nSYMM y-x,-x,z\nSFAC Cu Cs C\nUNIT 12 6 3\nFVAR 1\nCU1 1 .39538 .604636 .140547 10.5 .04\nCU2 1 .333333 .666667 .232031 10.16667 .04\nCS1 2 .333333 .666667 .376189 10.33333 .04\nPART -1\nC1 3 .675759 .421307 .394615 10.16667 .04\nHKLF 4\nEND\n'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.ins';path.write_text(text,encoding='ascii');r=audit(path,gemmi)
        self.assertEqual(r['general_multiplicity'],18)
        self.assertEqual([a['geometric_site_multiplicity'] for a in r['atoms']],[18,6,6,18])
        for actual,expected in zip([a['inferred_cif_occupancy'] for a in r['atoms']],[.5,.5,1,1/6]):self.assertAlmostEqual(actual,expected,places=4)
    def test_distinct_free_variables_are_not_implicitly_complements(self):
        fv=[1,.59546,.55865,.55679,.01685]
        self.assertAlmostEqual(decode_sof(21,fv)+decode_sof(-21,fv),1)
        self.assertAlmostEqual(decode_sof(31,fv)+decode_sof(-41,fv),1.00186)

    def test_incompatible_cell_stops_the_audit(self):
        text='TITL metric mismatch\nCELL .71073 9.6386 9.6386 9.6952 90 90 120\nLATT -7\nSYMM -x,y,-z\nSFAC C\nUNIT 4\nFVAR 1\nC1 1 .1 .2 .3 11 .04\nHKLF 4\nEND\n'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.ins';path.write_text(text,encoding='ascii')
            before=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'CELL metric incompatible'):audit(path,gemmi)
            self.assertEqual(path.read_bytes(),before)

    def test_monoclinic_different_unique_axes(self):
        for values,op in [((10,12,14,90,105,90),'-x,y,-z'),
                          ((10,12,14,105,90,90),'x,-y,-z'),
                          ((10,12,14,90,90,105),'-x,-y,z')]:
            self.assertLess(check_cell_metric(gemmi.UnitCell(*values),[gemmi.Op(op)])['maximum_normalized_discrepancy'],1e-12)

    def test_hexagonal_nondiagonal_rotation(self):
        ops=[gemmi.Op('-y,x-y,z'),gemmi.Op('y-x,-x,z')]
        self.assertLess(check_cell_metric(gemmi.UnitCell(10,10,18,90,90,120),ops)['maximum_normalized_discrepancy'],1e-12)
        with self.assertRaises(ValueError):check_cell_metric(gemmi.UnitCell(10,12,18,90,90,120),ops)

    def test_metric_translation_and_scale_do_not_change_result(self):
        for scale in [1,10]:
            result=check_cell_metric(gemmi.UnitCell(10*scale,12*scale,14*scale,90,105,90),[gemmi.Op('-x,y+1/2,-z')])
            self.assertLess(result['maximum_normalized_discrepancy'],1e-12)

    def test_metric_compatibility_does_not_require_higher_symmetry(self):
        ops=[gemmi.Op('x,y,z'),gemmi.Op('-x,-y,-z')]
        for values in [(10,10,10,90,90,90),(10,12,14,75,85,105)]:
            self.assertEqual(check_cell_metric(gemmi.UnitCell(*values),ops)['maximum_normalized_discrepancy'],0)

    def test_small_cell_rounding_versus_real_mismatch(self):
        op=[gemmi.Op('-x,y,-z')]
        check_cell_metric(gemmi.UnitCell(10,12,14,90,105,90.0001),op)
        with self.assertRaises(ValueError):check_cell_metric(gemmi.UnitCell(10,12,14,90,105,90.1),op)

if __name__=='__main__':unittest.main()
