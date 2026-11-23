import json
from pathlib import Path
import tempfile
import unittest

import gemmi
from crystal_runtime import sha
from temperature_consistency import AMBIENT, CELL, audit_temperature, celsius_string, kelvin, prepare

RES='''TITL Synthetic temperature test, not experimental data
CELL .71073 10 10 10 90 90 90
LATT -1
SFAC C H
UNIT 1 2
ACTA
LIST 4
FVAR 1
C1 1 .1 .2 .3 11 .04
HKLF 4
END
'''


def audit(temp='100(2)',native=RES,cell='100(2)'):
    b=gemmi.cif.read_string('data_test\n'+AMBIENT+' '+temp+'\n'+CELL+' '+cell+'\n').sole_block()
    return audit_temperature(b,native)


class Audit(unittest.TestCase):
    def test_units_and_uncertainty(self):
        self.assertEqual(celsius_string('100(2)'),'-173.15')
        self.assertEqual(celsius_string('293.15'),'20.00')
        self.assertEqual(celsius_string('1.00(2)e2'),'-173.15')
    def test_unknown_and_nonphysical(self):
        for value in [None,'?','.']: self.assertIsNone(kelvin(value))
        for value in ['0','-100','nan','100 K']:
            with self.assertRaises(ValueError): kelvin(value)
    def test_missing_native_detected(self):
        self.assertIn('TEMP_MISSING',{i['code'] for i in audit()['issues']})
    def test_conflicting_units_stop(self):
        self.assertEqual(audit(native=RES.replace('FVAR','TEMP 100\nFVAR'))['status'],'failed')
    def test_matching_temperatures(self):
        self.assertEqual(audit(native=RES.replace('FVAR','TEMP -173.15\nFVAR'))['status'],'checks_passed')
    def test_distinct_cell_temperature_not_overwritten(self):
        self.assertEqual(audit(native=RES.replace('FVAR','TEMP -173.15\nFVAR'),cell='200')['status'],'checks_passed')
    def test_missing_collection_not_assumed_from_cell(self):
        self.assertEqual(audit(temp='?')['status'],'needs_review')
    def test_duplicate_and_late_native(self):
        for native in [RES.replace('FVAR','TEMP 20\nTEMP 20\nFVAR'),RES.replace('HKLF','TEMP -173.15\nHKLF')]:
            self.assertEqual(audit(native=native)['status'],'failed')
    def test_comment_and_post_end_ignored(self):
        native=RES.replace('FVAR','REM TEMP 20\n TEMP 20\nTEMP -173.15\nFVAR')+'TEMP 100\n'
        self.assertEqual(audit(native=native)['status'],'checks_passed')
    def test_optional_atom_sof_u_still_enforces_temp_order(self):
        native=RES.replace('C1 1 .1 .2 .3 11 .04','C1 1 .1 .2 .3').replace('HKLF','TEMP -173.15\nHKLF')
        self.assertIn('TEMP_AFTER_ATOMS',{i['code'] for i in audit(native=native)['issues']})


class Preparation(unittest.TestCase):
    def inputs(self,p,source=None,native=RES,extras=None):
        s=p/'source.pcf';r=p/'current.res';e=p/'evidence.json'
        s.write_text(source or AMBIENT+' 100(2)\n',encoding='utf-8');r.write_bytes(native.encode('latin1'))
        record={'source_sha256':sha(s),'res_sha256':sha(r),'same_experiment_confirmed':True,
                'collection_temperature_confirmed':True,'basis':'Synthetic paired fixture only'}
        record.update(extras or {});e.write_text(json.dumps(record),encoding='utf-8')
        return s,r,e
    def test_prepares_new_ins_without_changing_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);args=self.inputs(p);before=[sha(x) for x in args]
            r=prepare(*args,p/'new')
            self.assertEqual(before,[sha(x) for x in args]);self.assertEqual(r['status'],'prepared_not_refined')
            new=(p/'new/model.ins').read_text();self.assertLess(new.index('TEMP'),new.index('C1 1'))
            self.assertEqual(new.replace('TEMP -173.15\n',''),RES)
            with self.assertRaises(ValueError):prepare(*args,p/'new')
    def test_source_hash_mismatch_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);args=self.inputs(p,extras={'source_sha256':'wrong'})
            with self.assertRaises(ValueError):prepare(*args,p/'new')
    def test_existing_conflict_requires_reason(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);args=self.inputs(p,native=RES.replace('FVAR','TEMP 20\nFVAR'))
            with self.assertRaises(ValueError):prepare(*args,p/'new')
            r=prepare(*args,p/'new',replace_reason='Synthetic old default contradicted by paired source')
            self.assertAlmostEqual(r['previous_TEMP_K'],293.15)
    def test_cell_fallback_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);args=self.inputs(p,source=CELL+' 100\n')
            with self.assertRaises(ValueError):prepare(*args,p/'new',tag=CELL)
            args=self.inputs(p,source=CELL+' 100\n',extras={'cell_temperature_is_collection_temperature':True})
            self.assertEqual(prepare(*args,p/'new',tag=CELL)['temperature_K'],100)
    def test_unknown_source_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);args=self.inputs(p,source=AMBIENT+' ?\n')
            with self.assertRaises(ValueError):prepare(*args,p/'new')
    def test_ambiguous_source_requires_block(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);args=self.inputs(p,source='data_a\n'+AMBIENT+' 100\ndata_b\n'+AMBIENT+' 200\n')
            with self.assertRaises(ValueError):prepare(*args,p/'new')
            self.assertEqual(prepare(*args,p/'new',source_block='b')['temperature_K'],200)
    def test_native_include_is_not_followed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);args=self.inputs(p,native=RES.replace('FVAR','+not_allowed.res\nFVAR'))
            with self.assertRaises(ValueError):prepare(*args,p/'new')
    def test_missing_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);args=self.inputs(p,extras={'collection_temperature_confirmed':False})
            with self.assertRaises(ValueError):prepare(*args,p/'new')


if __name__=='__main__':unittest.main()
