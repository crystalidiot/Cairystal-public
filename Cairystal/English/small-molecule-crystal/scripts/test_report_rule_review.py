"""Synthetic scientific and rendered-layout regressions; no historical models."""
import tempfile,unittest,json,argparse
from pathlib import Path
from scientific_report_rules import moiety,excluded_acceptors,basic_findings
from report_autoqa import check_chars,normalize,check_document
from crystal_delivery import finalize

def atom(k,e,q=0,h=0):return {'id':k,'element':e,'formal_charge':q,'hydrogens':h}
def glyph(t,x,y,w=6,h=10):return {'text':t,'x0':x,'x1':x+w,'top':y,'bottom':y+h}

class Rules(unittest.TestCase):
    def test_formula_from_graph_not_model_name(self):
        g={'atoms':[atom('c','C',h=3),atom('o','O',h=1)],'bonds':[['c','o',1]]}
        self.assertEqual(moiety(g),'C H4 O')
    def test_free_halide_not_excluded(self):
        g={'atoms':[atom('cl','Cl',-1)],'bonds':[]}
        self.assertEqual(excluded_acceptors(g,{'cl':'CL7'}),{})
    def test_oxohalogen_and_cationic_n_excluded(self):
        g={'atoms':[atom('cl','Cl'),atom('n','N',1),*[atom(f'o{i}','O') for i in range(4)]], 'bonds':[['cl',f'o{i}',1] for i in range(4)]}
        result=excluded_acceptors(g,{x['id']:x['id'].upper() for x in g['atoms']})
        self.assertEqual(set(result),{'CL','N'})
    def test_npd_and_charge_unknown_do_not_pass(self):
        m={'NPD_atoms':1,'last_abs_max_shift_esd':.1,'R1_observed':.04,'GooF':1}
        p={'local_adp_flags':[],'residual_density':[.4,-.4]}
        issues=basic_findings(m,p,{'atoms':[atom('n','N',1)]})
        self.assertEqual(len(issues),3)
    def test_large_residual_and_unsupported_element_escalate(self):
        m={'NPD_atoms':0,'last_abs_max_shift_esd':0,'R1_observed':.04,'GooF':1}
        issues=basic_findings(m,{'local_adp_flags':[],'residual_density':[2,-.3]},{'atoms':[atom('b','Bi')]})
        self.assertEqual(len(issues),2)
    def test_nonfinite_metric_escalates(self):
        m={'NPD_atoms':0,'last_abs_max_shift_esd':0,'R1_observed':float('nan'),'GooF':1}
        self.assertTrue(basic_findings(m,{'residual_density':[.2,-.2]},{'atoms':[atom('c','C')]}))

class Layout(unittest.TestCase):
    def test_clean_adjacent_glyphs(self):self.assertEqual(check_chars([glyph('A',20,20),glyph('B',26,20)],100,100),[])
    def test_major_overlap(self):self.assertTrue(any(i['kind']=='major_text_overlap' for i in check_chars([glyph('A',20,20),glyph('B',21,20)],100,100)))
    def test_raised_digit_low_punctuation_advance_box_overhang(self):self.assertEqual(check_chars([glyph('³',20,20,w=5),glyph(';',23.36,20,w=2.7)],100,100),[])
    def test_raised_digit_real_major_overlap_still_flagged(self):self.assertTrue(check_chars([glyph('³',20,20,w=5),glyph(';',20.2,20,w=2.7)],100,100))
    def test_page_overflow(self):self.assertEqual(check_chars([glyph('A',99,20)],100,100)[0]['kind'],'page_edge_overflow')
    def test_unmapped_glyph(self):self.assertEqual(check_chars([glyph('\ufffd',20,20)],100,100)[0]['kind'],'unmapped_glyph')
    def test_subscript_and_spaces_normalize(self):self.assertEqual(normalize('H₂ O\n'),normalize('H2O'))
    def rendered(self,source,printed,duplicate=False):
        from docx import Document
        from reportlab.pdfgen import canvas
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);d=Document();d.add_paragraph(source);d.save(p/'x.docx')
            c=canvas.Canvas(str(p/'x.pdf'));c.drawString(72,700,printed)
            if duplicate:c.drawString(72,700,printed)
            c.save()
            return check_document(p/'x.docx',p/'x.pdf',[{'path':'synthetic-preview'}])
    def test_real_pdf_text_preservation(self):self.assertEqual(self.rendered('C2 H6 O 0.0481','C2 H6 O 0.0481')['status'],'automatic_checks_passed')
    def test_real_pdf_missing_content(self):self.assertEqual(self.rendered('C2 H6 O 0.0481','C2 H6 O')['global_issues'][0]['kind'],'source_text_missing_after_render')
    def test_real_pdf_duplicate_overlay(self):self.assertEqual(self.rendered('C2 H6 O','C2 H6 O',True)['status'],'needs_review')
    def test_failed_autoqa_cannot_seal(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'result.json').write_text(json.dumps({'status':'awaiting_visual_review'}));(p/'qa.json').write_text(json.dumps({'status':'needs_review','visual_review_performed':False}))
            with self.assertRaisesRegex(ValueError,'Automatic QA must pass'):finalize(argparse.Namespace(run=td,automatic_qa=str(p/'qa.json')))
    def test_autoqa_cannot_claim_visual_review(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'result.json').write_text(json.dumps({'status':'awaiting_visual_review'}));(p/'qa.json').write_text(json.dumps({'status':'automatic_checks_passed','visual_review_performed':True}))
            with self.assertRaises(ValueError):finalize(argparse.Namespace(run=td,automatic_qa=str(p/'qa.json')))

if __name__=='__main__':unittest.main()
