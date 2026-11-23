import unittest
from fragment_orbits import occupancy_bound,site_account

class FragmentOrbitsTests(unittest.TestCase):
    def test_special_site_physical_occupancy_is_not_sof(self):
        a=site_account(.105,2,1)
        self.assertAlmostEqual(a['physical_occupancy'],.21)
        self.assertAlmostEqual(a['atoms_per_cell'],.21)
    def test_general_half_occupied_orientation(self):
        a=site_account(.5,2,2)
        self.assertEqual(a['physical_occupancy'],.5)
        self.assertEqual(a['atoms_per_cell'],1)
    def test_two_half_orientations_are_not_overoccupied(self):
        self.assertEqual(occupancy_bound([{'id':'a','probability':.5},{'id':'b','probability':.5}],[[0,1]]),[])
    def test_pairwise_valid_can_fail_triple(self):
        states=[{'id':str(i),'probability':p} for i,p in enumerate([.9,.1,.1])]
        bad=occupancy_bound(states,[[0,1],[1,2],[0,2]])
        self.assertEqual(len(bad),1);self.assertAlmostEqual(bad[0]['population_sum'],1.1)
    def test_probability_sum_without_clique_is_not_rejected(self):
        states=[{'id':str(i),'probability':p} for i,p in enumerate([.9,.1,.1])]
        self.assertEqual(occupancy_bound(states,[[0,1],[0,2]]),[])
    def test_conditional_half_minor_satisfies_bound(self):
        states=[{'id':str(i),'probability':p} for i,p in enumerate([.9,.05,.05])]
        self.assertEqual(occupancy_bound(states,[[0,1],[1,2],[0,2]]),[])
    def test_pair_overoccupation(self):
        states=[{'id':str(i),'probability':p} for i,p in enumerate([.8,.3])]
        self.assertEqual(len(occupancy_bound(states,[[0,1]])),1)
    def test_invalid_multiplicity(self):
        with self.assertRaises(ValueError):site_account(.5,2,0)

if __name__=='__main__':unittest.main()
