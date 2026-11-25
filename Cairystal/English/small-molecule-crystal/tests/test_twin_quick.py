import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import twin_quick as q
from crystal_runtime import sha,records

LISTING='''PLATON-TWINROTM
N(refl) = 4115, N(selected) = 50
2-axis ( 0 0 1 ) Freq = 50
(-1.000  0.000  0.000)   (h1)   (h2)  Nr Overlap = 4115
( 0.000 -1.000  0.000) * (k1) = (k2)  BASF = 0.30
( 0.000  0.000  1.000)   (l1)   (l2)  DEL-R =-0.205
'''
CIF='''data_case
_cell_length_a 10
_cell_length_b 11
_cell_length_c 12
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
loop_
_space_group_symop_operation_xyz
'x,y,z'
'-x,-y,-z'
'''
RES='TITL current\nCELL .71073 10 11 12 90 90 90\nLATT 1\nSFAC C\nUNIT 2\nWGHT .05\nFVAR 1\nC1 1 .1 .2 .3 11 .02\nHKLF 4\nEND\n'

class TwinTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        for e,t in [('cif',CIF),('res',RES),('hkl','data'),('fcf','factors')]:
            (self.base/f'case.{e}').write_text(t,'ascii')
        self.law=q.parse_listing(LISTING)[0]
    def evidence(self):
        lis=self.base/'native.lis';lis.write_text(LISTING,'ascii')
        p=self.base/'evidence.json';p.write_text(json.dumps({'source_hashes':{e:sha(self.base/f'case.{e}') for e in ['res','hkl','cif','fcf']},
                     'listing':str(lis),'listing_sha256':sha(lis),'search_state':'complete_candidates_early_stop'}),'utf-8')
        return {'evidence':str(p),'evidence_sha256':sha(p),'law':self.law}
    def test_complete_native_block(self):
        self.assertEqual(self.law['matrix'],[-1,0,0,0,-1,0,0,0,1]);self.assertEqual(self.law['basf_estimate'],.3)
    def test_truncated_block_not_accepted(self):
        self.assertEqual(q.parse_listing(LISTING.rsplit('( 0.000  0.000',1)[0]),[])
    def test_unlabelled_matrix_not_used(self):
        self.assertEqual(q.parse_listing(LISTING.replace('(h1)','(a1)')),[])
    def test_matrix_is_not_transposed(self):
        s=LISTING.replace('-1.000  0.000  0.000','1.000  1.000  0.000')
        self.assertEqual(q.parse_listing(s)[0]['matrix'][:4],[1,1,0,0])
    def test_duplicate_block_once(self):
        self.assertEqual(len(q.parse_listing(LISTING+LISTING)),1)
    def test_no_signal_skips_native(self):
        self.assertFalse(q.trigger(records(RES),[{'code':'183'}])['run'])
    def test_low_R_or_934_alone_not_signal(self):
        self.assertFalse(q.trigger(records(RES),[{'code':'934'}])['run'])
    def test_twin_C_notice_triggers(self):
        self.assertTrue(q.trigger(records(RES),[{'code':'930','level':'C'}])['run'])
    def test_negative_outliers_do_not_trigger(self):
        r={'weighted_outliers':[{'delta_over_sigmaW':-15,'Fo2':1,'Fc2':60}]*5}
        self.assertFalse(q.trigger(records(RES),reflection_evidence=r)['run'])
    def test_positive_excess_triggers(self):
        r={'weighted_outliers':[{'delta_over_sigmaW':15,'Fo2':60,'Fc2':1}]*3}
        self.assertTrue(q.trigger(records(RES),reflection_evidence=r)['run'])
    def test_existing_twin_not_duplicated(self):
        rows=records(RES)+[['TWIN'],['BASF','.2']]
        self.assertFalse(q.trigger(rows,[{'code':'930'}],reason='explicit')['run'])
    def test_batch_scales_not_reinterpreted(self):
        self.assertFalse(q.trigger(records(RES)+[['BASF','2']],reason='excess')['run'])
    def test_whole_overlap_required(self):
        law=dict(self.law,overlap_count=100)
        with self.assertRaisesRegex(ValueError,'Partial'):q.usable(law,self.base/'case.cif')
    def test_fractional_matrix_deferred(self):
        law=dict(self.law,matrix=[1,0,.83,0,-1,0,0,0,-1])
        with self.assertRaisesRegex(ValueError,'noninteger'):q.usable(law,self.base/'case.cif')
    def test_metric_mismatch_rejected(self):
        law=dict(self.law,matrix=[0,1,0,1,0,0,0,0,-1])
        with self.assertRaisesRegex(ValueError,'metric'):q.usable(law,self.base/'case.cif')
    def test_spacegroup_operation_rejected(self):
        law=dict(self.law,matrix=[-1,0,0,0,-1,0,0,0,-1])
        with self.assertRaisesRegex(ValueError,'space group'):q.usable(law,self.base/'case.cif')
    def test_only_two_cards_added_original_unchanged(self):
        config=self.evidence();before={e:sha(self.base/f'case.{e}') for e in ['res','hkl','cif','fcf']}
        text,edits=q.edit(self.base,config)
        rows=records(text);self.assertEqual([r for r in rows if r[0] not in {'TWIN','BASF'}],records(RES))
        self.assertEqual([r for r in rows if r[0]=='TWIN'],[['TWIN','-1','0','0','0','-1','0','0','0','1']])
        self.assertEqual(before,{e:sha(self.base/f'case.{e}') for e in before})
    def test_changed_model_rejected(self):
        config=self.evidence();(self.base/'case.res').write_text(RES+'REM changed\n')
        with self.assertRaisesRegex(ValueError,'another model'):q.edit(self.base,config)
    def test_changed_native_listing_rejected(self):
        config=self.evidence();(self.base/'native.lis').write_text(LISTING.replace('0.30','0.40'))
        with self.assertRaisesRegex(ValueError,'listing changed'):q.edit(self.base,config)
    def test_law_not_in_listing_rejected(self):
        config=self.evidence();config['law']=dict(self.law,basf_estimate=.4)
        with self.assertRaisesRegex(ValueError,'absent'):q.edit(self.base,config)
    def test_existing_mask_cannot_mix(self):
        (self.base/'case.res').write_text(RES.replace('HKLF 4','ABIN\nHKLF 4'))
        with self.assertRaisesRegex(ValueError,'mask'):q.edit(self.base,self.evidence())
    def test_HKLF5_never_relabelled(self):
        self.assertFalse(q.trigger([['HKLF','5']],reason='explicit')['run'])
    def test_timeout_evidence_cannot_edit(self):
        config=self.evidence();p=Path(config['evidence']);data=json.loads(p.read_text());data['search_state']='timeout'
        p.write_text(json.dumps(data));config['evidence_sha256']=sha(p)
        with self.assertRaisesRegex(ValueError,'timed out'):q.edit(self.base,config)
    def test_abort_overrides_a_candidate(self):
        (self.base/'case.lis').write_text(LISTING)
        (self.base/'platon.out').write_text('>>> STOP: Job ABORTED')
        fake=unittest.mock.MagicMock();fake.poll.return_value=None;fake.returncode=1
        with patch('twin_quick.subprocess.Popen',return_value=fake):
            result=q.search(self.base/'case.res',self.base,1)
        self.assertEqual(result['state'],'native_failure');self.assertFalse(result['negative_twin_diagnosis']);fake.kill.assert_called_once()

if __name__=='__main__':unittest.main()
