import tempfile, unittest
from pathlib import Path
import gemmi
from crystal_session import laue_seed,logical_text,parse_p4p,normalize_solver_records,summarize,inside
from report_preflight import review_contacts,normalize_sg_name
from crystal_runtime import symmetry_operations,compare_atom_loop

class RoutineTests(unittest.TestCase):
    def test_solver_output_without_fvar_preserves_coordinates(self):
        text='TITL solved\nCELL .71073 8 10 15 90 95 90\nLATT 1\nSFAC C H\nUNIT 8 0\nC1 1 .1 .2 .3 11 .02 8.9\nHKLF 4\nEND\n'
        result=normalize_solver_records(text)
        self.assertIn('FVAR 1',result);self.assertIn('C1 1 .1 .2 .3 11 .02\n',result);self.assertNotIn('8.9',result)
    def test_model_summary_handles_gemmi_rows_and_all_atom_coordinates(self):
        cif='''data_x
_cell_length_a 10
_cell_length_b 10
_cell_length_c 10
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_space_group_name_H-M_alt 'P 1'
_chemical_formula_sum 'C2'
loop_
_space_group_symop_operation_xyz
'x,y,z'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_U_iso_or_equiv
C1 C .1 .1 .1 .02
C2 C .25 .1 .1 .02
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'model.cif').write_text(cif);r=summarize(p)
            self.assertEqual(r['atoms'][0]['neighbors'],[['C2','C',1.5]])
            self.assertEqual(r['atoms'][1]['neighbors'],[['C1','C',1.5]])
    def test_previous_job_model_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'job').mkdir();(p/'earlier.res').write_text('model')
            with self.assertRaises(ValueError):inside(p/'job',p/'earlier.res')
    def test_ueq_propagates_res_tensor_rounding_but_rejects_changed_adp(self):
        ins='TITL synthetic\nCELL .71073 10 10 10 90 90 90\nLATT -1\nSFAC C\nUNIT 1\nFVAR 1\nC1 1 .1 .2 .3 11 .02005 .02005 .02004 0 0 0\nHKLF 4\n'
        cif='''data_x
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
_atom_site_U_iso_or_equiv
_atom_site_adp_type
C1 C .10000 .20000 .30000 1 .0201(1) Uani
loop_
_atom_site_aniso_label
_atom_site_aniso_U_11
_atom_site_aniso_U_22
_atom_site_aniso_U_33
_atom_site_aniso_U_23
_atom_site_aniso_U_13
_atom_site_aniso_U_12
C1 .02005 .02005 .02004 0 0 0
'''
        occupancy={'atoms':[{'label':'C1','element':'C','residue':'0','xyz':[.1,.2,.3],'inferred_cif_occupancy':1,'sof_serialization_rounding_bound':.000005}]}
        compare_atom_loop(gemmi.cif.read_string(cif).sole_block(),occupancy,ins)
        with self.assertRaises(ValueError):compare_atom_loop(gemmi.cif.read_string(cif.replace('.0201(1)','.0202(1)')).sole_block(),occupancy,ins)
    def test_recorded_monoclinic_search_and_conflict(self):
        m={'bravais':'Monoclinic(b-unique) P','cell':[8,10,15,90,95,90]}
        self.assertEqual(laue_seed(m)[:2],(1,['-X,Y,-Z']))
        m['cell'][3]=80
        with self.assertRaises(ValueError):laue_seed(m)
        with self.assertRaises(ValueError):laue_seed({'bravais':'Cubic P','cell':[10,10,10,90,90,90]})
    def test_theta_and_temperature_are_source_values(self):
        p='FILEID SAINT synthetic\nCELL 8 10 15 90 95 90 1200\nCELLSD .001 .001 .001 0 .01 0\nSOURCE MO .71073\nBRAVAIS Monoclinic(b-unique) P\nSAINGL 2500 2.5 26.3 0\nCSIZE ? ? ? ? 26.85\n'
        m=parse_p4p(p);self.assertEqual(m['measurement_reflections'],2500);self.assertEqual(m['temperature_K'],300);self.assertEqual(m['measurement_theta_max'],26.3)
    def test_normalize_not_alter_spacegroup_setting(self):
        self.assertEqual(normalize_sg_name('P2(1)/n'),'P21/n')
        self.assertNotEqual(normalize_sg_name('P2(1)/n'),normalize_sg_name('P2(1)/c'))
    def test_lattice_equivalent_operations_but_wrong_half_translation_rejected(self):
        def block(op):return gemmi.cif.read_string('data_x\nloop_\n_space_group_symop_operation_xyz\n\''+op+'\'\n').sole_block()
        self.assertEqual(symmetry_operations(block('x-1/2,-y-1/2,z-1/2')),symmetry_operations(block('x+1/2,-y+1/2,z+1/2')))
        self.assertNotEqual(symmetry_operations(block('x,-y,z')),symmetry_operations(block('x+1/2,-y,z')))
    def test_contact_filter_retains_free_halide_and_model(self):
        text='''data_x
_shelx_res_file 'unchanged embedded model'
loop_
_atom_site_label
_atom_site_type_symbol
Cl1 Cl
Cl2 Cl
O1 O
O2 O
O3 O
O4 O
N1 N
H1 H
loop_
_geom_bond_atom_site_label_1
_geom_bond_atom_site_label_2
_geom_bond_distance
Cl1 O1 1.42
Cl1 O2 1.43
Cl1 O3 1.44
Cl1 O4 1.45
loop_
_geom_hbond_atom_site_label_D
_geom_hbond_atom_site_label_H
_geom_hbond_atom_site_label_A
_geom_hbond_distance_HA
N1 H1 Cl1 2.98
N1 H1 Cl2 2.8
N1 H1 O1 2.1
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.cif';p.write_text(text);a=review_contacts(p);b=gemmi.cif.read_file(str(p)).sole_block()
            self.assertEqual(len(a['removed_reporting_rows']),1);self.assertEqual(a['retained_rows'],2)
            self.assertEqual(list(b.find_values('_geom_hbond_atom_site_label_A')),['Cl2','O1'])
            self.assertEqual(gemmi.cif.as_string(b.find_value('_shelx_res_file')),'unchanged embedded model')
            self.assertEqual(list(b.find_values('_atom_site_label')),['Cl1','Cl2','O1','O2','O3','O4','N1','H1'])
    def test_long_records_preserve_tokens(self):
        row=['C1','1']+['0.123456']*12
        rendered=logical_text([row]);self.assertTrue(all(len(s)<80 for s in rendered.splitlines()))
        self.assertEqual(rendered.replace('=\n',' ').split(),row)

if __name__=='__main__':unittest.main()
