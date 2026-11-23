import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import gemmi
from cif_text_preflight import check_ascii,encode_narratives,add_assistance_comment,CAIRYSTAL_COMMENT
from report_method_templates import narrative_digest
from prepare_validation_metadata import snapshot

class TextBoundaryTests(unittest.TestCase):
    def fixture(self,p,text='Recorded path D:\\中文\\decisions.json'):
        d=gemmi.cif.read_string('data_test\n_cell_length_a 7.123(4)\nloop_\n_atom_site_label\n_atom_site_fract_x\nC1 .12345\n_shelx_res_file\n;SFAC C H\nC1 1 .1 .2 .3 11 .02\n;\n_shelx_hkl_file\n;   1   0   0   25.0   1.0\n;\n')
        d.sole_block().set_pair('_publ_section_exptl_refinement',gemmi.cif.quote(text));d.write_file(str(p))
    def test_unicode_path_reversible_only_narrative_changes(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.cif';self.fixture(p);before=snapshot(gemmi.cif.read_file(str(p)))
            rec=encode_narratives(p,Path(t)/'audit.json');check_ascii(p)
            after=snapshot(gemmi.cif.read_file(str(p)))
            for tag,value in before['test'].items():
                if tag!='_publ_section_exptl_refinement':self.assertEqual(after['test'][tag],value)
            v=gemmi.cif.as_string(gemmi.cif.read_file(str(p)).sole_block().find_value('_publ_section_exptl_refinement'))
            self.assertEqual(json.loads(v.split('\n',1)[1]),rec['changes'][0]['original_utf8'])
            self.assertTrue(Path(rec['original_file']).exists())
    def test_ascii_no_change_and_repeat_safe(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.cif';self.fixture(p,'ASCII narrative');before=p.read_bytes()
            self.assertEqual(encode_narratives(p,Path(t)/'audit.json')['changes'],[])
            self.assertEqual(p.read_bytes(),before)
    def test_assistance_preserves_all_data_and_original_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.cif';self.fixture(p,'ASCII narrative');raw=p.read_bytes().replace(b'\r\n',b'\n');p.write_bytes(raw)
            before=snapshot(gemmi.cif.read_file(str(p)))
            result=add_assistance_comment(p,Path(t)/'credit.json')
            self.assertEqual(p.read_bytes(),CAIRYSTAL_COMMENT+b'\n'+raw)
            self.assertEqual(snapshot(gemmi.cif.read_file(str(p))),before)
            self.assertEqual(Path(result['original_file']).read_bytes(),raw)
            self.assertTrue(result['all_cif_values_unchanged'])
    def test_assistance_repeat_has_identical_hash(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.cif';self.fixture(p,'ASCII')
            first=add_assistance_comment(p,Path(t)/'credit1.json');raw=p.read_bytes()
            second=add_assistance_comment(p,Path(t)/'credit2.json')
            self.assertEqual(second['status'],'already_present')
            self.assertEqual(first['output_sha256'],second['output_sha256'])
            self.assertEqual(p.read_bytes(),raw)
    def test_assistance_keeps_version_declaration_and_crlf(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.cif'
            header=b'#\\#CIF_1.1\r\n';rest=b'data_x\r\n_cell_length_a 7.123(4)\r\n'
            p.write_bytes(header+rest);add_assistance_comment(p,Path(t)/'credit.json')
            self.assertEqual(p.read_bytes(),header+CAIRYSTAL_COMMENT+b'\r\n'+rest)
    def test_assistance_text_field_is_not_header_credit(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.cif'
            raw=b'data_x\n_note\n;\n'+CAIRYSTAL_COMMENT+b'\n;\n'
            p.write_bytes(raw);before=snapshot(gemmi.cif.read_file(str(p)))
            add_assistance_comment(p,Path(t)/'credit.json')
            self.assertEqual(p.read_bytes(),CAIRYSTAL_COMMENT+b'\n'+raw)
            self.assertEqual(snapshot(gemmi.cif.read_file(str(p))),before)
    def test_assistance_invalid_input_is_not_modified(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.cif';raw=b'data_x\n_tag\n';p.write_bytes(raw)
            with self.assertRaises(Exception):add_assistance_comment(p,Path(t)/'credit.json')
            self.assertEqual(p.read_bytes(),raw)
            self.assertFalse((Path(t)/'credit.before.cif').exists())
    def test_assistance_existing_audit_not_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.cif';self.fixture(p,'ASCII');raw=p.read_bytes()
            a=Path(t)/'credit.json';a.write_text('preserve',encoding='ascii')
            with self.assertRaisesRegex(ValueError,'audit already exists'):add_assistance_comment(p,a)
            self.assertEqual(p.read_bytes(),raw);self.assertEqual(a.read_text('ascii'),'preserve')
    def test_assistance_unsupported_cif_version_not_modified(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.cif';raw=b'#\\#CIF_2.0\ndata_x\n_tag value\n';p.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'CIF1 only'):add_assistance_comment(p,Path(t)/'credit.json')
            self.assertEqual(p.read_bytes(),raw)
    def test_non_ascii_label_blocks_without_mutation(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.cif';self.fixture(p);p.write_text(p.read_text('utf-8').replace('C1 .12345',"'碳1' .12345"),encoding='utf-8');before=p.read_bytes()
            with self.assertRaisesRegex(ValueError,'outside'):encode_narratives(p,Path(t)/'audit.json')
            self.assertEqual(p.read_bytes(),before)
    def test_invalid_cif_never_fetches(self):
        from iucr_validation import validate
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.cif';self.fixture(p)
            with patch('iucr_validation.fetch') as fetch:
                with self.assertRaisesRegex(ValueError,'no upload'):validate(p,Path(t)/'official',authorized=True)
                fetch.assert_not_called()
    def test_control_character_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.cif';p.write_bytes(b'data_x\n# bad\x00\n')
            with self.assertRaisesRegex(ValueError,'line 2'):check_ascii(p)
    def test_digest_keeps_limitations_without_copying_logs(self):
        raw='Recorded plan abc: long English debug log\nOriginal absorption processing records an additional spherical mu*r=1.2340. Physical applicability needs review.\nOriginal processing transmission limits: 0.0123 to 0.0456.'
        d=narrative_digest({'_publ_section_exptl_refinement':raw})
        self.assertEqual(d['original_records']['_publ_section_exptl_refinement'],raw)
        self.assertNotIn('Recorded plan',d['zh']);self.assertIn('1.2340',d['zh']);self.assertIn('0.0456',d['zh']);self.assertIn('full_audit_records.json',d['zh'])
        self.assertIn('1.2340',d['en']);self.assertIn('review',d['en'])
        self.assertNotIn('1.2340.',d['zh']);self.assertNotIn('1.2340.;',d['en'])
    def test_encoded_source_digest_preserves_exact_unicode(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.cif';self.fixture(p);rec=encode_narratives(p,Path(t)/'audit.json')
            text=gemmi.cif.as_string(gemmi.cif.read_file(str(p)).sole_block().find_value('_publ_section_exptl_refinement'))
            self.assertEqual(narrative_digest({'_publ_section_exptl_refinement':text})['original_records']['_publ_section_exptl_refinement'],rec['changes'][0]['original_utf8'])

if __name__=='__main__':unittest.main()
