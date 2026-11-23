"""Cross-stage regressions for the 2026-11 workflow review."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import crystal_autorun as ar
import crystal_pipeline as cp
from crystal_runtime import read_hkl, write_json
from graph_assignment import select_trial
from inspect_case import reflection_stats
from pipeline_intake import validate_specimen
from test_graph_assignment import trial
from test_input_formats import record


class Boundaries(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)

    def test_incomplete_competitor_prevents_automatic_selection(self):
        for key in ('NPD_atoms','wR2','R1_observed','unique','last_abs_max_shift_esd'):
            for invalid in (None,float('nan'),-1,True):
                a,b=trial('a',.03),trial('b',.07)
                b['metrics'][key]=invalid
                self.assertEqual(select_trial([a,b])['status'],'needs_review')
        a=trial('a',.03)
        del a['metrics']['NPD_atoms']
        self.assertEqual(select_trial([a])['status'],'needs_review')

    def test_partial_dimensions_and_radiation_survive_intake(self):
        p=self.root/'specimen.json'
        fields={'_exptl_crystal_size_min':0.05,'_exptl_crystal_size_max':0.08,'_diffrn_radiation_type':'Mo Kalpha'}
        write_json(p,{'provenance':'experiment log','confirmed':True,'cif_fields':fields})
        data,missing=validate_specimen(p)
        self.assertEqual(data['cif_fields'],fields)
        self.assertIn('three_dimensions',missing)
        fields['_exptl_crystal_size_min']=.15
        write_json(p,{'provenance':'experiment log','cif_fields':fields})
        with self.assertRaises(ValueError):validate_specimen(p)

    def test_hkl4_preflight_distinguishes_negative_intensity(self):
        p=self.root/'data.hkl'
        for content,issue in [(record(1,2,3,-12.,2.),None),(record(1,2,3,12.,0.),'nonpositive_sigma'),
                              (record(1,2,3,12.,1.,-2),'negative_component_index_requires_review'),
                              (record(1,2,3,12.,1.).rstrip()+' 2\n','additional_reflection_columns')]:
            p.write_text(content+'   0   0   0\n','ascii')
            found=reflection_stats(p)['routine_hkl4_issue']
            self.assertEqual(found['reason'] if found else None,issue)

    def test_notes_follow_actual_solver_or_unknown(self):
        for program in ('SHELXD','SHELXT',None):
            write_json(self.root/'session.json',{'solution_program':program})
            notes=cp.solution_notes(self.root)
            if program:
                self.assertTrue(all(program in s for s in notes))
            else:self.assertFalse(any('SHELX' in s for s in notes))

    def test_pairing_and_intake_agree_on_blank_hkl_terminator(self):
        p=self.root/'data.hkl'
        row=record(1,2,3,40.,2.)
        for footer in ('CELL footer\n','   0   0   0\n'):
            text=row+'\n'+footer
            p.write_text(text,'ascii')
            self.assertIsNone(reflection_stats(p)['routine_hkl4_issue'])
            self.assertEqual(read_hkl(text),read_hkl(row))
        text=row+'\n'+row
        p.write_text(text,'ascii')
        self.assertEqual(reflection_stats(p)['routine_hkl4_issue']['reason'],'reflection_after_blank_terminator')
        with self.assertRaisesRegex(ValueError,'blank HKL terminator'):
            read_hkl(text)

    def test_manual_signoff_refuses_integrity_findings(self):
        dr=self.root/'delivery_run';dr.mkdir()
        write_json(dr/'automatic_qa.json',{'status':'needs_review','documents':{'zh':{},'en':{}},'findings':['Official alert counts differ']})
        with patch.object(cp,'checked'),self.assertRaisesRegex(ValueError,'integrity'):
            cp.finalize(self.root,{'status':'needs_report_review','finish_root':str(self.root)},SimpleNamespace())

    def test_review_checkpoint_requires_all_three_confirmations(self):
        args=SimpleNamespace(reviewed_zh=True,reviewed_en=True,reviewed_official=False,review_note='Checked')
        with self.assertRaisesRegex(ValueError,'actual review'):ar.review_reports(self.root,{},args)

    def test_review_dispatch_cannot_repeat_solution_or_upload(self):
        args=SimpleNamespace(reviewed_zh=True,reviewed_en=True,reviewed_official=True,review_note='Examined pages and interpreted remaining alerts')
        write_json(self.root/'profile.json',{'python':'python'})
        state={'category':'report_review','options':{'profile':str(self.root/'profile.json')},'actions':[],'completed_actions':['solve','match','finish']}
        (self.root/'logs').mkdir();p=self.root/'pipeline';p.mkdir()
        write_json(p/'pipeline.json',{'status':'needs_report_review'})
        commands=[]
        def runner(command,log):
            commands.append(command)
            write_json(p/'pipeline.json',{'status':'complete'})
            return 0
        with patch.object(ar,'verify'),patch.object(ar,'drive',return_value=state):
            ar.review_reports(self.root,state,args,runner)
        self.assertEqual(len(commands),1)
        self.assertEqual(commands[0][3],'finalize')
        self.assertNotIn('--authorize-iucr-upload',commands[0])
