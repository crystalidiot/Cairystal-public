import random
import tempfile
import unittest
from pathlib import Path

from crystal_session import laue_seed, parse_p4p


class MeasuredSeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hkl = Path(self.tmp.name) / "sample.hkl"
        self.meta = parse_p4p("CELL 8 9 10 90 100 90\nCELLSD .01 .01 .01 0 .01 0\nSOURCE Mo .71073\n")

    def write(self, centred=False, mates=True):
        rng = random.Random(519)
        rows = []
        for h in range(1,8):
            for k in range(1,7):
                for l in range(1,6):
                    if centred and (h+k)%2:
                        continue
                    value = rng.randrange(12, 500)
                    for x,y,z in ([(h,k,l),(-h,k,-l)] if mates else [(h,k,l)]):
                        rows.append(f"{x:4d}{y:4d}{z:4d}{value:8.2f}{1:8.2f}")
        self.hkl.write_text("\n".join(rows)+"\n   0   0   0    0.00    0.00\n")

    def test_supported_rotation_is_a_search_seed(self):
        self.write()
        lattice, ops, _ = laue_seed(self.meta,self.hkl)
        self.assertEqual((lattice,ops),(1,["-X,Y,-Z"]))
        self.assertTrue(self.meta["laue_screen"]["passed"])
        self.assertNotIn("bravais",self.meta)

    def test_c_centring_is_not_overridden(self):
        self.write(centred=True)
        with self.assertRaisesRegex(ValueError,"Centring unresolved"):
            laue_seed(self.meta,self.hkl)

    def test_missing_mates_are_not_negative_evidence(self):
        self.write(mates=False)
        with self.assertRaisesRegex(ValueError,"incomplete"):
            laue_seed(self.meta,self.hkl)

    def test_symm_declaration_must_agree(self):
        self.write()
        self.meta["declared_symmetry"] = ["mmm"]
        with self.assertRaisesRegex(ValueError,"conflicts"):
            laue_seed(self.meta,self.hkl)

    def test_cell_alone_requires_reflections(self):
        with self.assertRaisesRegex(ValueError,"measured HKLF"):
            laue_seed(self.meta)
