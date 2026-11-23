import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import gemmi
import structure_viewer as v


def fixture(root, atoms, ops=('x,y,z',), cell=(10,10,10,90,90,90)):
    # atoms: label, element, fractional xyz, part, CIF occupancy
    fields=['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']
    cif='data_test\n'+''.join('_cell_'+k+' '+str(x)+'\n' for k,x in zip(fields,cell))
    cif+="loop_\n_space_group_symop_operation_xyz\n"+'\n'.join("'"+s+"'" for s in ops)+'\n'
    cif+='loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_occupancy\n'
    for label,el,pos,part,occ in atoms:cif+=' '.join([label,el,*map(str,pos),str(occ)])+'\n'
    c=root/'model.cif';c.write_text(cif,encoding='utf-8')
    elements=list(dict.fromkeys(a[1] for a in atoms))
    res='TITL synthetic\nCELL .71073 '+' '.join(map(str,cell))+'\nLATT -1\nSFAC '+' '.join(elements)+'\nUNIT '+' '.join('1' for _ in elements)+'\nFVAR 1 .6\n'
    for label,el,pos,part,occ in atoms:
        res+='PART '+str(part)+'\n'+label+' '+str(elements.index(el)+1)+' '+' '.join(map(str,pos))+' '+('11' if occ==1 else '21')+' .03\n'
    res+='HKLF 4\nEND\n';r=root/'model.res';r.write_text(res,encoding='ascii')
    return c,r


class ViewerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def data(self,atoms,**kwargs):
        c,r=fixture(self.root,atoms,**kwargs);result=v.build(c,r,self.root/'view')
        return json.loads(Path(result['data']).read_text('utf-8')),result
    def test_periodic_molecule_assembled_without_input_mutation(self):
        atoms=[('C1','C',[.95,.2,.3],0,1),('C2','C',[.09,.2,.3],0,1)]
        c,r=fixture(self.root,atoms);before=[v.digest(c),v.digest(r)]
        result=v.build(c,r,self.root/'view');d=json.loads(Path(result['data']).read_text('utf-8'))
        self.assertAlmostEqual(v.distance(d['atoms'][0]['xyz'],d['atoms'][1]['xyz']),1.4)
        self.assertEqual(d['assembly']['components'],1);self.assertEqual(len(d['bonds']),1)
        self.assertEqual(before,[v.digest(c),v.digest(r)])
    def test_mutually_exclusive_parts_have_no_cross_bond(self):
        d,_=self.data([('C1','C',[.2,.2,.2],0,1),('C2A','C',[.34,.2,.2],1,.6),('C2B','C',[.34,.25,.2],2,.4)])
        for bond in d['bonds']:
            a,b=[d['atoms'][bond[k]] for k in ('i','j')]
            self.assertFalse(a['part'] and b['part'] and a['part']!=b['part'])
        self.assertEqual({a['part'] for a in d['atoms']},{0,1,2})
    def test_occupancy_comes_from_cif_not_encoded_sof(self):
        d,_=self.data([('C1','C',[.2,.2,.2],1,.6)])
        self.assertEqual(d['atoms'][0]['occupancy'],.6)
        self.assertEqual(d['groups'][0]['occupancy_range'],[.6,.6])
    def test_symmetry_completes_dimer(self):
        d,_=self.data([('C1','C',[.07,0,0],0,1)],ops=('x,y,z','-x,-y,-z'))
        self.assertEqual(len(d['atoms']),2);self.assertEqual(len(d['bonds']),1)
        self.assertAlmostEqual(d['bonds'][0]['length'],1.4)
    def test_special_position_not_duplicated(self):
        d,_=self.data([('C1','C',[0,0,0],0,1)],ops=('x,y,z','-x,-y,-z'))
        self.assertEqual(len(d['atoms']),1)
    def test_negative_part_does_not_generate_symmetry_bonds(self):
        d,_=self.data([('C1','C',[.07,0,0],-1,.5)],ops=('x,y,z','-x,-y,-z'))
        self.assertEqual(len(d['atoms']),1);self.assertFalse(d['bonds'])
    def test_periodic_network_is_explicitly_finite(self):
        d,_=self.data([('C1','C',[0,0,0],0,1),('C2','C',[.5,0,0],0,1)],cell=(3,10,10,90,90,90))
        self.assertEqual(d['assembly']['mode'],'finite_periodic_fragment');self.assertGreater(d['assembly']['cut_edges'],0)
    def test_nonorthogonal_cell_uses_cartesian_metric(self):
        d,_=self.data([('C1','C',[0,0,0],0,1),('C2','C',[0,.14,0],0,1)],cell=(10,10,10,90,90,60))
        self.assertAlmostEqual(d['bonds'][0]['length'],1.4)
    def test_coordinate_mismatch_rejected(self):
        c,r=fixture(self.root,[('C1','C',[.2,.2,.2],0,1)])
        r.write_text(r.read_text().replace('0.2 0.2 0.2','0.3 0.2 0.2'))
        with self.assertRaises(ValueError):v.build(c,r,self.root/'view')
    def test_missing_res_has_explicit_unknown_group(self):
        c,_=fixture(self.root,[('C1','C',[.2,.2,.2],0,1)])
        result=v.build(c,None,self.root/'view');d=json.loads(Path(result['data']).read_text('utf-8'))
        self.assertEqual(d['groups'][0]['key'],'unassigned');self.assertTrue(d['warnings'])
    def test_independent_cif_disorders_can_connect(self):
        a=dict(part=None,group='1',assembly='A');b=dict(part=None,group='2',assembly='B')
        self.assertTrue(v.compatible(a,b));b['assembly']='A';self.assertFalse(v.compatible(a,b))
    def test_existing_viewer_not_overwritten(self):
        c,r=fixture(self.root,[('C1','C',[.2,.2,.2],0,1)])
        first=v.build(c,r,self.root/'view');before=v.digest(first['path'])
        with self.assertRaises(FileExistsError):v.build(c,r,self.root/'view')
        self.assertEqual(before,v.digest(first['path']))
    def test_script_injection_escaped(self):
        c,r=fixture(self.root,[('C1','C',[.2,.2,.2],0,1)])
        result=v.build(c,r,self.root/'view',title='</script><script>alert(1)</script>')
        s=Path(result['path']).read_text('utf-8')
        self.assertNotIn('</script><script>alert(1)</script>',s)
        self.assertIn('\\u003c/script',s)
    def test_no_browser_for_disabled_or_failed_view(self):
        with patch.object(v.webbrowser,'open') as opened:
            self.assertEqual(v.open_generated({'status':'failed'})['status'],'not_available')
            self.assertEqual(v.open_generated({'status':'generated','path':'x'},False)['status'],'disabled')
        opened.assert_not_called()
    def test_open_checks_exact_html_hash(self):
        _,result=self.data([('C1','C',[.2,.2,.2],0,1)])
        with patch.dict(os.environ,{'CAIRYSTAL_NO_OPEN':''}),patch.object(v.webbrowser,'open',return_value=True) as opened:
            self.assertEqual(v.open_generated(result)['status'],'open_requested')
            self.assertTrue(opened.call_args.args[0].startswith('file:'))
            Path(result['path']).write_text('changed')
            self.assertEqual(v.open_generated(result)['status'],'failed')
            self.assertEqual(opened.call_count,1)
    def test_delivery_view_failure_explicit(self):
        result=v.prepare_delivery(self.root/'missing.cif',None,self.root/'out')
        self.assertEqual(result['status'],'failed');self.assertFalse(result['source_modified'])


if __name__=='__main__':unittest.main()
