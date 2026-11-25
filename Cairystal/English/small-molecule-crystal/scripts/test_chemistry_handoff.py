import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import tempfile
import chemistry_handoff as ch
import crystal_pipeline as cp

def atom(label,e='C',**kw):
    return dict(label=label,element=e,part=0,residue='0',inferred_cif_occupancy=1,
                geometric_site_multiplicity=4,general_multiplicity=4,**kw)

class PreparationTests(unittest.TestCase):
    def test_short_simultaneous_rename(self):
        atoms=[atom('C1'),atom('C00F'),atom('N008','N'),atom('Cl01','Cl')]
        result=ch.short_labels(atoms)
        self.assertEqual(len(set(result.values())),4)
        self.assertEqual(result['N008'],'N1')
        self.assertTrue(all(len(x)<4 for x in result.values()))
        self.assertEqual({x['label'] for x in atoms},{'C1','C00F','N008','Cl01'})
    def test_partial_rejected(self):
        a=atom('C1');a['inferred_cif_occupancy']=.5
        with self.assertRaises(ValueError):ch.safe_atoms([a])
    def test_special_rejected(self):
        a=atom('C1');a['geometric_site_multiplicity']=2
        with self.assertRaises(ValueError):ch.safe_atoms([a])
    def test_existing_h_rejected(self):
        with self.assertRaises(ValueError):ch.safe_atoms([atom('H1','H')])
    def test_explicit_elements_only(self):
        a=[atom('C1')];v={'atoms':[dict(label='C1',neighbors=[])]}
        p,_=ch.propose_changes(a,{'C1':set()},v,['C','N'],'light')
        self.assertEqual([x['element_changes'] for x in p],[{'C1':'N'}])
    def test_oxo_is_only_proposal(self):
        aa=[atom('X','Cl')]+[atom('Q'+str(i)) for i in range(4)]
        nn={'X':{'Q'+str(i) for i in range(4)}}
        nn.update({'Q'+str(i):{'X'} for i in range(4)})
        vv={'atoms':[dict(label='X',neighbors=[['Q'+str(i),'C',1.44] for i in range(4)])]+[dict(label='Q'+str(i),neighbors=[['X','Cl',1.44]]) for i in range(4)]}
        p,_=ch.propose_changes(aa,nn,vv,['Cl','C','O'],'motifs')
        self.assertEqual(len(p),1);self.assertEqual(len(p[0]['element_changes']),4)
        self.assertNotIn('accepted',p[0])
        vv['atoms'][0]['neighbors'][0][2]=1.85
        p,_=ch.propose_changes(aa,nn,vv,['Cl','C','O'],'motifs')
        self.assertEqual(p,[])

class ContinuationTests(unittest.TestCase):
    def test_qa_success_seals(self):
        state={'status':'awaiting_visual_review','finish_root':'run/finish','events':[]}
        qa={'status':'automatic_checks_passed','documents':{'zh':{'pages':[]},'en':{'pages':[]}},'findings':[]}
        with patch('report_autoqa.run',return_value=qa),patch.object(cp,'timed',side_effect=lambda r,s,n,fn,a:fn()),patch.object(cp,'finalize') as final:
            cp.complete_report_qa(Path('run'),state,SimpleNamespace())
            final.assert_called_once()
    def test_qa_finding_stops_export(self):
        state={'status':'awaiting_visual_review','finish_root':'run/finish','events':[]}
        qa={'status':'needs_review','documents':{'zh':{'pages':[]},'en':{'pages':[]}},'findings':['Official A/B requires scientific review']}
        with patch('report_autoqa.run',return_value=qa),patch.object(cp,'timed',side_effect=lambda r,s,n,fn,a:fn()),patch.object(cp,'save'),patch.object(cp,'finalize') as final:
            cp.complete_report_qa(Path('run'),state,SimpleNamespace())
            final.assert_not_called();self.assertEqual(state['status'],'needs_report_review')
    def test_repeated_qa_does_not_export_twice(self):
        with patch('report_autoqa.run') as qa,patch.object(cp,'finalize') as final:
            cp.complete_report_qa(Path('run'),{'status':'complete'},SimpleNamespace())
            qa.assert_not_called();final.assert_not_called()
    def test_missing_plan_prevents_step(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(cp,'checked'),patch.object(cp,'timed') as native:
            root=Path(tmp);stage=root/'session/stages/source';stage.mkdir(parents=True);(stage/'model.res').write_text('dummy')
            with self.assertRaises((ValueError,FileNotFoundError)):
                cp.step(root,{'status':'needs_scientific_review'},SimpleNamespace(source='source',name='next',plan=str(root/'absent.json')))
            native.assert_not_called()

if __name__=='__main__':unittest.main()
