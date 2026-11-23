import json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import gemmi
from water_h_trial import edit,rigid_rotation
from reflection_omit_trial import edit as omit_edit,validate_list
from adp_directions import axis_evidence
from structure_diagnostics import res_records
from crystal_runtime import records,sha,REFLECTION_TAGS
from reflection_audit import audit as reflection_audit
from candidate_trials import build,controls,IMMUTABLE
from repair_plan import compile_trials
from ab_auto import generate_requests,load_policy


def water_fixture(d):
    text='TITL synthetic water\nCELL .71073 10 10 10 90 90 90\nLATT -1\nSFAC O H C\nUNIT 3 2 1\nFVAR 1\nWGHT .04 0\n'
    text+='DFIX .84 .02 O1 H1 O1 H2\nDANG 1.35 .04 H1 H2\n'
    text+='O1 1 .3 .3 .3 11 .04\nH1 2 .384 .3 .3 11 -1.5\nH2 2 .278 .381 .3 11 -1.5\nO2 1 .3 .58 .3 11 .04\nO3 1 .58 .3 .3 11 .04\nC1 3 .8 .8 .8 11 .04\nHKLF 4\nEND\n'
    (d/'case.res').write_text(text,'ascii')
    doc=gemmi.cif.Document();b=doc.add_new_block('test')
    for name,value in zip(['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma'],[10,10,10,90,90,90]):b.set_pair('_cell_'+name,str(value))
    b.init_loop('_space_group_symop_',['operation_xyz']).add_row([gemmi.cif.quote('x,y,z')])
    loop=b.init_loop('_atom_site_',['label','type_symbol','fract_x','fract_y','fract_z','U_iso_or_equiv','occupancy'])
    for a in res_records(d/'case.res')['atoms']:loop.add_row([a['label'],a['element'],*map(str,a['xyz']),'.04','1'])
    doc.write_file(str(d/'case.cif'))
    return text


def config():
    return dict(parent='O1',hydrogens=['H1','H2'],mode='orient',basis='Synthetic identified water and acceptor chemistry',
                acceptors=[dict(atom='O2',symmetry='x,y,z',translation=[0,0,0]),dict(atom='O3',symmetry='x,y,z',translation=[0,0,0])])


class WaterToolTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.d=Path(self.t.name);self.text=water_fixture(self.d)
    def replace(self,a,b):
        (self.d/'case.res').write_text(self.text.replace(a,b),'ascii')
    def test_rigid_proper_rotation_and_internal_geometry(self):
        a=np.array([[.84,0,0],[-.22,.81,0]]);b=np.array([[0,2.8,0],[2.8,0,0]])
        r=rigid_rotation(a,b);m=(r@a.T).T
        self.assertAlmostEqual(np.linalg.det(r),1);self.assertTrue(np.allclose(r.T@r,np.eye(3)))
        self.assertTrue(np.allclose(m@m.T,a@a.T))
    def test_collinear_target_rejected(self):
        with self.assertRaises(ValueError):rigid_rotation([[1,0,0],[0,1,0]],[[1,0,0],[-1,0,0]])
    def test_edit_preserves_atom_count_sof_U_and_parent(self):
        text,changes=edit(self.d,config());(self.d/'new.res').write_text(text,'ascii')
        old=res_records(self.d/'case.res')['atoms'];new=res_records(self.d/'new.res')['atoms']
        self.assertEqual(len(old),len(new));self.assertEqual(old[0]['row'],new[0]['row'])
        for a,b in zip(old,new):self.assertEqual(a['row'][:2]+a['row'][5:],b['row'][:2]+b['row'][5:])
        self.assertEqual([a['afix'] for a in new[:3]],[0,3,3]);self.assertEqual((self.d/'case.res').read_text('ascii'),self.text)
        self.assertEqual(len(changes[0]['water_orientation']['removed_redundant_internal_distance_restraints']),2)
    def test_freeze_does_not_move_H(self):
        c=config();c.update(mode='freeze',acceptors=[]);text,_=edit(self.d,c)
        (self.d/'new.res').write_text(text,'ascii')
        for a,b in zip(res_records(self.d/'case.res')['atoms'],res_records(self.d/'new.res')['atoms']):self.assertTrue(np.allclose(a['xyz'],b['xyz']))
    def test_chemical_basis_required(self):
        c=config();c['basis']=''
        with self.assertRaises(ValueError):edit(self.d,c)
    def test_duplicate_H_rejected(self):
        c=config();c['hydrogens']=['H1','H1']
        with self.assertRaises(ValueError):edit(self.d,c)
    def test_partial_occupancy_rejected(self):
        self.replace('O1 1 .3 .3 .3 11','O1 1 .3 .3 .3 10.5')
        with self.assertRaises(ValueError):edit(self.d,config())
    def test_disorder_part_rejected(self):
        self.replace('O1 1','PART 1\nO1 1')
        with self.assertRaises(ValueError):edit(self.d,config())
    def test_intervening_atom_rejected(self):
        self.replace('H1 2','C2 3 .7 .7 .7 11 .04\nH1 2')
        with self.assertRaises(ValueError):edit(self.d,config())
    def test_external_H_restraint_not_silently_removed(self):
        self.replace('HKLF 4','DFIX 1.8 .02 H1 O2\nHKLF 4')
        with self.assertRaises(ValueError):edit(self.d,config())
    def test_unsupported_H_constraints_rejected(self):
        self.replace('HKLF 4','EADP H1 H2\nHKLF 4')
        with self.assertRaises(ValueError):edit(self.d,config())
    def test_existing_AFIX3_reused(self):
        self.replace('H1 2','AFIX 3\nH1 2')
        text=(self.d/'case.res').read_text('ascii').replace('O2 1','AFIX 0\nO2 1');(self.d/'case.res').write_text(text,'ascii')
        result,_=edit(self.d,config());self.assertEqual(result.count('AFIX 3'),1)
    def test_wrong_symmetry_and_translation_rejected(self):
        for key,value in [('symmetry','x+1/2,y,z'),('translation',[True,0,0])]:
            c=config();c['acceptors'][0][key]=value
            with self.assertRaises(ValueError):edit(self.d,c)
    def test_no_new_atoms_and_immutable_controls_in_builder(self):
        req=dict(recipe='water_orient',parameters={k:v for k,v in config().items() if k!='mode'},reason='test',evidence=['test'])
        ps=compile_trials(self.d,req);self.assertEqual(len(ps),4)
        for p in ps:
            text,_=build(self.d,p,self.d)
            self.assertEqual(controls(self.text,IMMUTABLE),controls(text,IMMUTABLE))
    def test_mixed_reflection_and_water_edits_rejected(self):
        p=dict(name='bad',kind='diagnostic_refinement',reason='x',evidence=['x'],water_orientation=config(),reflection_omit={'hkls':[[1,2,3]],'basis':'x'})
        with self.assertRaises(ValueError):build(self.d,p,self.d)
    def test_special_position_rejected(self):
        self.replace('O1 1 .3 .3 .3','O1 1 .3 .3 .25')
        doc=gemmi.cif.read_file(str(self.d/'case.cif'));b=doc.sole_block();loop=b.find_values('_space_group_symop_operation_xyz').get_loop();loop.add_row([gemmi.cif.quote('x,y,-z+1/2')])
        for row in b.find(['_atom_site_label','_atom_site_fract_z']):
            if row[0]=='O1':row[1]='.25'
        doc.write_file(str(self.d/'case.cif'))
        with self.assertRaises(ValueError):edit(self.d,config())


class OmitToolTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.d=Path(self.t.name);self.text=water_fixture(self.d)
    def evidence(self):return {'weighted_outliers':[{'hkl':[8,1,3],'status':'o','delta_over_sigmaW':-11}]}
    def test_fixed_list_inserts_only_OMIT(self):
        with patch('reflection_omit_trial.audit',return_value=self.evidence()):text,edits=omit_edit(self.d,{'hkls':[[8,1,3]],'basis':'sensitivity'})
        self.assertIn('OMIT 8 1 3',text);self.assertEqual(controls(text,IMMUTABLE-{'OMIT'}),controls(self.text,IMMUTABLE-{'OMIT'}))
        self.assertFalse(edits[0]['reflection_omit']['raw_HKL_modified']);self.assertEqual((self.d/'case.res').read_text(),self.text)
    def test_ordinary_sigma_only_not_eligible(self):
        with patch('reflection_omit_trial.audit',return_value={'weighted_outliers':[]}):
            with self.assertRaises(ValueError):omit_edit(self.d,{'hkls':[[8,1,3]],'basis':'x'})
    def test_excluded_x_not_eligible(self):
        e=self.evidence();e['weighted_outliers'][0]['status']='x'
        with patch('reflection_omit_trial.audit',return_value=e):
            with self.assertRaises(ValueError):omit_edit(self.d,{'hkls':[[8,1,3]],'basis':'x'})
    def test_unknown_weights_not_zero(self):
        with patch('reflection_omit_trial.audit',return_value={'weighted_outliers':None}):
            with self.assertRaises(ValueError):omit_edit(self.d,{'hkls':[[8,1,3]],'basis':'x'})
    def test_bounds_and_no_duplicates(self):
        for v in [[],[[1,2,3]]*2,[[True,2,3]],[[0,0,0]],[[1,2.5,3]],[[i,0,1] for i in range(21)]]:
            with self.assertRaises(ValueError):validate_list(v)
    def test_twin_correction_not_supported(self):
        (self.d/'case.res').write_text(self.text.replace('HKLF','TWIN -1 0 0 0 -1 0 0 0 -1\nHKLF'))
        with patch('reflection_omit_trial.audit',return_value=self.evidence()):
            with self.assertRaises(ValueError):omit_edit(self.d,{'hkls':[[8,1,3]],'basis':'x'})
    def test_existing_omit_not_repeated(self):
        (self.d/'case.res').write_text(self.text.replace('HKLF','OMIT 8 1 3\nHKLF'))
        with patch('reflection_omit_trial.audit',return_value=self.evidence()):
            with self.assertRaises(ValueError):omit_edit(self.d,{'hkls':[[8,1,3]],'basis':'x'})
    def test_active_reflection_audit_excludes_x(self):
        doc=gemmi.cif.read_file(str(self.d/'case.cif'));b=doc.sole_block()
        b.set_pair('_refine_ls_weighting_details',gemmi.cif.quote('w=1/[sigma^2(Fo^2)+(0P)^2+0P] where P=(Fo^2+2Fc^2)/3'))
        b.set_pair('_diffrn_radiation_wavelength','.71073');doc.write_file(str(self.d/'case.cif'))
        fdoc=gemmi.cif.Document();fb=fdoc.add_new_block('f')
        for k in ['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']:fb.set_pair('_cell_'+k,b.find_value('_cell_'+k))
        fb.set_pair('_shelx_F_squared_multiplier','1');loop=fb.init_loop('',REFLECTION_TAGS)
        loop.add_row(['1','0','0','100','200','1','x']);loop.add_row(['2','0','0','100','102','1','o']);fdoc.write_file(str(self.d/'case.fcf'))
        files={e:str(self.d/('case.'+e)) for e in ['cif','fcf','res']};bundle={'files':files,'source_sha256':{e:sha(p) for e,p in files.items()}}
        with patch('reflection_audit.paired_bundle',return_value=bundle):r=reflection_audit(self.d)
        self.assertEqual(r['weighted_gt10_count'],0);self.assertEqual(r['excluded_status_x_rows'],1);self.assertEqual(r['active_FCF_rows'],1)


class AdpAxisTests(unittest.TestCase):
    def test_unique_long_axis(self):
        r=axis_evidence(np.diag([.01,.02,.16]));self.assertEqual(r['status'],'axis_resolved')
        self.assertAlmostEqual(r['rms_ratio'],4);self.assertAlmostEqual(abs(r['major_axis_cartesian'][2]),1)
    def test_rotated_cartesian_tensor(self):
        a=.7;q=np.array([[math.cos(a),0,math.sin(a)],[0,1,0],[-math.sin(a),0,math.cos(a)]])
        r=axis_evidence(q@np.diag([.01,.02,.16])@q.T)
        self.assertAlmostEqual(abs(np.dot(r['major_axis_cartesian'],q[:,2])),1)
    def test_degenerate_major_axis_has_no_direction(self):
        r=axis_evidence(np.diag([.01,.16,.16]));self.assertIsNone(r['major_axis_cartesian'])
    def test_NPD_not_split_direction(self):
        r=axis_evidence(np.diag([-.01,.02,.16]));self.assertEqual(r['status'],'NPD');self.assertIsNone(r['rms_ratio'])
    def test_asymmetric_tensor_rejected(self):
        with self.assertRaises(ValueError):axis_evidence([[1,1,0],[0,1,0],[0,0,1]])

class AutomaticOmitTests(unittest.TestCase):
    def test_missing_optional_numpy_does_not_break_donor_tool(self):
        import importlib
        from ab_evidence_tools import collect
        original=importlib.import_module
        def importing(name):
            if name=='adp_directions':raise ModuleNotFoundError('numpy unavailable')
            return original(name)
        with tempfile.TemporaryDirectory() as t,patch('donor_audit.audit',return_value={'status':'evidence_ready','seconds':.01}),patch('ab_evidence_tools.importlib.import_module',side_effect=importing):
            r=collect(t,[{'code':'306'},{'code':'214'}],Path(t)/'evidence')
            results={x['tool']:x for x in r}
            self.assertEqual(results['donor-audit']['status'],'evidence_ready')
            self.assertEqual(results['adp-directions']['status'],'failed')
            self.assertEqual(results['adp-directions']['exception_type'],'ModuleNotFoundError')
            self.assertIn('parameter-correlations',results)
    def route(self,code,rows):
        packet={'all_atoms':[],'regions':[],'AB_alerts':[{'code':code,'level':'B','text':'synthetic','atom_labels':[]}],
                'reflection_evidence':{'weighted_outliers':rows}}
        return generate_requests(packet,{'atoms':[],'sfac':[]},load_policy())
    def test_weighted_evidence_prepares_fixed_list(self):
        req,_=self.route('934',[{'hkl':[8,1,3],'status':'o','delta_over_sigmaW':-11,'theta_degrees':12}])
        self.assertEqual(req[0]['recipe'],'reflection_omit');self.assertEqual(req[0]['parameters']['hkls'],[[8,1,3]])
    def test_missing_weighted_evidence_does_not_prepare(self):
        req,_=self.route('934',None);self.assertFalse(req)
    def test_over_budget_does_not_truncate_to_twenty(self):
        req,_=self.route('934',[{'hkl':[i,1,3],'status':'o'} for i in range(21)]);self.assertFalse(req)
    def test_beamstop_route_requires_low_angle_negative(self):
        req,_=self.route('919',[{'hkl':[1,0,0],'status':'o','delta_over_sigmaW':11,'theta_degrees':2}]);self.assertFalse(req)

if __name__=='__main__':unittest.main()
