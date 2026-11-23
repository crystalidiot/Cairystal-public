import tempfile,unittest
from pathlib import Path
import gemmi
from routine_finish import carry_metadata

class UnknownMetadataTests(unittest.TestCase):
    def check(self,source,expected):
        with tempfile.TemporaryDirectory() as t:
            a=Path(t)/'a.cif';b=Path(t)/'b.cif'
            a.write_text('data_x\n'+source,encoding='utf-8')
            b.write_text('data_x\n_diffrn_ambient_temperature 293(2)\n_cell_measurement_temperature 293(2)\n_exptl_crystal_colour blue\n_cell_length_a 12.345(6)\n',encoding='utf-8')
            changes=carry_metadata(a,b,0);doc=gemmi.cif.read_file(str(b)).sole_block()
            self.assertEqual(doc.find_value('_cell_length_a'),'12.345(6)')
            for k,v in expected.items():self.assertEqual(doc.find_value(k),v)
            return changes
    def test_unknown_temperature(self):
        self.check('_diffrn_ambient_temperature ?\n_cell_measurement_temperature ?\n',{'_diffrn_ambient_temperature':'?','_cell_measurement_temperature':'?'})
    def test_absent_temperature_not_native_default(self):
        self.check('_chemical_name_common ?\n',{'_diffrn_ambient_temperature':'?','_cell_measurement_temperature':'?'})
    def test_known_temperature_retained(self):
        self.check('_diffrn_ambient_temperature 100(2)\n',{'_diffrn_ambient_temperature':'100(2)'})
    def test_not_applicable_preserved(self):
        self.check('_exptl_crystal_colour .\n',{'_exptl_crystal_colour':'.'})
    def test_unknown_colour_preserved(self):
        self.check('_exptl_crystal_colour ?\n',{'_exptl_crystal_colour':'?'})

if __name__=='__main__':unittest.main()
