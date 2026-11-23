"""Regressions for observed integration failures; synthetic inputs, no answer models."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
import gemmi
from crystal_runtime import compare_cell_tokens,local_validation
from compare_diagnostic_trials import changes,compare
from candidate_trials import metadata_copy
from ab_auto import generate_requests,load_policy,rank_rows
from report_autoqa import body_content

TAGS=['_cell_length_a','_cell_length_b','_cell_length_c','_cell_angle_alpha','_cell_angle_beta','_cell_angle_gamma']
def block(angle='74.05(8)',volume='1000(2)'):
 d=gemmi.cif.Document();b=d.add_new_block('synthetic')
 for tag,value in zip(TAGS,['10.000','10.000','10.000',angle,'90.000','90.000']):b.set_pair(tag,value)
 b.set_pair('_diffrn_radiation_wavelength','0.71073')
 if volume is not None:b.set_pair('_cell_volume',volume)
 return d

class CellPrecision(unittest.TestCase):
 def test_two_decimal_rounding_is_not_a_different_cell(self):
  result=compare_cell_tokens(block().sole_block(),block('74.051').sole_block())
  self.assertAlmostEqual(result['_cell_angle_alpha']['difference'],.001)
 def test_standard_uncertainty_does_not_hide_change(self):
  with self.assertRaises(ValueError):compare_cell_tokens(block('74.05(99)').sole_block(),block('74.06(99)').sole_block())
 def test_precision_mismatch_not_hidden_by_old_fixed_tolerance(self):
  with self.assertRaises(ValueError):compare_cell_tokens(block('74.05100').sole_block(),block('74.05150').sole_block())
 def test_missing_values_rejected(self):
  with self.assertRaises(ValueError):compare_cell_tokens(block('?').sole_block(),block().sole_block())
 def test_integer_symmetry_angle_not_one_degree_tolerance(self):
  with self.assertRaises(ValueError):compare_cell_tokens(block('90').sole_block(),block('90.2').sole_block())
 def test_scientific_notation_precision(self):
  compare_cell_tokens(block('7.405E1').sole_block(),block('74.051').sole_block())

def alert(text='Atom C6 has ADP max/min Ratio ..... 4.3 prolat',**kw):
 return dict({'code':'213','type':2,'level':'B','text':text,'atom_labels':['C6']},**kw)

class AlertIdentity(unittest.TestCase):
 def test_ratio_change_retained_as_same_warning(self):
  v=changes([alert()],[alert('Atom C6 has ADP max/min Ratio ..... 4.1 prolat')])
  self.assertEqual(len(v['unchanged']),1);self.assertEqual(len(v['value_changed']),1);self.assertFalse(v['added'] or v['removed'])
 def test_duplicate_counts_preserved(self):
  v=changes([alert(),alert()],[alert()]);self.assertEqual(len(v['removed']),1)
 def test_atom_suffix_and_symmetry_are_not_ignored(self):
  for replacement in [alert(atom_labels=['C6B']),alert(symmetry_code='2_655'),alert(part=2)]:
   self.assertEqual(len(changes([alert()],[replacement])['added']),1)
 def test_severity_change_is_real(self):self.assertEqual(len(changes([alert()],[alert(level='A')])['added']),1)
 def test_unknown_payload_not_masked(self):
  self.assertEqual(len(changes([alert(code='999')],[alert('Atom C6 has ADP max/min Ratio ..... 4.1 prolat',code='999')])['added']),1)
 def test_failed_validation_is_not_zero_AB(self):
  v=compare({},dict(status='failed',AB=[]));self.assertIsNone(v['AB_counts']);self.assertIsNone(v['AB'])
 def test_missing_AB_cannot_be_priority_candidate(self):
  v=rank_rows([dict(status='completed',comparison_context_verified=True,source_unchanged=True,flags=[])])[0]
  self.assertFalse(v['eligible_for_priority'])

class MetadataLineage(unittest.TestCase):
 def prepare(self,root,volume='1000(2)'):
  base=root/'base';native=root/'native';base.mkdir();native.mkdir()
  for p in (base,native):
   (p/'case.hkl').write_text('same measured reflections')
   (p/'case.res').write_text('CELL .71073 10 10 10 90 90 90\nLATT -1\nSFAC C\nUNIT 1\nHKLF 4\n')
  block('90.000',volume).write_file(str(base/'case.cif'))
  block('90.000','1000.0(1)').write_file(str(native/'case.cif'))
  (native/'case.fcf').write_text('data_factors\n')
  return base,native,root/'out'
 def test_volume_uncertainty_preserved(self):
  with tempfile.TemporaryDirectory() as td:
   args=self.prepare(Path(td));metadata_copy(*args)
   self.assertEqual(gemmi.cif.read_file(str(args[2]/'case.cif')).sole_block().find_value('_cell_volume'),'1000(2)')
 def test_unknown_volume_does_not_invent_uncertainty(self):
  for v in (None,'?','.'):
   with tempfile.TemporaryDirectory() as td:
    args=self.prepare(Path(td),v);metadata_copy(*args)
    self.assertEqual(gemmi.cif.read_file(str(args[2]/'case.cif')).sole_block().find_value('_cell_volume'),v or '?')
 def test_different_hkl_cannot_supply_metadata(self):
  with tempfile.TemporaryDirectory() as td:
   args=self.prepare(Path(td));(args[1]/'case.hkl').write_text('different')
   self.assertRaises(ValueError,metadata_copy,*args);self.assertFalse(args[2].exists())
 def test_changed_native_cell_rejected_even_if_su_large(self):
  with tempfile.TemporaryDirectory() as td:
   args=self.prepare(Path(td));p=args[1]/'case.res';p.write_text(p.read_text().replace('10 10 10','11 10 10'))
   self.assertRaises(ValueError,metadata_copy,*args)
 def test_bad_volume_source_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   args=self.prepare(Path(td),'800(2)');self.assertRaises(ValueError,metadata_copy,*args)

class FailureAndLayout(unittest.TestCase):
 def test_timeout_records_null_validated_counts(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);frozen=root/'frozen';frozen.mkdir();exe=root/'platon.exe';exe.write_bytes(b'synthetic')
   (frozen/'case.cif').write_text('data_x\n_a 1\n');(frozen/'case.fcf').write_text('data_y\n_a 1\n')
   process=MagicMock();process.poll.return_value=None;process.returncode=-1
   with patch('crystal_runtime.subprocess.Popen',return_value=process),patch('platon_execution.rules_context',return_value={}),patch('platon_execution.native_versions',return_value={}):
    with self.assertRaises(ValueError):local_validation(exe,frozen,root/'val','case',timeout=0)
   v=json.loads((root/'val/local_validation.json').read_text());self.assertEqual(v['state'],'timeout')
   self.assertIsNone(v['alerts']);self.assertIsNone(v['validated_counts']);self.assertFalse(v['validation_complete']);self.assertIn('failure_reason',v)
 def test_only_footer_is_empty_body(self):
  page=MagicMock(height=792,chars=[{'text':'Page 4','top':750,'bottom':762}],images=[],curves=[])
  self.assertFalse(any(body_content(page,(47,47)).values()))
 def test_figure_only_page_counts_as_content(self):
  page=MagicMock(height=792,chars=[],images=[{'top':100,'bottom':300}],curves=[])
  self.assertEqual(body_content(page,(47,47))['body_images'],1)
 def test_one_line_body_is_not_empty(self):
  page=MagicMock(height=792,chars=[{'text':'Note','top':100,'bottom':112}],images=[],curves=[])
  self.assertEqual(body_content(page,(47,47))['body_characters'],1)

class DisorderRouting(unittest.TestCase):
 def test_neighbor_disorder_precedes_Ueq_type_scan(self):
  a=dict(label='N1',res_label='N1',element='N',part=0,occupancy=1.,res_context_status='matched')
  p={'all_atoms':[a],'regions':[dict(a,neighbors=[dict(label='O1A',element='O',part=1,occupancy=.4,within_covalent_radius_screen=True,part_compatible=True)])],'AB_alerts':[dict(code='242',level='B',text='Low Ueq N1',atom_labels=['N1'])]}
  requests,findings=generate_requests(p,{'atoms':[],'sfac':['C','N','O']},load_policy())
  self.assertFalse(requests);self.assertIn('disordered/partial',findings[0]['reason'])

if __name__=='__main__':unittest.main()
