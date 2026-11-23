"""Synthetic diagnostic controls; these tests do not establish chemical accuracy."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import contextlib
import io
from initial_model_review import build_review, review, save_review
from candidate_packet import make_packet

def packet():
    atom={'label':'C1','element':'C','part':0,'occupancy':1.,'Ueq':.01,
          'res_context_status':'matched','non_positive_definite':False,'principal_rms_axis_ratio':1.,
          'nearby_reported_Q_peaks':[]}
    atom['neighbors']=[{'label':name,'element':'N','part':0,'occupancy':1.,'Ueq':.05,
                        'part_compatible':True,'within_covalent_radius_screen':True,
                        'distance':1.4,'symmetry':'x,y,z','translation':[0,0,0]}
                       for name in ['N1','N2']]
    return {'all_atoms':[atom], 'regions':[atom], 'source_hashes':{},'source_directory':'synthetic',
            'space_group':'P 1','gate':{'metrics':{'R1_observed':None}},'difference_density':{'max':None,'min':None}}

def write_fixture(directory):
    directory.mkdir(exist_ok=True,parents=True)
    (directory/'model.res').write_text('''TITL synthetic screening only
CELL 0.71073 10 10 10 90 90 90
LATT -1
SFAC C N O
UNIT 1 1 1
FVAR 1
C1 1 .40 .40 .40 11 .01
N1 2 .54 .40 .40 11 .05
O1 3 .26 .40 .40 11 .05
HKLF 4
END
''',encoding='ascii')
    (directory/'model.cif').write_text('''data_synthetic
_cell_length_a 10
_cell_length_b 10
_cell_length_c 10
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_space_group_name_H-M_alt 'P 1'
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
_atom_site_occupancy
C1 C .40 .40 .40 .01 1
N1 N .54 .40 .40 .05 1
O1 O .26 .40 .40 .05 1
''',encoding='ascii')

class InitialReviewTests(unittest.TestCase):
    def test_low_relative_U_is_only_a_candidate_hint(self):
        out=build_review(packet(),['C','N','O'])
        self.assertIn('low_relative_Ueq',out['sites'][0]['flags'])
        self.assertEqual(out['sites'][0]['candidate_elements_to_review'],['C','N','O'])
        self.assertFalse(out['scientific_acceptance'])
        self.assertFalse(out['sites'][0]['element_replacement_decided'])

    def test_high_U_does_not_decide_an_element(self):
        p=packet();p['regions'][0]['Ueq']=.2
        out=build_review(p,['C','N'])
        self.assertIn('high_relative_Ueq',out['sites'][0]['flags'])
        self.assertNotIn('O',out['sites'][0]['candidate_elements_to_review'])

    def test_mutually_exclusive_part_is_not_a_neighbor(self):
        p=packet();p['regions'][0]['neighbors'][0]['part_compatible']=False
        out=build_review(p,['C','N','O'])
        self.assertEqual(out['sites'][0]['comparable_neighbor_count'],1)
        self.assertIsNone(out['sites'][0]['relative_Ueq'])

    def test_partial_occupancy_does_not_set_neighbor_reference_U(self):
        p=packet();p['regions'][0]['neighbors'][0]['occupancy']=.3
        self.assertIsNone(build_review(p,['C','N','O'])['sites'][0]['relative_Ueq'])

    def test_normal_screen_is_not_chemical_acceptance(self):
        p=packet();p['regions'][0]['Ueq']=.05
        out=build_review(p,['C','N','O'])
        self.assertEqual(out['status'],'screened_requires_chemical_review')
        self.assertFalse(out['scientific_acceptance'])

    def test_missing_U_and_local_negative_density_stay_unknown(self):
        p=packet();p['regions'][0]['Ueq']=None
        out=build_review(p,['C','N','O'])
        self.assertIsNone(out['sites'][0]['relative_Ueq'])
        self.assertIsNone(out['local_negative_density'])

    def test_element_not_allowed_and_unmatched_pair_are_explicit(self):
        p=packet();p['all_atoms'][0]['res_context_status']='ambiguous_or_unmatched'
        out=build_review(p,['N','O'])
        self.assertEqual({x['code'] for x in out['findings']},
                         {'light_atom_review','element_outside_input','cif_res_pairing_unresolved'})

    def test_real_file_geometry_and_hash_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);write_fixture(d)
            before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in d.iterdir()}
            out=review(d,'model',['C','N','O'])
            c=next(x for x in out['sites'] if x['label']=='C1')
            self.assertAlmostEqual(c['relative_Ueq'],.2)
            self.assertEqual(c['contact_angles_not_bond_orders'][0]['angle_deg'],180.)
            self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in d.iterdir()})

    def test_failed_review_is_saved_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'failure.json'
            saved=save_review(Path(tmp),'model',['C'],p)
            self.assertEqual(saved['status'],'review_unavailable')
            self.assertFalse(json.loads(p.read_text())['scientific_acceptance'])
            with self.assertRaises(FileExistsError):save_review(Path(tmp),'model',['C'],p)

    def test_candidate_packet_preserves_review_status_and_path(self):
        summary={'candidates':[{'stage':'any/01_baseline_0','metrics':{},'review':{
            'atoms':[],'space_group':'P 1','formula':'?','difference_density':[None,None]},
            'initial_review':{'status':'review_unavailable','path':'initial_review.json','scientific_acceptance':False}}]}
        c=make_packet(Path('.'),summary)['candidates'][0]
        self.assertEqual(c['initial_review'],summary['candidates'][0]['initial_review'])

    def test_session_start_actually_invokes_post_solution_screening(self):
        import crystal_session as cs
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);hkl=base/'input.hkl';hkl.write_text('synthetic only')
            p4p=base/'input.p4p';p4p.write_text('synthetic only')
            exe=base/'native_stub.exe';exe.write_text('never executed')
            root=base/'run'
            a=SimpleNamespace(hkl=str(hkl),p4p=str(p4p),output=str(root),elements=['C','N','O'],
                shelxt=str(exe),shelxl=str(exe),specimen=None,prior_conversation_exposure=False)
            meta={'cell':[10.,10.,10.,90.,90.,90.],'cell_su':[.001,.001,.001,0,0,0],'wavelength':.71073}
            def native_stub(job,name,text,program,reason,**kwargs):
                stage=job/'stages'/name;write_fixture(stage)
                if program=='shelxt':return {'success':True,'candidate_outputs':['model.res']}
                return {'gate':{'metrics':{}},'review':{'atoms':[]}}
            with (patch.object(cs,'parse_p4p',return_value=meta),patch.object(cs,'laue_seed',return_value=(-1,[],'synthetic')),
                 patch('p4p_metadata.input_conflicts',return_value=[]),patch.object(cs,'edit_candidate',return_value=('unused',{})),
                 patch.object(cs,'execute',side_effect=native_stub),contextlib.redirect_stdout(io.StringIO())):
                cs.start(a)
            summary=json.loads((root/'start_summary.json').read_text('utf-8'))
            saved=summary['candidates'][0]['initial_review']
            self.assertEqual(saved['status'],'needs_review')
            report=json.loads(Path(saved['path']).read_text('utf-8'))
            self.assertIn('low_relative_Ueq',report['sites'][0]['flags'])

if __name__=='__main__':unittest.main()
