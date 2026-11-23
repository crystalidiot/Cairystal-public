import tempfile,unittest
from pathlib import Path
import gemmi
from atom_labels import make_plan,parse,apply_plan,require_normalized,remap_narrative,sort_cif,NamingReview
from crystal_runtime import records

def model(atoms,extra=''):
    return ('TITL test\nCELL .71073 20 20 20 90 90 90\nZERR 1 .001 .001 .001 0 0 0\nLATT -1\nSFAC C H N O Cl\nUNIT 2 4 1 1 1\nL.S. 12\nWGHT .1\nFVAR 1 .6\n'+extra+'\n'+atoms+'\nHKLF 4\nEND\n')

class AtomLabels(unittest.TestCase):
    def test_element_counters_and_simultaneous_collision(self):
        text=model('O9 4 .5 .5 .5 11 .03\nC2 1 .1 .1 .1 11 .03\nN9 3 .4 .4 .4 11 .03\nC1 1 .2 .2 .2 11 .03')
        p=make_plan(text);self.assertEqual(p['mapping'],{'O9':'O1','C2':'C1','N9':'N1','C1':'C2'})
        self.assertEqual([r[1:] for r in records(text)],[r[1:] for r in records(p['native_input'])])
        self.assertFalse(require_normalized(p['native_input'])['changed'])
    def test_disorder_correspondence_not_inferred(self):
        t=model('PART 1\nC34A 1 .1 .1 .1 21 .03\nC35A 1 .2 .1 .1 21 .03\nPART 2\nC34B 1 .1 .2 .1 -21 .03\nC90B 1 .2 .2 .1 -21 .03\nPART 0')
        p=make_plan(t)
        self.assertEqual(p['mapping'],{'C34A':'C1A','C35A':'C2A','C34B':'C1B','C90B':'C3B'})
        self.assertFalse(require_normalized(p['native_input'])['changed'])
        old=records(t);new=records(p['native_input'])
        self.assertEqual([r[1:] for r in old],[r[1:] for r in new])
    def test_references_range_symmetric_and_element_selectors(self):
        t=model('C9 1 .1 .1 .1 11 .03\nC8 1 .2 .1 .1 11 .03\nO9 4 .3 .1 .1 11 .03','EQIV $1 -x,y,z\nDFIX 1.5 .02 C9 C8\nSIMU .04 C9>O9\nSAME C9 < O9\nEADP C9 C8\nHTAB C9 O9_$1\nHFIX 23 C8\nISOR .02 $C\nRTAB C9 C9 C8')
        p=make_plan(t);rows=records(p['native_input']);lookup={r[0]:r for r in rows}
        self.assertEqual(lookup['HTAB'],['HTAB','C1','O1_$1'])
        self.assertEqual(lookup['SIMU'],['SIMU','.04','C1>O1'])
        self.assertEqual(lookup['RTAB'],['RTAB','C9','C1','C2'])
        self.assertEqual(lookup['ISOR'],['ISOR','.02','$C'])
        # Inverting only the labels restores every token of native physics.
        inv={'mapping':{v:k for k,v in p['mapping'].items()}}
        self.assertEqual(records(apply_plan(p['native_input'],inv)),records(t))
    def test_h_parent_afix_and_free_h(self):
        t=model('C9 1 .1 .1 .1 11 .03\nAFIX 23\nH9A 2 .148 .1 .1 11 -1.2\nH9B 2 .1 .148 .1 11 -1.2\nAFIX 0\nO8 4 .5 .5 .5 11 .03\nH8 2 .54 .5 .5 11 .05')
        p=make_plan(t)
        self.assertEqual([p['mapping'][x] for x in ['H9A','H9B','H8']],['H1A','H1B','H1C'])
        h=next(a for a in p['atoms'] if a['old']=='H8');self.assertEqual(h['parent_new'],'O1')
        self.assertFalse(require_normalized(p['native_input'])['changed'])
    def test_h_and_part_pairing(self):
        t=model('PART 1\nC34A 1 .1 .1 .1 21 .03\nAFIX 23\nH3A 2 .148 .1 .1 21 -1.2\nH3B 2 .1 .148 .1 21 -1.2\nAFIX 0\nPART 2\nC34B 1 .5 .5 .5 -21 .03\nAFIX 23\nH4A 2 .548 .5 .5 -21 -1.2\nH4B 2 .5 .548 .5 -21 -1.2\nAFIX 0\nPART 0')
        p=make_plan(t);h=[a for a in p['atoms'] if a['element']=='H']
        self.assertEqual([x['new'] for x in h],['H1A','H1B','H1C','H1D'])
        self.assertEqual([x['parent_new'] for x in h],['C1A','C1A','C1B','C1B'])
        self.assertFalse(require_normalized(p['native_input'])['changed'])
    def test_ambiguous_h_stops(self):
        t=model('O9 4 .1 .1 .1 11 .03\nO8 4 .19 .1 .1 11 .03\nH7 2 .145 .1 .1 11 .04')
        with self.assertRaisesRegex(NamingReview,'ambiguous'):make_plan(t)
    def test_sign_and_residue_guard(self):
        for control in ['CHIV 2 C9','RESI 1','DFIX_1 1.5 C9 C8','FRAG 1','MOVE 1 1 1']:
            with self.subTest(control=control),self.assertRaises(NamingReview):make_plan(model('C9 1 .1 .1 .1 11 .03',control))
    def test_zero_chiv_allowed(self):
        p=make_plan(model('C9 1 .1 .1 .1 11 .03','CHIV 0 C9'))
        self.assertIn(['CHIV','0','C1'],records(p['native_input']))
    def test_numbering_gate_prevents_stale_delivery(self):
        with self.assertRaisesRegex(NamingReview,'pending'):require_normalized(model('C9 1 .1 .1 .1 11 .03'))
    def test_narrative_boundaries(self):
        self.assertEqual(remap_narrative('C9 and C90; file_C9 and C9A remain.',{'C9':'C1'}),'C1 and C90; file_C9 and C9A remain.')
    def test_old_chemistry_prose_not_rewritten_as_atom_names(self):
        from atom_labels import remap_notes
        old={'bilingual_notes':{'zh':{'summary':'C9 H12；检查 C9'},'en':{'summary':'C9 H12; inspect C9'}}}
        new=remap_notes(old,{'C9':'C1'})
        self.assertEqual(new['bilingual_notes']['zh']['summary'],old['bilingual_notes']['zh']['summary'])
        self.assertIn('atom_label_map.json',new['bilingual_notes']['en']['limitations'])
    def test_occupancy_print_rounding_not_uncertainty(self):
        import copy
        from test_delivery_automation import atom_cif,OCC,INS
        from crystal_runtime import compare_atom_loop
        occ=copy.deepcopy(OCC);occ['atoms'][0]['inferred_cif_occupancy']=.59832
        compare_atom_loop(atom_cif(occ='.598(3)'),occ,INS)
        with self.assertRaisesRegex(ValueError,'occupancy mismatch'):
            compare_atom_loop(atom_cif(occ='.600(99)'),occ,INS)
        with self.assertRaisesRegex(ValueError,'occupancy mismatch'):
            compare_atom_loop(atom_cif(occ='1'),occ,INS)
    def test_anisotropic_numeric_tails_not_changed(self):
        t=model('C9 1 .1 .1 .1 11 .03 .04 .05 .001 .002 .003\nO8 4 .2 .2 .2 10.5 .04')
        p=make_plan(t)
        self.assertEqual([r[1:] for r in records(t)],[r[1:] for r in records(p['native_input'])])
    def test_output_sorted_whole_rows_without_numeric_changes(self):
        cif='''data_test
_audit_creation_method 'synthetic'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_U_iso_or_equiv
_atom_site_occupancy
_atom_site_disorder_group
H2 H .4(2) .04 1 .
O1 O .3(1) .02(2) 1 .
C10 C .2(1) .03(2) .6(2) 1
C2 C .1(1) .04(2) 1 .
loop_
_atom_site_aniso_label
_atom_site_aniso_U_11
O1 .032(2)
C10 .042(3)
C2 .012(3)
loop_
_geom_bond_atom_site_label_1
_geom_bond_atom_site_label_2
_geom_bond_distance
C2 O1 1.23(2)
'''
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'m.cif';path.write_text(cif)
            b=gemmi.cif.read_file(str(path)).sole_block();before={r[0]:list(r) for r in b.find(['_atom_site_label','_atom_site_type_symbol','_atom_site_fract_x','_atom_site_U_iso_or_equiv','_atom_site_occupancy','_atom_site_disorder_group'])}
            sort_cif(path);b=gemmi.cif.read_file(str(path)).sole_block()
            self.assertEqual(list(b.find_values('_atom_site_label')),['C2','C10','O1','H2'])
            self.assertEqual(list(b.find_values('_atom_site_aniso_label')),['C2','C10','O1'])
            after={r[0]:list(r) for r in b.find(['_atom_site_label','_atom_site_type_symbol','_atom_site_fract_x','_atom_site_U_iso_or_equiv','_atom_site_occupancy','_atom_site_disorder_group'])}
            self.assertEqual(before,after);self.assertEqual(list(b.find_values('_geom_bond_distance')),['1.23(2)'])
            one=path.read_bytes();sort_cif(path);self.assertEqual(path.read_bytes(),one)

if __name__=='__main__':unittest.main()
