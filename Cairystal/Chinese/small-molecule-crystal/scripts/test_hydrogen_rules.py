import copy, json, tempfile, unittest
from pathlib import Path
from hydrogen_plan import rule,generate,parse_graph,model_context
from report_method_templates import hydrogen_method_notes

def atom(e='C',h=None,q=0,**kw):return {'element':e,'hydrogens':h,'formal_charge':q,**kw}

class RuleTests(unittest.TestCase):
    def test_carbon_geometries(self):
        for orders,h,code in [([1],3,137),([1,1],2,23),([1,1,1],1,13),([1,2],1,43),([1.5,1.5],1,43),([3],1,163),([2,2],0,None)]:
            with self.subTest(orders=orders):self.assertEqual(rule(atom(),orders)[:2],(code,h))
    def test_hybridization_alone_not_sufficient(self):
        self.assertEqual([rule(atom(),[1]*n)[0] for n in (1,2,3)],[137,23,13])
    def test_bad_carbon_valence_and_charge(self):
        for a,o in [(atom(h=3),[1,1]),(atom(q=1,h=3),[1]),(atom(),[1.5]),(atom(),[2])]:
            with self.subTest(a=a,o=o),self.assertRaises(ValueError):rule(a,o)
    def test_donor_protonation_required(self):
        for a in (atom('O',1),atom('N',3,1)):
            with self.assertRaises(ValueError):rule(a,[1])
    def test_explicit_donors(self):
        self.assertEqual(rule(atom('N',3,1),[1],'charge and chemistry checked')[0],137)
        self.assertEqual(rule(atom('O',1),[1],'OH identified')[0],147)
        self.assertEqual(rule(atom('N',1,geometry='planar'),[1,1],'amide checked')[0],43)
    def test_water_amine_and_special_elements_not_guessed(self):
        for a,o in [(atom('O',2),[]),(atom('N',2),[1]),(atom('S',1),[1])]:
            with self.assertRaises(ValueError):rule(a,o,'known H count')
    def test_nh4_has_no_axis(self):
        with self.assertRaises(ValueError):rule(atom('N',4,1),[],'ammonium')
    def test_no_H_nitrogen_and_perchlorate_oxygen(self):
        self.assertEqual(rule(atom('N',0,1),[1,1,1,1])[1],0)
        self.assertEqual(rule(atom('O',0,-1),[1])[1],0)

class MappingTests(unittest.TestCase):
    def fixture(self):
        g={'atoms':[{'id':'a',**atom(h=3)},{'id':'b',**atom(h=3)}],'bonds':[['a','b',1]]}
        m=[{'label':n,'element':'C','part':0,'residue':'0','inferred_cif_occupancy':1,'general_multiplicity':1,'geometric_site_multiplicity':1} for n in ('C1','C2')]
        return g,{'a':'C1','b':'C2'},m,{'C1':{'C2'},'C2':{'C1'}}
    def test_success(self):
        r=generate(*self.fixture());self.assertEqual(r['status'],'ready_for_refinement');self.assertEqual(r['expected_H_sites_for_accepted_rules'],6)
    def test_ambiguous_mapping_rejected(self):
        g,p,m,n=self.fixture();p['b']='C1'
        with self.assertRaises(ValueError):generate(g,p,m,n)
    def test_existing_H_rejected(self):
        g,p,m,n=self.fixture();m[1]['element']='H'
        with self.assertRaises(ValueError):generate(g,p,m,n)
    def test_parts_population_special_positions_and_wrong_element_block(self):
        for k,v in [('part',1),('residue','1'),('inferred_cif_occupancy',.5),('general_multiplicity',2),('element','N')]:
            g,p,m,n=self.fixture();m[0][k]=v
            self.assertEqual(generate(g,p,m,n)['status'],'needs_review',k)
    def test_coordination_or_wrong_geometry_block(self):
        g,p,m,n=self.fixture();n['C1'].add('M1');self.assertEqual(generate(g,p,m,n)['status'],'needs_review')
    def test_graph_duplicate_bond_rejected(self):
        g,*_=self.fixture();g['bonds'].append(['b','a',1])
        with self.assertRaises(ValueError):parse_graph(g)

MODEL='''TITL synthetic
CELL .71073 10 10 10 90 90 90
LATT -1
SFAC C H
UNIT 2 0
TEMP 20
FVAR 1
C1 1 .1 .2 .3 11 .03
C2 1 .25 .2 .3 11 .03
HKLF 4
END
'''

class NativeGuardTests(unittest.TestCase):
    def context(self,text):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'m.res';p.write_text(text);return model_context(p)
    def test_geometry_from_current_model(self):
        a,n,_=self.context(MODEL);self.assertEqual(n,{'C1':{'C2'},'C2':{'C1'}})
    def test_existing_hfix_rejected(self):
        with self.assertRaises(ValueError):self.context(MODEL.replace('HKLF','HFIX 137 C1\nHKLF'))
    def test_missing_temperature_rejected(self):
        with self.assertRaises(ValueError):self.context(MODEL.replace('TEMP 20\n',''))
    def test_custom_connectivity_rejected(self):
        with self.assertRaises(ValueError):self.context(MODEL.replace('HKLF','CONN 0 C1\nHKLF'))

class TemplateTests(unittest.TestCase):
    def test_actual_controls_not_claimed_map_locations(self):
        text=MODEL.replace('HKLF','AFIX 23\nH1 2 .1 .3 .3 11 -1.2\nH2 2 .1 .1 .3 11 -1.2\nAFIX 0\nHKLF')
        r=hydrogen_method_notes(text)
        self.assertEqual(r['evidence']['AFIX_H_site_counts'],{23:2});self.assertIn('AFIX 23',r['zh']['methods']);self.assertIn('do not claim',r['en']['limitations'])
    def test_cards_not_misread_as_atoms(self):
        text=MODEL.replace('UNIT 2 0','UNIT 2 0 0 11 -1.2 0 0')
        self.assertEqual(hydrogen_method_notes(text)['evidence']['AFIX_H_site_counts'],{})
    def test_unsupported_afix_flagged(self):
        text=MODEL.replace('HKLF','AFIX 99\nH1 2 .1 .3 .3 11 -1.2\nHKLF')
        self.assertIn('AFIX 99',hydrogen_method_notes(text)['evidence']['unsupported'])

if __name__=='__main__':unittest.main()
