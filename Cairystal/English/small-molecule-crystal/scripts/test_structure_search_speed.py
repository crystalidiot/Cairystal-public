"""Checks on equivalent terminal labels and exact-byte reflection preflight reuse."""
from itertools import permutations
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from crystal_runtime import sha
from graph_assignment import enumerate_assignments
from run_crystal_stage import staged_hkl_check


class StructureSearchTests(unittest.TestCase):
    def test_equivalent_tails_match_exhaustive_two_fragment_result(self):
        graph = {'atoms': [], 'bonds': []}
        near = {}
        for prefix in ('p','q'):
            graph['atoms'].append(dict(id=prefix,element='C',hydrogens=0,formal_charge=0))
            neighbors = []
            for suffix, element in [('1','F'),('2','F'),('3','F'),('4','Cl')]:
                key = prefix + suffix
                graph['atoms'].append(dict(id=key,element=element,hydrogens=0,formal_charge=0))
                graph['bonds'].append([prefix, key, 1])
                neighbors.append(key.upper())
                near[key.upper()] = {prefix.upper()}
            near[prefix.upper()] = set(neighbors)
        atoms = [dict(label=a['id'].upper(),element=a['element']) for a in reversed(graph['atoms'])]
        graph['atoms'].reverse()
        result = enumerate_assignments(graph, atoms, near, {})
        reference = []
        for centres in permutations(('P','Q')):
            for left in permutations('123'):
                for right in permutations('123'):
                    mapping = {}
                    for prefix, centre, suffixes in zip(('p','q'), centres, (left,right)):
                        mapping[prefix]=centre
                        mapping.update({prefix+i: centre+j for i,j in zip('1234',(*suffixes,'4'))})
                    reference.append(tuple(sorted(mapping.items())))
        self.assertEqual(result['assignment_classes'], 1)
        self.assertEqual(result['complete_label_mappings'],len(reference))
        candidate = result['candidates'][0]
        self.assertEqual(tuple(sorted(candidate['original_mapping'].items())), min(reference))
        self.assertEqual(candidate['label_permutations'], len(reference))

    def test_snapshot_change_invalidates_hkl_check(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp)/'obs.hkl'
            working = Path(tmp)/'model.hkl'
            data = b'   1   2   3   10.00    1.00\r\n'
            source.write_bytes(data)
            working.write_bytes(data)
            a,hit=staged_hkl_check(source, working, sha(source))
            self.assertFalse(hit)
            a['format_issue_samples'].append({'mutated':True})
            b,hit=staged_hkl_check(source, working, sha(source))
            self.assertTrue(hit)
            self.assertEqual(b['format_issue_samples'],[])
            working.write_bytes(data.replace(b'10.00',b'20.00'))
            with self.assertRaisesRegex(ValueError,'differs'):
                staged_hkl_check(source,working,sha(source))
            source.write_bytes(working.read_bytes())
            c,hit=staged_hkl_check(source, working, sha(source))
            self.assertFalse(hit)
            self.assertNotEqual(c['sha256'],b['sha256'])
