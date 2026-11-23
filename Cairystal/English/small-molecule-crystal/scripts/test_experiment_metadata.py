"""Synthetic controls for read-only CIF/PCF metadata inspection, not model validity."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import inspect_experiment_metadata as inspector


class ExperimentMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "实验.pcf"

    def write(self, content):
        self.source.write_text(content, encoding="utf-8")

    def test_headerless_pcf_has_no_cell_and_preserves_input(self):
        self.write("# metadata fragment\n_cell_measurement_reflns_used 850\n"
                   "_cell_measurement_theta_min 2.90\n_cell_measurement_theta_max 28.0\n"
                   "_exptl_crystal_description 'block'\n")
        before = self.source.read_bytes()
        result = inspector.inspect_metadata(self.source)
        self.assertTrue(result["in_memory_header_added"])
        self.assertFalse(result["ready_for_merge"])
        self.assertEqual(result["blocks"][0]["essential_not_present_as_scalar"], [])
        self.assertNotIn("_cell_length_a", json.dumps(result))
        self.assertEqual(before, self.source.read_bytes())
        self.assertEqual(result["source_sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_model_and_embedded_inputs_are_not_emitted(self):
        self.write("data_test\n_exptl_crystal_colour colourless\n"
                   "_chemical_formula_sum 'SECRET_FORMULA'\n_refine_ls_R_factor_gt 0.032\n"
                   "loop_\n_atom_site_label\n_atom_site_fract_x\nSECRET_ATOM 0.123456\n"
                   "_shelx_res_file\n;\nSECRET_RES\n;\n")
        result = inspector.inspect_metadata(self.source)
        text = json.dumps(result)
        for protected in ("SECRET_", "0.123456", "0.032", "_atom_site", "_shelx"):
            self.assertNotIn(protected, text)
        self.assertEqual(set(result["blocks"][0]["fields"]), {"_exptl_crystal_colour"})

    def test_multiple_blocks_and_conflicts_are_not_selected(self):
        self.write("data_one\n_exptl_crystal_description block\n"
                   "data_two\n_exptl_crystal_description needle\n")
        result = inspector.inspect_metadata(self.source)
        self.assertEqual([b["block"] for b in result["blocks"]], ["one", "two"])
        self.assertEqual(len(result["cross_block_disagreements"]), 1)
        self.assertFalse(result["ready_for_merge"])

    def test_unknown_dot_and_quoted_question_remain_distinct(self):
        self.write("data_test\n_cell_measurement_reflns_used ?\n"
                   "_cell_measurement_theta_min .\n_exptl_crystal_description '?'\n")
        fields = inspector.inspect_metadata(self.source)["blocks"][0]["fields"]
        self.assertEqual(fields["_cell_measurement_reflns_used"]["state"], "unknown")
        self.assertEqual(fields["_cell_measurement_theta_min"]["state"], "not_applicable")
        self.assertEqual(fields["_exptl_crystal_description"]["state"], "present_unverified")

    def test_case_insensitive_tags_multiline_unicode_and_bom(self):
        self.source.write_text("data_test\n_EXPTL_CRYSTAL_DESCRIPTION '块状'\n"
                               "_exptl_absorpt_process_details\n;\n多行记录\n第二行\n;\n",
                               encoding="utf-8-sig")
        fields = inspector.inspect_metadata(self.source)["blocks"][0]["fields"]
        self.assertEqual(fields["_exptl_crystal_description"]["value"], "块状")
        self.assertIn("第二行", fields["_exptl_absorpt_process_details"]["value"])

    def test_looped_metadata_is_flagged_not_imported(self):
        self.write("data_test\nloop_\n_exptl_crystal_colour\ncolourless\n")
        block = inspector.inspect_metadata(self.source)["blocks"][0]
        self.assertEqual(block["fields"], {})
        self.assertEqual(block["looped_metadata_requires_review"], ["_exptl_crystal_colour"])

    def test_invalid_and_unsupported_sources_fail_without_repair(self):
        for text in ("not a CIF\n", "", "data_test\n_exptl_crystal_colour\n",
                     "data_test\nsave_one\n_exptl_crystal_colour blue\nsave_\n"):
            with self.subTest(text=text):
                self.write(text)
                original = self.source.read_bytes()
                with self.assertRaises(ValueError):
                    inspector.inspect_metadata(self.source)
                self.assertEqual(original, self.source.read_bytes())
        with self.assertRaises(ValueError):
            inspector.inspect_metadata(self.root)

    def test_encoding_must_be_explicit_and_read_is_bounded(self):
        self.source.write_bytes("_exptl_crystal_description '块状'\n".encode("gbk"))
        with self.assertRaises(ValueError):
            inspector.inspect_metadata(self.source)
        result = inspector.inspect_metadata(self.source, "gbk")
        self.assertEqual(result["blocks"][0]["fields"]["_exptl_crystal_description"]["value"], "块状")
        with patch.object(inspector, "MAX_BYTES", 8):
            with self.assertRaises(ValueError):
                inspector.inspect_metadata(self.source, "gbk")

    def test_cli_json_success_and_failure(self):
        command = [sys.executable, "-B", str(Path(inspector.__file__)), str(self.source)]
        self.write("_exptl_crystal_colour colourless\n")
        good = subprocess.run(command, capture_output=True, encoding="utf-8")
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)["status"], "inspected")
        self.write("data_test\n_atom_site_fract_x\n")
        bad = subprocess.run(command, capture_output=True, encoding="utf-8")
        self.assertEqual(bad.returncode, 2, bad.stderr)
        self.assertEqual(json.loads(bad.stdout)["status"], "error")
        self.assertNotIn("_atom_site", bad.stdout)


if __name__ == "__main__":
    unittest.main()
