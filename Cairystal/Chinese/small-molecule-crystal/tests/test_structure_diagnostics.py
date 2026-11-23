import unittest,math,tempfile
from pathlib import Path
import gemmi
from structure_diagnostics import cartesian_tensor,nearest_images,compatible,res_records,number

class DiagnosticsTests(unittest.TestCase):
 def test_orthogonal_tensor(self):
  c=gemmi.UnitCell(10,11,12,90,90,90);u=[.03,.04,.06,.002,.003,.004]
  t=cartesian_tensor(c,u)
  for x,y in zip(t.elements_pdb(),u):self.assertAlmostEqual(x,y,places=12)
 def test_oblique_isotropic_metric(self):
  c=gemmi.UnitCell(10,11,12,75,105,112);rc=c.reciprocal();u=.04
  vals=[u,u,u,u*math.cos(math.radians(rc.gamma)),u*math.cos(math.radians(rc.beta)),u*math.cos(math.radians(rc.alpha))]
  t=cartesian_tensor(c,vals)
  for x in t.calculate_eigenvalues():self.assertAlmostEqual(x,u,places=11)
 def test_not_raw_diagonal_mean(self):
  c=gemmi.UnitCell(10,11,12,80,100,115);t=cartesian_tensor(c,[.03,.04,.05,.01,.02,.015])
  self.assertGreater(abs(t.trace()/3-.04),.001)
 def test_npd_is_retained(self):
  t=cartesian_tensor(gemmi.UnitCell(10,10,10,90,90,90),[-.01,.04,.05,0,0,0])
  self.assertLess(min(t.calculate_eigenvalues()),0)
 def test_periodic_contact(self):
  v=nearest_images(gemmi.UnitCell(10,10,10,90,90,90),[gemmi.Op('x,y,z')],[.95,0,0],[.05,0,0],2)
  self.assertEqual(v[0]['translation'],[1,0,0]);self.assertAlmostEqual(v[0]['distance'],1)
  self.assertAlmostEqual(v[0]['vector_cart'][0],1)
 def test_same_atom_symmetry_mate(self):
  v=nearest_images(gemmi.UnitCell(10,10,10,90,90,90),[gemmi.Op('x,y,z'),gemmi.Op('-x,-y,-z')],[.05,0,0],[.05,0,0],2)
  self.assertEqual(len(v),1);self.assertAlmostEqual(v[0]['distance'],1)
 def test_alternative_parts_not_bond(self):
  self.assertFalse(compatible({'part':1},{'part':2},'x,y,z',[0,0,0]))
  self.assertTrue(compatible({'part':0},{'part':2},'x,y,z',[0,0,0]))
 def test_unknown_context_is_not_assumed(self):
  self.assertIsNone(compatible({'part':None},{'part':0},'x,y,z',[0,0,0]))
 def test_missing_numeric_not_zero(self):
  self.assertIsNone(number('?'));self.assertIsNone(number('.'));self.assertEqual(number('0.04(2)'),.04)
 def test_res_metadata_and_peak_boundary(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.res';p.write_text('SFAC C H\nFVAR 1 .3\nPART 1\nC1 1 .1 .2 .3 21 .1 .2 .3 =\n .01 .02 .03\nAFIX 23\nH1 2 .1 .2 .4 21 -1.2\nHKLF 4\nEND\nWGHT .2\nQ1 1 .2 .3 .4 11 .05 1.3\n',encoding='ascii')
   r=res_records(p);self.assertEqual(len(r['atoms']),2);self.assertEqual(r['atoms'][0]['part'],1)
   self.assertEqual(r['atoms'][1]['afix'],23);self.assertEqual(r['peaks'][0]['height'],1.3)
   self.assertNotIn('WGHT .2',r['controls'])

if __name__=='__main__':unittest.main(verbosity=2)
