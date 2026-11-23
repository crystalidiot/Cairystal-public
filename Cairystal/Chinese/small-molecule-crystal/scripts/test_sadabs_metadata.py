import tempfile,unittest
from pathlib import Path
from experiment_metadata_state import sadabs_fields,append_sadabs_details
import gemmi

class Sadabs(unittest.TestCase):
 def test_native_citation_preserved_when_appending_output_note(self):
  old=gemmi.cif.quote('SADABS 2016/2: native citation');new=gemmi.cif.quote('SADABS-2016/2; mu*r=0.2; uncertain applicability')
  result=append_sadabs_details(old,new)
  self.assertIn('native citation',gemmi.cif.as_string(result));self.assertIn('uncertain applicability',gemmi.cif.as_string(result));self.assertEqual(append_sadabs_details(result,new),result)
 def test_different_version_or_parameter_not_merged(self):
  self.assertIsNone(append_sadabs_details("'SADABS 2014/1'","'SADABS-2016/2'"))
  self.assertIsNone(append_sadabs_details("'SADABS 2016/2 mu*r=0.5'","'SADABS-2016/2 mu*r=0.2'"))
 def fixture(self,p):
  h=p/'sample.hkl';h.write_text('   1   0   0  100.00   10.00\n   0   0   0    0.00    0.00\n')
  a=p/'sample.abs';a.write_text(' SADABS-2016/2 - Bruker AXS\nApproximate wavelength .12345\n 1 Corrected reflections written to file sample.hkl\nEstimated minimum and maximum transmission: 0.2 0.8\nAdditional spherical absorption correction applied with mu*r = 2.0\n')
  return a,h
 def test_output_only(self):
  with tempfile.TemporaryDirectory() as td:
   fields,loc=sadabs_fields(*self.fixture(Path(td)))
   self.assertEqual(fields['_exptl_absorpt_correction_T_min'],'0.2');self.assertNotIn('_diffrn_radiation_wavelength',fields)
   self.assertIn('unverified',fields['_exptl_absorpt_process_details'])
 def test_mismatching_count(self):
  with tempfile.TemporaryDirectory() as td:
   a,h=self.fixture(Path(td));a.write_text(a.read_text().replace('1 Corrected','2 Corrected'))
   with self.assertRaises(ValueError):sadabs_fields(a,h)
 def test_mismatching_output_name(self):
  with tempfile.TemporaryDirectory() as td:
   a,h=self.fixture(Path(td));a.write_text(a.read_text().replace('sample.hkl','other.hkl'))
   with self.assertRaises(ValueError):sadabs_fields(a,h)
 def test_ambiguous_output_sections(self):
  with tempfile.TemporaryDirectory() as td:
   a,h=self.fixture(Path(td));a.write_text(a.read_text()*2)
   with self.assertRaises(ValueError):sadabs_fields(a,h)

if __name__=='__main__':unittest.main()
