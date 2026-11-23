"""Geometry/formula oracles and error isolation; no correctness labels for real models."""
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import gemmi
from donor_audit import images,screen,audit
from reflection_audit import standard_weights,row_metrics
from ab_evidence_tools import collect

CELL=gemmi.UnitCell(10,10,10,90,90,90)
OPS=[gemmi.Op('x,y,z')]
def atom(label,element,xyz,part=0):
    return dict(label=label,element=element,xyz=xyz,part=part,occupancy=1,afix=0)

class DonorEvidenceTests(unittest.TestCase):
    def test_free_water_H_and_collinear_acceptor(self):
        atoms=[atom('O1','O',[.2,.2,.2]),atom('H1','H',[.284,.2,.2]),
               atom('H2','H',[.18,.28,.2]),atom('O2','O',[.48,.2,.2])]
        r=screen(CELL,OPS,atoms);o=r['donors'][0]
        self.assertEqual(len(o['hydrogens']),2);self.assertFalse(o['possible_water_missing_H'])
        contact=o['hydrogens'][0]['contacts'][0]
        self.assertAlmostEqual(contact['D_H_A_degrees'],180)
        self.assertAlmostEqual(contact['H_A_A'],1.96)
        self.assertTrue(contact['geometric_screen']);self.assertFalse(contact['acceptor_chemistry_confirmed'])
    def test_unbonded_oxygen_is_only_water_hypothesis(self):
        o=screen(CELL,OPS,[atom('O1','O',[.2,.2,.2])])['donors'][0]
        self.assertTrue(o['possible_water_missing_H']);self.assertFalse(o['water_identity_confirmed'])
    def test_carbonyl_oxygen_is_not_auto_water(self):
        o=screen(CELL,OPS,[atom('O1','O',[.2,.2,.2]),atom('C1','C',[.325,.2,.2])])['donors'][0]
        self.assertFalse(o['possible_water_missing_H'])
    def test_metal_coordination_not_covalent_carbonyl(self):
        o=screen(CELL,OPS,[atom('O1','O',[.2,.2,.2]),atom('Co1','Co',[.4,.2,.2])])['donors'][0]
        self.assertTrue(o['possible_water_missing_H']);self.assertTrue(o['heavy_contacts'][0]['metal'])
    def test_shared_H_ambiguous_not_assigned_twice(self):
        r=screen(CELL,OPS,[atom('O1','O',[.2,.2,.2]),atom('H1','H',[.29,.2,.2]),atom('O2','O',[.38,.2,.2])])
        self.assertEqual(len(r['ambiguous_hydrogens']),1)
        self.assertEqual(sum(len(x['hydrogens']) for x in r['donors']),0)
    def test_incompatible_parts_excluded(self):
        r=screen(CELL,OPS,[atom('O1','O',[.2,.2,.2],1),atom('H1','H',[.284,.2,.2],2)])
        self.assertEqual(len(r['donors'][0]['hydrogens']),0)
    def test_periodic_parent_image_geometry(self):
        r=screen(CELL,OPS,[atom('O1','O',[.98,.2,.2]),atom('H1','H',[.064,.2,.2]),atom('O2','O',[.26,.2,.2])])
        h=r['donors'][0]['hydrogens'][0]
        self.assertEqual(h['parent_translation'],[-1,0,0]);self.assertAlmostEqual(h['contacts'][0]['D_H_A_degrees'],180)
    def test_all_translations_not_just_nearest(self):
        cell=gemmi.UnitCell(2,10,10,90,90,90)
        r=images(cell,OPS,[.2,.2,.2],[.3,.2,.2],2.4)
        self.assertEqual({tuple(v['translation']) for v in r},{(-1,0,0),(0,0,0),(1,0,0)})
    def test_skew_cell_matches_bruteforce(self):
        cell=gemmi.UnitCell(4,5,6,71,82,63);origin=[.2,.8,-.3];target=[.9,-.2,.4]
        r=images(cell,OPS,origin,target,3.2)
        brute=set()
        import itertools
        for shift in itertools.product(range(-3,4),repeat=3):
            d=cell.orthogonalize(gemmi.Fractional(*[target[i]+shift[i]-origin[i] for i in range(3)])).length()
            if .001<d<3.2:brute.add(shift)
        self.assertEqual({tuple(x['translation']) for x in r},brute)
    def test_special_symmetry_duplicate_image_deduplicated(self):
        r=images(CELL,[gemmi.Op('x,y,z'),gemmi.Op('-x,-y,-z')],[.08,0,0],[0,0,0],1.5)
        self.assertEqual(len(r),1)
    def test_unknown_part_never_unique_assignment(self):
        r=screen(CELL,OPS,[atom('O1','O',[.2,.2,.2]),atom('H1','H',[.284,.2,.2],None)])
        self.assertEqual(len(r['ambiguous_hydrogens']),1)
    def test_incompatible_contact_retained_without_accepting_H_bond(self):
        r=screen(CELL,OPS,[atom('O1','O',[.2,.2,.2],1),atom('H1','H',[.284,.2,.2],1),atom('O2','O',[.48,.2,.2],2)])
        c=r['donors'][0]['hydrogens'][0]['contacts'][0]
        self.assertFalse(c['part_compatible']);self.assertFalse(c['geometric_screen'])
    def test_reported_Q_not_asserted_new_map(self):
        r=screen(CELL,OPS,[atom('O1','O',[.2,.2,.2])],[dict(label='Q1',xyz=[.284,.2,.2],height=.6)])
        self.assertEqual(len(r['donors'][0]['nearby_reported_Q_peaks']),1)
    def test_mismatched_context_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            for e in ['cif','res']:(d/('case.'+e)).write_text('fixture')
            with patch('donor_audit.structure',return_value=(None,CELL,OPS,[{'res_context_status':'missing'}],{})):
                with self.assertRaisesRegex(ValueError,'contexts'):audit(d)

class ReflectionEvidenceTests(unittest.TestCase):
    def formula(self,s):
        doc=gemmi.cif.Document();b=doc.add_new_block('t');b.set_pair('_refine_ls_weighting_details',gemmi.cif.quote(s))
        return standard_weights(b)[0]
    def test_native_CIF_markup_formula(self):
        self.assertEqual(self.formula(r'w=1/[\s^2^(Fo^2^)+(0.0218P)^2^+1.5155P] where P=(Fo^2^+2Fc^2^)/3'),(.0218,1.5155))
    def test_plain_formula(self):
        self.assertEqual(self.formula('w=1/[sigma^2(Fo^2)+(0.04P)^2+0P] where P=(Fo^2+2Fc^2)/3'),(.04,0))
    def test_extended_formula_not_guessed(self):
        self.assertIsNone(self.formula('w=1/[sigma^2(Fo^2)+(0.04P)^2+0P+sin(theta)] where P=(Fo^2+2Fc^2)/3'))
    def test_negative_weight_rejected(self):
        self.assertIsNone(self.formula('w=1/[sigma^2(Fo^2)+(0.04P)^2+-2P] where P=(Fo^2+2Fc^2)/3'))
    def test_sigma_and_sigmaW_differ(self):
        r=row_metrics([1,0,0],200,100,2,CELL,.71073,(.1,1))
        self.assertEqual(r['delta_over_sigma'],50)
        self.assertLess(r['delta_over_sigmaW'],10)
    def test_negative_Fo_uses_zero_only_in_P(self):
        r=row_metrics([1,0,0],-10,30,2,CELL,.71073,(.1,1))
        self.assertAlmostEqual(r['sigmaW'],math.sqrt(28));self.assertAlmostEqual(r['delta_over_sigmaW'],-40/math.sqrt(28))
    def test_missing_weight_null_not_zero(self):
        r=row_metrics([1,0,0],-10,30,2,CELL,None,None)
        self.assertIsNone(r['delta_over_sigmaW']);self.assertIsNone(r['theta_degrees'])
    def test_theta_from_hkl_and_wavelength(self):
        r=row_metrics([1,0,0],100,100,1,CELL,1,(0,0))
        self.assertAlmostEqual(r['theta_degrees'],math.degrees(math.asin(.05)))
    def test_invalid_sigma(self):
        for s in [0,-1,float('nan')]:
            with self.assertRaises(ValueError):row_metrics([1,0,0],1,1,s,CELL,1,None)
    def test_zero_reflection_rejected(self):
        with self.assertRaises(ValueError):row_metrics([0,0,0],1,1,1,CELL,1,None)
    def test_route_deduplicates_and_does_not_call_unrelated_tools(self):
        with tempfile.TemporaryDirectory() as t,patch('donor_audit.audit',return_value={'status':'evidence_ready','seconds':.1}) as h,patch('reflection_audit.audit') as f:
            r=collect(t,[{'code':'306'},{'code':'420'}],Path(t)/'out')
            self.assertEqual(len(r),1);h.assert_called_once();f.assert_not_called()
    def test_one_failed_tool_does_not_hide_other_tool(self):
        with tempfile.TemporaryDirectory() as t,patch('donor_audit.audit',side_effect=ValueError('bad pairing')),patch('reflection_audit.audit',return_value={'status':'evidence_ready','seconds':.1}):
            r=collect(t,[{'code':'306'},{'code':'934'}],Path(t)/'out')
            results={x['tool']:x for x in r}
            self.assertEqual(results['donor-audit']['status'],'failed')
            self.assertEqual(results['reflection-audit']['status'],'evidence_ready')
            self.assertIsNone(results['donor-audit']['path'])
            self.assertIn('resolution-shells',results)

if __name__=='__main__':unittest.main()
