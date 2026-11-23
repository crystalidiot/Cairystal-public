import itertools
import json
import hashlib
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from graph_assignment import enumerate_assignments,propose
from graph_components import small_fragment_key
from hydrogen_plan import hydrogen_scope,parse_graph,predicted_unit_h
from scientific_report_rules import basic_findings


def chlorinated_copies(n):
    graph={'atoms':[],'bonds':[]}
    model=[]
    neighbors={}
    for i in range(n):
        ca=f'c{i}'
        for p,el,h in [('c','C',2),('a','Cl',0),('b','Cl',0)]:
            key=p+str(i)
            graph['atoms'].append(dict(id=key,element=el,formal_charge=0,hydrogens=h))
            model.append(dict(label=key.upper(),element=el))
            neighbors[key.upper()]=set()
        for p in ('a','b'):
            cl=p+str(i)
            graph['bonds'].append([ca,cl,1])
            neighbors[ca.upper()].add(cl.upper())
            neighbors[cl.upper()].add(ca.upper())
    return graph,model,neighbors,{}


class FragmentRoutes(unittest.TestCase):
    def test_visible_local_alerts_must_match_the_sealed_inputs(self):
        from crystal_autorun import local_report_at_checkpoint,seal
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pipeline=root/'pipeline';finish=pipeline/'auto_finish'
            frozen=finish/'frozen';frozen.mkdir(parents=True);(finish/'local_validation').mkdir()
            (pipeline/'pipeline.json').write_text(json.dumps({'finish_root':str(finish)}))
            for ext in ('cif','fcf'):(frozen/('model.'+ext)).write_text(ext)
            path=finish/'local_validation/local_validation.json'
            data={'validation_complete':True,'input_sha256':{k:hashlib.sha256(k.encode()).hexdigest() for k in ('cif','fcf')},
                  'validated_counts':{'A':0,'B':1},'alerts':{'alerts':[dict(level='B',code='025',text='synthetic example')]}}
            def check():
                path.write_text(json.dumps(data))
                return local_report_at_checkpoint(root,{'pipeline_seal':seal(pipeline)})
            self.assertEqual(check()['counts'],{'A':0,'B':1})
            data['validated_counts']['B']=0
            self.assertIsNone(check()['counts'])
            data['validated_counts']['B']=1
            (frozen/'model.cif').write_text('changed')
            self.assertIsNone(check()['counts'])
            data['validation_complete']=False
            self.assertIsNone(check()['counts'])
    def test_permutations_preserved_under_the_normal_budget(self):
        for n in [2,3,8]:
            r=enumerate_assignments(*chlorinated_copies(n))
            self.assertEqual(r['status'],'candidates_ready')
            self.assertEqual(r['assignment_classes'],1)
            self.assertEqual(r['complete_label_mappings'],math.factorial(n)*2**n)
            self.assertEqual(r['candidates'][0]['label_permutations'],r['complete_label_mappings'])

    def test_distinct_local_assignments_survive_exchange_of_identical_fragments(self):
        # Three identical unsymmetrical C/O fragments, with genuinely distinct O positions.
        g={'atoms':[],'bonds':[]};m=[];ns={}
        for i in range(3):
            c='x'+str(i);o='y'+str(i)
            g['atoms'] += [dict(id=c,element='C',hydrogens=3,formal_charge=0),dict(id=o,element='O',hydrogens=1,formal_charge=0)]
            g['bonds'].append([c,o,1]);m.extend([dict(label=c.upper(),element='C'),dict(label=o.upper(),element='O')])
            ns[c.upper()]={o.upper()};ns[o.upper()]={c.upper()}
        def sets(result):
            return {tuple(sorted((site['element'],cand['original_mapping'][site['id']]) for site in g['atoms'])):cand['label_permutations']
                    for cand in result['candidates']}
        for n in [2,12]:
            with patch('graph_components.restrict_copies',return_value=[]):
                full=enumerate_assignments(g,m,ns,{},max_classes=n)
            fast=enumerate_assignments(g,m,ns,{},max_classes=n)
            self.assertEqual((fast['status'],sets(fast)),(full['status'],sets(full)))
        self.assertEqual(len(sets(fast)),8)

    def test_different_chemical_graphs_with_same_topology_not_pruned(self):
        g,m,n,d=chlorinated_copies(3)
        next(a for a in g['atoms'] if a['id']=='a1')['formal_charge']=-1
        self.assertEqual(enumerate_assignments(g,m,n,d)['equivalent_fragment_groups'],[])

    def test_nitrogen_acceptor_exclusions_remain_distinct(self):
        # A synthetic topology with two isodegree N sites requiring different acceptor rules.
        g={'atoms':[dict(id=k,element=e,formal_charge=q,hydrogens=h) for k,e,q,h in
                   [('a','N',0,0),('b','N',1,0),('c','C',0,1),('x','Cl',-1,0)]],
           'bonds':[['a','b',2],['a','c',1],['b','c',2]]}
        m=[dict(label=a['id'].upper(),element=a['element']) for a in g['atoms']]
        n={'A':{'B','C'},'B':{'A','C'},'C':{'A','B'},'X':set()}
        self.assertEqual(enumerate_assignments(g,m,n,{})['assignment_classes'],6)

    def test_unit_accounting_guards_and_multiplicity(self):
        atom=dict(label='C1',element='C',part=0,residue='0',geometric_site_multiplicity=4,
                  general_multiplicity=4,inferred_cif_occupancy=1.,unit_cell_contribution=4)
        def count(sites,cmd='HFIX 23 C1',value=2):
            return predicted_unit_h({'C1':value},[cmd],{'atoms':sites})
        self.assertEqual(count([atom]),8)
        for change in [dict(part=1),dict(inferred_cif_occupancy=.5),dict(geometric_site_multiplicity=2)]:
            with self.assertRaises(ValueError):count([atom|change])
        with self.assertRaises(ValueError):count([atom,atom|dict(label='H1',element='H')])
        with self.assertRaises(ValueError):count([atom],value=3)

    def test_labelled_cycle_with_shuffled_input(self):
        g={'atoms':[dict(id=str(i),element=e,formal_charge=0,hydrogens=h) for i,(e,h) in enumerate([('O',0)]+[('C',2)]*4)],
           'bonds':[[str(i),str((i+1)%5),1] for i in range(5)]}
        atoms,adj=parse_graph(g)
        key=small_fragment_key(list(atoms),atoms,adj)
        self.assertTrue(all(key==small_fragment_key(list(order),atoms,adj) for order in itertools.permutations(atoms)))

    def test_hydrogen_scope_and_non_donor(self):
        g,*_=chlorinated_copies(1)
        self.assertEqual(hydrogen_scope(g),(2,[]))
        g['atoms']=[dict(id='c',element='C',formal_charge=0,hydrogens=3),dict(id='o',element='O',formal_charge=0,hydrogens=1)]
        g['bonds']=[['c','o',1]]
        self.assertEqual(hydrogen_scope(g),(4,['o']))
        del g['atoms'][1]['hydrogens']
        with self.assertRaises(ValueError):hydrogen_scope(g)

    def test_no_H_graph_without_H_sfac_or_TEMP(self):
        graph={'atoms':[dict(id=v,element='Cl',hydrogens=0,formal_charge=0) for v in ['a','b']],'bonds':[['a','b',1]]}
        res='TITL synthetic\nCELL .71 16 17 18 90 90 90\nLATT -1\nSFAC Cl\nUNIT 2\nFVAR 1\nCl1 1 .2 .2 .3 11 .03\nCl2 1 .32 .2 .3 11 .03\nHKLF 4\nEND\n'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'model.res';path.write_text(res)
            self.assertEqual(propose(path,graph)['status'],'candidates_ready')
            with self.assertRaisesRegex(ValueError,'TEMP'):
                propose(path,chlorinated_copies(1)[0])

    def test_missing_nonfinite_and_cif_uncertainties(self):
        metrics=dict(NPD_atoms=0,last_abs_max_shift_esd=0,R1_observed=.04,GooF=1.)
        g={'atoms':[dict(element='C',formal_charge=0)]}
        def check(density,**change):
            return basic_findings(metrics|change,{'local_adp_flags':[],'residual_density':density},g)
        self.assertFalse(check(['0.31(2)','-0.23(3)']))
        for v in ('?','.',None,'-inf','NaN',False):
            self.assertTrue(check([v,-.23]))
        for v in (None,float('nan'),-.1,True):
            self.assertTrue(check([.31,-.23],last_abs_max_shift_esd=v))
        self.assertTrue(check([-.23,.31]))
