"""Questionnaire image handling and local preservation."""
from pathlib import Path
import base64,io,json,unittest,tempfile
from PIL import Image
from intake_once import export,extract_uploaded_diagram

class IntakeUpload(unittest.TestCase):
 def test_embedded_image_round_trip(self):
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp);buf=io.BytesIO();Image.new('RGB',(8,8),'white').save(buf,format='PNG');image=buf.getvalue()
   src=tmp/'input.json';src.write_text(json.dumps({'schema':1,'data_dir':str(tmp),'elements':['C','N','O','Cl'],'diagram_image_data_url':'data:image/png;base64,'+base64.b64encode(image).decode()}),encoding='utf-8')
   state,out=export(src,tmp/'out');path=Path(state['data']['diagram_path'])
   self.assertEqual(path.read_bytes(),image);self.assertEqual(path.parent,out)
   self.assertNotIn('diagram_image_data_url',state['data']);self.assertEqual(state['data']['iucr_upload'],'not_answered')
 def test_rejects_wrong_format_or_invalid_content(self):
  for item in ['data:image/svg+xml;base64,PHN2Zz4=', 'data:image/png;base64,Zm9v', 'data:image/png;base64,!!!!']:
   with self.subTest(item=item),self.assertRaises(ValueError):extract_uploaded_diagram({'diagram_image_data_url':item})
 def test_rejects_both_path_and_image(self):
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp);buf=io.BytesIO();Image.new('RGB',(8,8),'white').save(buf,format='PNG')
   src=tmp/'input.json';src.write_text(json.dumps({'schema':1,'data_dir':str(tmp),'elements':['C'],'diagram_path':'anything.png','diagram_image_data_url':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()}),encoding='utf-8')
   with self.assertRaises(ValueError):export(src,tmp/'out')
   self.assertFalse((tmp/'out').exists())
 def test_oversized_rejected(self):
  with self.assertRaises(ValueError):extract_uploaded_diagram({'diagram_image_data_url':'data:image/png;base64,'+'A'*12000000})
if __name__=='__main__':unittest.main()
