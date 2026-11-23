import unittest
import gemmi
from configuration_orbits import equivalent_configuration,unique_configurations,predicted_site_population,norm_operation,audit_fragment_hydrogens

class ConfigurationOrbitTests(unittest.TestCase):
    def setUp(self):
        self.cell=gemmi.UnitCell(10,10,10,90,90,90)
        self.atoms=[{'label':'A','element':'C','xyz':[.5,.5,.5]},
                    {'label':'B','element':'C','xyz':[.4,.6,.5]},
                    {'label':'C','element':'C','xyz':[.6,.6,.5]}]
        self.ops=[gemmi.Op(s) for s in ['x,y,z','1-x,y,1-z','x,1-y,z','1-x,1-y,1-z']]
    def test_whole_molecule_stabilizer_removes_duplicates(self):
        s=unique_configurations(self.cell,self.atoms,self.ops,'g',.5)
        self.assertEqual(len(s),2)
        self.assertEqual([len(x['equivalent_operations']) for x in s],[2,2])
    def test_shared_special_site_sums_two_half_orientations(self):
        s=unique_configurations(self.cell,self.atoms,self.ops,'g',.5)
        self.assertAlmostEqual(predicted_site_population(self.cell,[.5,.5,.5],'C',s),1.)
        self.assertAlmostEqual(predicted_site_population(self.cell,[.4,.6,.5],'C',s),.5)
    def test_identical_atoms_must_match_bijectively(self):
        bad=[self.atoms[0],self.atoms[0],self.atoms[2]]
        self.assertFalse(equivalent_configuration(self.cell,self.atoms,bad))
    def test_one_global_lattice_shift_allowed(self):
        b=[dict(x,xyz=[x['xyz'][0]+1,x['xyz'][1]-2,x['xyz'][2]]) for x in self.atoms]
        self.assertTrue(equivalent_configuration(self.cell,self.atoms,b))
    def test_independent_atom_image_jumps_rejected(self):
        b=[dict(x,xyz=list(x['xyz'])) for x in self.atoms];b[0]['xyz'][0]+=1
        self.assertFalse(equivalent_configuration(self.cell,self.atoms,b))
    def test_element_swap_is_not_equivalent(self):
        b=[dict(x) for x in self.atoms];b[0]['element']='N'
        self.assertFalse(equivalent_configuration(self.cell,self.atoms,b))
    def test_symmetry_membership_ignores_integer_translation_only(self):
        self.assertEqual(norm_operation(gemmi.Op('-x,y,-z')),norm_operation(gemmi.Op('1-x,y,1-z')))
        self.assertNotEqual(norm_operation(gemmi.Op('-x,y,-z')),norm_operation(gemmi.Op('1/2-x,y,1-z')))
    def test_duplicate_site_is_not_counted_twice_silently(self):
        states=[{'probability':.5,'atoms':[self.atoms[0],self.atoms[0]]}]
        with self.assertRaises(ValueError):predicted_site_population(self.cell,[.5,.5,.5],'C',states)
    def hydrogen_case(self,parent_part,hpart,exported):
        parsed={'atoms':[{'element':'C','label':'C82','part':parent_part},{'element':'H','label':'HS82','part':hpart,'afix':3}]}
        raw={'HS82':{'general_multiplicity':8,'geometric_site_multiplicity':4,'decoded_shelx_sof':.25}}
        cif={'HS82':{'occupancy':exported,'res_context_status':'matched'}}
        return audit_fragment_hydrogens(parsed,cif,raw,{'C82'})[1]
    def test_changed_parent_requires_matching_hydrogen_part(self):
        self.assertTrue(any('PART' in w for w in self.hydrogen_case(1,-1,.5)))
    def test_shared_parent_part_zero_can_have_alternative_hydrogens(self):
        self.assertEqual(self.hydrogen_case(0,-1,.5),[])
    def test_special_hydrogen_export_mismatch_detected(self):
        self.assertTrue(any('occupancy' in w for w in self.hydrogen_case(1,1,.25)))

if __name__=='__main__':unittest.main()
