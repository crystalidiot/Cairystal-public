"""Independent synthetic HKL tests; none contain a solved model."""
import hashlib
import itertools
import json
from pathlib import Path
import random
import tempfile
import unittest

from crystal_autorun import first_model_handoff
from crystal_session import laue_seed
from ortho_laue import LaueReviewRequired, screen


class OrthorhombicStartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root/'fresh.hkl'
        self.meta = dict(bravais='Orthorhombic P',cell=[10,12,14,90,90,90])

    def write(self,indices,signal):
        rows=[]
        for h,k,l in indices:
            if (h,k,l)==(0,0,0):
                continue
            rows.append(f'{h:4d}{k:4d}{l:4d}{signal(h,k,l):8.2f}{2.0:8.2f}')
        self.path.write_text('\n'.join(rows)+'\n   0   0   0    0.00    0.00\n',encoding='ascii')

    @staticmethod
    def indices():
        return itertools.product(range(-8,9),range(-3,4),range(-3,4))

    def test_consistent_mates_without_merging_friedel(self):
        self.write(self.indices(),lambda h,k,l: 400+3*h*h+5*k*k+7*l*l+(150 if h*k*l>0 else -150))
        before=hashlib.sha256(self.path.read_bytes()).hexdigest()
        latt,ops,_=laue_seed(self.meta,self.path)
        self.assertEqual((latt,len(ops)),(1,3))
        ev=self.meta['laue_screen']
        self.assertEqual(ev['hkl_sha256'],before)
        self.assertEqual(before,hashlib.sha256(self.path.read_bytes()).hexdigest())
        for op in ev['operations']:
            self.assertEqual(op['pairs'],288)
            self.assertAlmostEqual(op['cc'],1)
            self.assertEqual(op['r_pair'],0)

    def test_many_contradictory_mates(self):
        rng=random.Random(20261120)
        self.write(self.indices(),lambda *_:rng.uniform(10,600))
        with self.assertRaises(LaueReviewRequired) as caught:
            laue_seed(self.meta,self.path)
        self.assertTrue(all(op['pairs']>=30 and not op['passed'] for op in caught.exception.evidence['operations']))

    def test_reduced_octant_or_weak_data_require_review(self):
        self.write(itertools.product(range(1,9),range(1,5),range(1,5)), lambda h,k,l: 30+h*k*l)
        self.assertFalse(screen(self.path)['passed'])
        self.write(self.indices(),lambda *_: 1)
        self.assertTrue(all(op['pairs']==0 for op in screen(self.path)['operations']))

    def test_flat_intensities_and_zone_only_reflections(self):
        self.write(self.indices(),lambda *_: 100)
        self.assertFalse(screen(self.path)['passed'])
        self.write(((h,k,0) for h in range(-20,21) for k in range(-20,21) if h*k),lambda h,k,l:50+h*h+k*k)
        self.assertFalse(screen(self.path)['passed'])

    def test_declaration_metric_and_observations_required(self):
        with self.assertRaises(ValueError): laue_seed(self.meta)
        for edits in (dict(bravais='Cubic P'),dict(declared_symmetry=['2/m']),dict(cell=[10,12,14,90,105,90])):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                laue_seed(self.meta|edits,self.path)

    def test_packet_reads_only_paired_first_review(self):
        folder=self.root/'pipeline/session/stages/baseline'
        folder.mkdir(parents=True)
        path=folder/'initial_review.json'
        path.write_text(json.dumps(dict(status='needs_review',findings=[{'atom':'C1'}]*4)))
        key=hashlib.sha256(path.read_bytes()).hexdigest()
        candidate={'stage':'baseline','initial_review':{'sha256':key}}
        entry=first_model_handoff(self.root,[candidate])[0]
        self.assertEqual((entry['finding_count'],len(entry['first_findings'])),(4,3))
        path.write_text('{}')
        self.assertEqual(first_model_handoff(self.root,[candidate])[0]['status'],'missing_or_unverified_review')
