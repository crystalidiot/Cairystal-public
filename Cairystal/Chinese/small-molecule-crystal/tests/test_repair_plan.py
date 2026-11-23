from pathlib import Path
import tempfile, unittest, json, math
from unittest.mock import patch
from repair_plan import compile_trials, run
from hydrogen_riding_trial import edit
from candidate_trials import build, controls, IMMUTABLE

def fixture(d):
    res='TITL synthetic\nCELL .71073 10 10 10 90 90 90\nZERR 1 .001 .001 .001 .01 .01 .01\nLATT -1\nSFAC C O N H\nUNIT 2 1 1 1\nFVAR 1\nWGHT .04 0\nL.S. 20\n'
    res+='C1 1 .2 .2 .2 11 .04 .04 .04 0 0 0\nC2 1 .1 .1 .2 11 .04 .04 .04 0 0 0\nN1 3 .3 .4 .5 11 .04 .04 .04 0 0 0\nO1 2 .34 .2 .2 11 .04 .04 .04 0 0 0\nAFIX 147\nH1 4 .368 .279196 .2 11 -1.5\nAFIX 0\nHKLF 4\nEND\n'
    cif="data_test\n_cell_length_a 10\n_cell_length_b 10\n_cell_length_c 10\n_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\nloop_\n_space_group_symop_operation_xyz\n'x,y,z'\nloop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_U_iso_or_equiv\n_atom_site_occupancy\n"
    cif+='C1 C .2 .2 .2 .04 1\nC2 C .1 .1 .2 .04 1\nN1 N .3 .4 .5 .04 1\nO1 O .34 .2 .2 .04 1\nH1 H .368 .279196 .2 .06 1\n'
    (d/'case.res').write_text(res,encoding='ascii');(d/'case.cif').write_text(cif,encoding='ascii');return res

class RepairTests(unittest.TestCase):
    def setUp(self):self.t=tempfile.TemporaryDirectory();self.d=Path(self.t.name);self.original=fixture(self.d)
    def tearDown(self):self.t.cleanup()
    def req(self,recipe,params):return {'recipe':recipe,'parameters':params,'reason':'Synthetic hypothesis','evidence':['Synthetic atom and geometry observations']}
    def test_element_scan_preserves_order_and_excludes_unchanged(self):
        plans=compile_trials(self.d,self.req('element_scan',{'atom':'N1','elements':['C','N','O']}));self.assertEqual(len(plans),3)
        text,_=build(self.d,plans[-1],self.d);self.assertIn('O2 2 ',text);self.assertIn('SFAC C O N H',text);self.assertEqual(plans[-1]['rename'],{'N1':'O2'})
    def test_element_scan_rejects_parent_with_h(self):
        with self.assertRaises(ValueError):compile_trials(self.d,self.req('element_scan',{'atom':'O1','elements':['C','O']}))
    def test_unknown_element(self):
        with self.assertRaises(ValueError):compile_trials(self.d,self.req('element_scan',{'atom':'N1','elements':['Cu']}))
    def test_empty_evidence(self):
        req=self.req('h_freeze',{'parent':'O1'});req['evidence']=[]
        with self.assertRaises(ValueError):compile_trials(self.d,req)
    def test_local_adp_not_combined(self):
        ps=compile_trials(self.d,self.req('adp_local',{'atoms':['C1','C2'],'methods':['RIGU','SIMU','ISOR','ISO']}));self.assertEqual(len(ps),5)
        self.assertEqual(ps[2]['add_restraints'],['SIMU 0.04 0.08 1.7 C1 C2'])
    def test_no_selector_or_newline(self):
        for token in ['$C','C1 > C2','C1\nOMIT 1 2 3']:
            with self.assertRaises(ValueError):compile_trials(self.d,self.req('adp_local',{'atoms':[token],'methods':['ISOR']}))
    def test_no_tiny_sigma(self):
        with self.assertRaises(ValueError):compile_trials(self.d,self.req('geometry_local',{'restraint':'DFIX','atoms':['C1','C2'],'target':1.5,'sigma':.0001,'basis':'known'}))
    def test_geometry_requires_basis(self):
        with self.assertRaises(ValueError):compile_trials(self.d,self.req('geometry_local',{'restraint':'DFIX','atoms':['C1','C2'],'target':1.5,'sigma':.02,'basis':''}))
    def test_flat_supported(self):
        p=compile_trials(self.d,self.req('geometry_local',{'restraint':'FLAT','atoms':['C1','C2','N1','O1'],'sigma':.1,'basis':'synthetic planar hypothesis'}))[-1]
        text,_=build(self.d,p,self.d);self.assertIn('FLAT 0.1 C1 C2 N1 O1',text)
    def test_atom_omit_is_zero_cycle_map(self):
        p=compile_trials(self.d,self.req('omit_map',{'atoms':['N1']}))[-1];text,_=build(self.d,p,self.d)
        self.assertIn('L.S. 0',text);self.assertIn('LIST 6',text);self.assertNotIn('ACTA',text);self.assertNotIn('OMIT 1',text)
    def test_freeze_preserves_h_count_sof_u_and_controls(self):
        p=compile_trials(self.d,self.req('h_freeze',{'parent':'O1'}))[-1];text,changes=build(self.d,p,self.d)
        self.assertIn('AFIX 3',text);self.assertIn('H1 4 .368 .279196 .2 11 -1.5',text);self.assertEqual(controls(text,IMMUTABLE),controls(self.original,IMMUTABLE));self.assertIn('hydrogen_riding',changes[0])
    def test_rotation_preserves_bond_and_angle(self):
        text,changes=edit(self.d,{'mode':'rotate_oh','parent':'O1','anchor':'C1','angle_degrees':180})
        r=changes[0]['hydrogen_riding']['rotation'];x,y,z=r['new_H_fractional'];self.assertAlmostEqual(x,.368);self.assertAlmostEqual(y,.120804);self.assertAlmostEqual(z,.2);self.assertEqual((self.d/'case.res').read_text('ascii'),self.original)
    def test_rotation_guard_wrong_anchor(self):
        with self.assertRaises(ValueError):edit(self.d,{'mode':'rotate_oh','parent':'O1','anchor':'N1','angle_degrees':180})
    def test_nonfinite_angle(self):
        with self.assertRaises(ValueError):compile_trials(self.d,self.req('oh_rotate',{'parent':'O1','anchor':'C1','angles':[float('nan')]}))
    def test_malformed_H_count(self):
        (self.d/'case.res').write_text(self.original.replace('AFIX 147','AFIX 23'),'ascii')
        with self.assertRaises(ValueError):edit(self.d,{'parent':'O1'})
    def test_hfix_conflict(self):
        (self.d/'case.res').write_text(self.original.replace('HKLF','HFIX 147 O1\nHKLF'),'ascii')
        with self.assertRaises(ValueError):edit(self.d,{'parent':'O1'})
    def test_native_output_cards_before_AFIX_zero(self):
        (self.d/'case.res').write_text(self.original.replace('AFIX 0','LIST 4\nACTA\nPLAN 100\nAFIX 0'),'ascii')
        text,_=edit(self.d,{'parent':'O1'});self.assertIn('AFIX 3',text);self.assertIn('LIST 4',text)
    def test_h_environment_records_geometry(self):
        from hydrogen_riding_trial import environment
        e=environment(self.d,'O1');self.assertEqual(len(e['hydrogens']),1);self.assertAlmostEqual(e['hydrogens'][0]['D_H_A'],.84,places=4)
    def test_referenced_H_constraint(self):
        (self.d/'case.res').write_text(self.original.replace('HKLF','DFIX .84 .02 O1 H1\nHKLF'),'ascii')
        with self.assertRaises(ValueError):edit(self.d,{'parent':'O1'})
    def test_reject_mixed_h_and_other_edits(self):
        p=compile_trials(self.d,self.req('h_freeze',{'parent':'O1'}))[-1];p['add_restraints']=['ISOR C1']
        with self.assertRaises(ValueError):build(self.d,p,self.d)
    def test_crosspart_adp(self):
        (self.d/'case.res').write_text(self.original.replace('C2 1','PART 1\nC2 1').replace('N1 3','PART 0\nN1 3'),'ascii')
        with self.assertRaises(ValueError):compile_trials(self.d,self.req('adp_local',{'atoms':['C1','C2'],'methods':['SIMU']}))

if __name__=='__main__':unittest.main(verbosity=2)
