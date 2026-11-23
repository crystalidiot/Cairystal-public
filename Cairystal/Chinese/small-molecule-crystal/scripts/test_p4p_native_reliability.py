import json
import tempfile
import unittest
from pathlib import Path
import gemmi
import contextlib
import io
from types import SimpleNamespace
from p4p_metadata import read_p4p, input_conflicts
from crystal_session import parse_p4p, laue_seed, logical_text
from pipeline_intake import inspect
from experiment_metadata_state import p4p_fields, collect, synchronize
from shelx_input_preflight import validate_native_input
from crystal_runtime import sha, records
from iucr_validation import parse_official_text

P4P='FILEID Rigaku RapidAuto3.1 synthetic\nCELL 8.85 8.85 8.2 90 90 120\nCELLSD .001 .001 .001 0 0 0\nSOURCE Mo .71073\nBRAVAIS hexagonal\nSYMM 6/mmm 6/mmm\nCSIZE .1 .1 .1 ? 296.15\nCHEM C9 H13 O5 N3\n'
INS='TITL synthetic\nCELL .71073 10 10 10 90 90 90\nLATT -1\nSFAC C H\nUNIT 2 0\nWGHT .1\nLIST 4\nFVAR 1\nC1 1 .2 .3 .4 11 .04\nHKLF 4\nEND\n'
HKL=f'{1:4d}{0:4d}{1:4d}{100.:8.2f}{5.:8.2f}{1:4d}\n'+f'{0:4d}{0:4d}{0:4d}{0.:8.2f}{0.:8.2f}{0:4d}\n'

class P4PDialect(unittest.TestCase):
    def test_missing_subset_is_unknown(self):
        m=read_p4p(P4P);self.assertIsNone(m['measurement_reflections']);self.assertIsNone(m['measurement_theta_min'])
    def test_rigaku_unit_not_inferred_from_magnitude(self):
        for raw in ['296.15','23','0']:
            m=read_p4p(P4P.replace('296.15',raw));self.assertNotIn('temperature_K',m);self.assertEqual(m['temperature_evidence']['raw'],raw)
    def test_unknown_vendor_unit_unconfirmed(self):
        self.assertNotIn('temperature_K',read_p4p(P4P.replace('Rigaku RapidAuto3.1','OTHER')))
    def test_saint_explicit_dialect_conversion(self):
        m=read_p4p(P4P.replace('Rigaku RapidAuto3.1','SAINT').replace('296.15','-173.15'));self.assertEqual(m['temperature_K'],100)
    def test_known_zero_celsius_preserved(self):
        self.assertEqual(read_p4p(P4P.replace('Rigaku RapidAuto3.1','SAINT').replace('296.15','0'))['temperature_K'],273.15)
    def test_explicit_unit_needs_evidence(self):
        with self.assertRaises(ValueError):read_p4p(P4P,temperature_unit='K')
        self.assertEqual(read_p4p(P4P,temperature_unit='K',temperature_basis='Synthetic documented format convention')['temperature_K'],296.15)
    def test_bad_unit_overrides_rejected(self):
        for unit in ['F','kelvin',True]:
            with self.assertRaises(ValueError):read_p4p(P4P,temperature_unit=unit,temperature_basis='test')
    def test_invalid_cell(self):
        for cell in ['0 10 10 90 90 90','10 10 10 90 0 90','nan 10 10 90 90 90']:
            with self.assertRaises(ValueError):read_p4p(P4P.replace('8.85 8.85 8.2 90 90 120',cell))
    def test_repeated_conflicting_source(self):
        with self.assertRaises(ValueError):read_p4p(P4P+'SOURCE Mo .154\n')
    def test_duplicate_saint_subset_same_is_allowed(self):
        m=read_p4p(P4P+'SAINGL 1000 2 25 a\nSAINGL 1000 2 25 b\n');self.assertEqual(m['measurement_reflections'],1000)
    def test_invalid_subset(self):
        for s in ['1.5 2 25','100 26 25','100 2 95','100 nan 25']:
            with self.assertRaises(ValueError):read_p4p(P4P+'SAINGL '+s+'\n')
    def test_scan_limits_not_cell_subset(self):
        m=read_p4p(P4P+'LIMITS 0 90 0 90\nADPAR 1 2 3 4600\n');self.assertIsNone(m['measurement_reflections']);self.assertIsNone(m['measurement_theta_max'])
    def test_template_conflicts_recorded(self):
        spec={'cif_fields':dict(zip(['_exptl_crystal_size_'+s for s in ['max','mid','min']],[.07,.065,.06]))}
        c=input_conflicts(read_p4p(P4P),['Pb','I','C','H','N'],spec);self.assertEqual({r['field'] for r in c},{'CHEM','CSIZE dimensions'})
    def test_both_parser_entrypoints_agree(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.p4p';p.write_text(P4P);fields,_,_=p4p_fields(p,'both')
            self.assertNotIn('_diffrn_ambient_temperature',fields);self.assertNotIn('_cell_measurement_reflns_used',fields)
    def test_intake_accepts_real_format_without_subset(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'x.p4p').write_text(P4P);(p/'x.hkl').write_text(HKL)
            r=inspect(p,['Pb','I','C','H','N']);self.assertIsNone(r['metadata']['measurement_reflections']);self.assertEqual(len(r['laue_seed'][1]),11)

class LaueChecks(unittest.TestCase):
    def test_complete_hexagonal_operations(self):
        latt,sym,_=laue_seed(read_p4p(P4P));self.assertEqual(latt,1)
        ops=[gemmi.Op('x,y,z')]+[gemmi.Op(s) for s in sym]
        inv=gemmi.Op('-x,-y,-z');actual={o.triplet() for o in ops}|{inv.combine(o).triplet() for o in ops}
        self.assertEqual(actual,{o.triplet() for o in gemmi.SpaceGroup('P 6/m m m').operations()})
    def test_hexagonal_metric_cannot_select_laue(self):
        with self.assertRaises(ValueError):laue_seed(read_p4p(P4P.replace('SYMM 6/mmm 6/mmm\n','')))
    def test_mismatched_hexagonal_cell_rejected(self):
        with self.assertRaises(ValueError):laue_seed(read_p4p(P4P.replace('8.85 8.85','8.85 9.85')))
    def test_lower_hexagonal_laue_not_promoted(self):
        self.assertEqual(len(laue_seed(read_p4p(P4P.replace('6/mmm','6/m')))[1]),5)

class SyntaxChecks(unittest.TestCase):
    def test_good_native_input(self):self.assertEqual(validate_native_input(INS)['checked_atom_records'],1)
    def test_long_rem_is_separate_comments(self):
        result=logical_text(['REM '+'word '*80]);self.assertTrue(all(s.startswith('REM ') and len(s)<80 and not s.endswith('=') for s in result.splitlines()))
    def test_long_atom_preserves_numbers(self):
        row='C1 1 '+'0.12345678 '*10
        text=logical_text([row]);self.assertEqual(text.replace('=\n',' ').split(),row.split())
    def test_oversized_physical_input_blocked(self):
        with self.assertRaisesRegex(ValueError,'80 columns'):validate_native_input(INS.replace('TITL synthetic','TITL '+'x'*100))
    def test_duplicate_active_weight_blocked(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):validate_native_input(INS.replace('LIST 4','WGHT .2\nLIST 4'))
    def test_post_end_suggested_weight_allowed(self):validate_native_input(INS+'WGHT .5\n')
    def test_bad_atom_sfac_index_blocked(self):
        with self.assertRaisesRegex(ValueError,'index out of range'):validate_native_input(INS.replace('C1 1','C1 3'))
    def test_unit_sfac_count_mismatch(self):
        with self.assertRaisesRegex(ValueError,'UNIT count'):validate_native_input(INS.replace('UNIT 2 0','UNIT 2'))
    def test_non_plat_alerts_stay_visible(self):
        r=parse_official_text('Structure factors have been supplied\nNo syntax errors\nDIFF003_ALERT_1_A Instrument missing\nPLAT183_ALERT_1_A Count missing\n2 ALERT level A =\n0 ALERT level B =\n0 ALERT level C =\n0 ALERT level G =\n')
        self.assertEqual(r['counts']['A'],2)
    def test_rejected_input_leaves_attempt_log_without_execution(self):
        from run_crystal_stage import run
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);exe=p/'shelxl.exe';exe.write_bytes(b'Never execute this synthetic file')
            ins=p/'x.ins';ins.write_text(INS.replace('LIST 4','LIST 4\nWGHT .3'))
            hkl=p/'x.hkl';hkl.write_text(HKL)
            a=SimpleNamespace(executable=str(exe),ins=str(ins),hkl=str(hkl),stem='model',fab=None,output=str(p/'out'),reason='Synthetic rejection test',timeout=1)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(run(a),1)
            record=json.loads((p/'out/attempt.json').read_text())
            self.assertIn('Duplicate',record['error']);self.assertNotIn('command',record)

class DerivedTemperature(unittest.TestCase):
    def test_temperature_uncertainty_comes_from_source(self):
        from test_metadata_state_and_comparison import Metadata
        for source_token in ['100','100(5)']:
            with self.subTest(source=source_token),tempfile.TemporaryDirectory() as t:
                p=Path(t);args=Metadata().setup_case(p,'_diffrn_ambient_temperature '+source_token+'\n')
                doc=gemmi.cif.read_file(str(args[1]));doc.sole_block().set_pair('_diffrn_ambient_temperature','100(2)');doc.write_file(str(args[1]))
                r=synchronize(*args,p/'derived')
                self.assertEqual(gemmi.cif.read_file(r['output']).sole_block().find_value('_diffrn_ambient_temperature'),source_token)
    def test_native_default_removed_without_measured_source(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);h=p/'model.hkl';h.write_text(HKL)
            raw=p/'model.p4p';raw.write_text(P4P.replace('8.85 8.85 8.2 90 90 120','10 10 10 90 90 90'))
            res=p/'model.res';res.write_text(INS)
            cif=p/'model.cif';doc=gemmi.cif.Document();b=doc.add_new_block('test')
            b.set_pair('_diffrn_ambient_temperature','293(2)')
            for k,v in zip(['a','b','c'],[10,10,10]):b.set_pair('_cell_length_'+k,str(v))
            for k in ['alpha','beta','gamma']:b.set_pair('_cell_angle_'+k,'90')
            doc.write_file(str(cif))
            cfg=p/'sources.json';cfg.write_text(json.dumps({'hkl':str(h),'sources':[{'path':str(raw),'kind':'p4p','same_experiment_confirmed':True,'basis':'Synthetic source','hkl_sha256':sha(h),'source_sha256':sha(raw)}]}))
            collect(cfg,p/'ledger');r=synchronize(p/'ledger/metadata_ledger.json',cif,res,h,p/'derived')
            self.assertEqual(gemmi.cif.read_file(r['output']).sole_block().find_value('_diffrn_ambient_temperature'),'?')
            self.assertEqual(gemmi.cif.read_file(str(cif)).sole_block().find_value('_diffrn_ambient_temperature'),'293(2)')
            self.assertEqual(r['status'],'needs_review')

if __name__=='__main__':unittest.main()
