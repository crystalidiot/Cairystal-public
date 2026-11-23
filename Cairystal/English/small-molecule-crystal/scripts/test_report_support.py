import json,tempfile,unittest,zipfile
from pathlib import Path
from docx import Document
from docx.shared import Pt
from report_typography import apply,scientific,space_group,formula,contact_text
from support_report import record,try_record

class Typography(unittest.TestCase):
 def test_scalar_and_units(self):
  d=Document();p=d.add_paragraph();scientific(p,'a / b / c / Å; V / Å³; Z; R1 / wR2; μ / mm⁻¹',True)
  self.assertTrue(next(r for r in p.runs if r.text=='a').italic)
  self.assertTrue(next(r for r in p.runs if r.text=='R').italic)
  self.assertTrue(next(r for r in p.runs if r.text=='1').font.subscript)
  self.assertTrue(next(r for r in p.runs if r.text=='wR').italic)
  self.assertFalse(next(r for r in p.runs if 'Å;' in r.text).italic)
 def test_u_descriptors_upright_indices_italic(self):
  d=Document();p=d.add_paragraph();scientific(p,'Ueq Uiso Uij U11')
  self.assertTrue(next(r for r in p.runs if r.text=='eq').font.subscript)
  self.assertFalse(next(r for r in p.runs if r.text=='eq').italic)
  self.assertTrue(next(r for r in p.runs if r.text=='ij').italic)
  self.assertFalse(next(r for r in p.runs if r.text=='11').italic)
 def test_formula_does_not_change_text_or_case(self):
  d=Document();p=d.add_paragraph();formula(p,'2(C12 H14 Cl2) 2+')
  self.assertEqual(p.text,'2(C12 H14 Cl2) 2+')
  self.assertTrue(next(r for r in p.runs if r.text=='12').font.subscript)
  self.assertFalse(next(r for r in p.runs if r.text=='Cl').italic)
 def test_spacegroup_screw_subscript(self):
  d=Document();p=d.add_paragraph();self.assertTrue(space_group(p,'P 21/c'))
  self.assertEqual(p.text,'P 21/c')
  self.assertTrue(next(r for r in p.runs if r.text=='1').font.subscript)
  self.assertTrue(next(r for r in p.runs if r.text=='P').italic)
 def test_spacegroup_negative_bar(self):
  d=Document();p=d.add_paragraph();self.assertTrue(space_group(p,'P -1'));self.assertIn('1\u0305',p.text)
 def test_unrecognized_group_no_inference(self):
  d=Document();p=d.add_paragraph();self.assertFalse(space_group(p,'UNKNOWN_X'));self.assertEqual(p.text,'UNKNOWN_X')
 def test_atom_labels_and_coordinate_values_preserved(self):
  d=Document();t=d.add_table(rows=1,cols=2);t.rows[0].cells[0].text='Item';t.rows[0].cells[1].text='Result'
  r=t.add_row();r.cells[0].text='R1 / wR2';r.cells[1].text='0.0304 / 0.0793'
  u=d.add_table(rows=1,cols=2);u.rows[0].cells[0].text='Atom';u.rows[0].cells[1].text='Ueq/Uiso'
  r=u.add_row();r.cells[0].text='C34B';r.cells[1].text='0.024(3)'
  u.rows[0].cells[1].paragraphs[0].runs[0].font.size=Pt(9)
  apply(d)
  self.assertEqual(u.rows[1].cells[0].text,'C34B');self.assertEqual(u.rows[1].cells[1].text,'0.024(3)')
  self.assertEqual(t.rows[1].cells[1].text,'0.0304 / 0.0793')
  self.assertTrue(all(r.font.size==Pt(9) for r in u.rows[0].cells[1].paragraphs[0].runs))
 def test_contact_once_and_case(self):
  self.assertIn('caizhuoerr@qq.com',contact_text());self.assertIn('crystal-idiot',contact_text(False))

class Feedback(unittest.TestCase):
 def setup_run(self,td):
  p=Path(td);(p/'result.json').write_text('{}');(p/'model.cif').write_text('private molecular coordinates');return p
 def test_science_separate_from_execution_no_mutation(self):
  with tempfile.TemporaryDirectory() as td:
   p=self.setup_run(td);a=record(p,'scientific_decision','NPD remains','finish');b=record(p,'execution_error','process failed','solve')
   self.assertNotEqual(a['code'],b['code']);self.assertEqual((p/'model.cif').read_text(),'private molecular coordinates')
   x=json.loads((Path(a['directory'])/'incident.json').read_text('utf-8'));self.assertIsNone(x['confirmed_root_cause']);self.assertFalse(x['scientific_acceptance'])
 def test_share_zip_has_no_private_content_or_paths(self):
  with tempfile.TemporaryDirectory() as td:
   p=self.setup_run(td);secret='token=PRIVATE_42 at C:\\lab\\secret.cif';r=record(p,'execution_error',secret,'arbitrary/private path',ValueError(secret))
   with zipfile.ZipFile(r['share_zip']) as z:
    self.assertEqual(set(z.namelist()),{'feedback.json','README.txt'});text=''.join(z.read(n).decode() for n in z.namelist())
   for forbidden in ['PRIVATE_42','secret.cif','private molecular',td,'arbitrary/private']:self.assertNotIn(forbidden,text)
   self.assertIn(secret,json.loads((Path(r['directory'])/'incident.json').read_text('utf-8'))['observed_error'])
 def test_repeated_event_reuses_packet(self):
  with tempfile.TemporaryDirectory() as td:
   p=self.setup_run(td);a=record(p,'report_review','AB review','report');b=record(p,'report_review','AB review','report')
   self.assertEqual(a['id'],b['id']);self.assertTrue(b['cache_hit'])
 def test_no_input_folder_fallback(self):
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(ValueError):record(td,'execution_error','missing input')
   self.assertEqual(list(Path(td).iterdir()),[])
 def test_write_failure_keeps_original_error_visible(self):
  with tempfile.TemporaryDirectory() as td:
   x=try_record(td,'execution_error','original error');self.assertEqual(x['status'],'diagnostic_write_failed');self.assertTrue(x['original_error_preserved'])
 def test_autorun_stop_emits_packet(self):
  from crystal_autorun import stop,summary
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'autorun.json').write_text('{}');s={'actions':[],'options':{},'completed_actions':[]}
   stop(p,s,'execution_error','Synthetic command failure')
   self.assertTrue(Path(summary(p,s)['support_report']['share_zip']).is_file())
   self.assertEqual(s['status'],'needs_attention')
class ReleaseIntegrity(unittest.TestCase):
 def test_tamper_extra_and_traversal_rejected(self):
  import hashlib
  from verify_release import verify
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);root=p/'skill';root.mkdir();f=root/'x.py';f.write_text('original')
   m=p/'manifest.json';m.write_text(json.dumps({'x.py':hashlib.sha256(f.read_bytes()).hexdigest()}))
   self.assertEqual(verify(root,m)['status'],'integrity_verified')
   f.write_text('changed')
   with self.assertRaises(ValueError):verify(root,m)
   f.write_text('original');(root/'extra.py').write_text('unexpected')
   with self.assertRaises(ValueError):verify(root,m)
   m.write_text(json.dumps({'../secret':'0'*64}))
   with self.assertRaises(ValueError):verify(root,m)
if __name__=='__main__':unittest.main()
