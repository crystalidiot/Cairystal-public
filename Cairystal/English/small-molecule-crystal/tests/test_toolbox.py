"""Exercise public toolbox calls, not scientific correctness or live web services."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import toolbox

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts" / "toolbox.py"


class ToolboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def call(self, *args, entry=ENTRY, isolated=False):
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        # Only for the tests' native tool imports; discovery must also work under -S.
        env["PYTHONPATH"] = os.pathsep.join(str(x) for x in sys.path if x)
        cmd = [sys.executable, "-B"]
        if isolated:
            cmd.append("-S")
        return subprocess.run([*cmd, str(entry), *map(str,args)], cwd=self.directory,
                              env=env, encoding="utf-8", capture_output=True, timeout=90)

    def test_catalog_discovery_without_site_packages(self):
        result = self.call("list", "--json", isolated=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        entries = json.loads(result.stdout)["tools"]
        self.assertGreaterEqual(len(entries), 25)
        self.assertEqual(len({x["id"] for x in entries}), len(entries))
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_description_and_group_filter_in_both_languages(self):
        for lang, title in [("zh-CN","IUCr 官网"),("en","official IUCr")]:
            result = self.call("--language",lang,"describe","checkcif")
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn(title,result.stdout)
        result = self.call("list","--group","validation","--json")
        self.assertEqual({x["group"] for x in json.loads(result.stdout)["tools"]},{"validation"})

    def test_every_registered_cli_supports_help_without_creating_outputs(self):
        for entry in toolbox.load_catalog()["tools"]:
            with self.subTest(tool=entry["id"]):
                result = self.call("run",entry["id"],"--","--help")
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn("usage:",result.stdout.lower())
        self.assertEqual(list(self.directory.iterdir()),[])

    def test_preview_is_not_execution_or_permission_and_preserves_literal_args(self):
        literal = "中文 path & ; $(do_not_execute)"
        result=self.call("plan","checkcif","--","--cif",literal,"--output",self.directory/"new")
        self.assertEqual(result.returncode,0,result.stderr)
        record=json.loads(result.stdout)
        self.assertFalse(record["executed"])
        self.assertFalse(record["authorization_granted"])
        self.assertFalse(record["arguments_validated"])
        self.assertEqual(record["argv"][-4:],["--cif",literal,"--output",str(self.directory/"new")])
        self.assertNotIn("--authorize-iucr-upload",record["argv"])
        self.assertEqual(list(self.directory.iterdir()),[])

    def test_unknown_tool_or_missing_separator_does_not_execute(self):
        for args in [("run","../outside","--","--help"),("run","metadata","--help"),
                     ("list","--group","invented")]:
            result=self.call(*args)
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
        self.assertEqual(list(self.directory.iterdir()),[])

    def test_unicode_metadata_tool_matches_direct_call_and_preserves_input(self):
        source=self.directory/"实验 参数 & 原始.pcf"
        source.write_text("_cell_measurement_reflns_used 850\n_cell_measurement_theta_min 2.90\n"
                          "_cell_measurement_theta_max 28.0\n_exptl_crystal_description block\n",
                          encoding="utf-8")
        original=hashlib.sha256(source.read_bytes()).hexdigest()
        wrapped=self.call("run","metadata","--",source)
        direct=subprocess.run([sys.executable,"-B",str(ROOT/"scripts/inspect_experiment_metadata.py"),str(source)],
                              encoding="utf-8",capture_output=True,timeout=30)
        self.assertEqual(wrapped.returncode,direct.returncode)
        self.assertEqual(wrapped.returncode,0,wrapped.stdout+wrapped.stderr)
        self.assertEqual(json.loads(wrapped.stdout),json.loads(direct.stdout))
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),original)

    def test_underlying_error_is_not_rewritten_as_success(self):
        result=self.call("run","metadata","--",self.directory/"missing.pcf")
        self.assertEqual(result.returncode,2,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"],"error")
        self.assertIn("metadata_inspection",result.stdout)

    def test_native_usage_error_goes_to_stderr(self):
        result=self.call("run","metadata","--","--invented-option")
        self.assertEqual(result.returncode,2)
        self.assertIn("usage:",result.stderr)
        self.assertEqual(result.stdout,"")

    def test_official_upload_without_consent_remains_blocked(self):
        source=self.directory/"synthetic.cif"
        source.write_text("data_synthetic\n_exptl_crystal_description block\n",encoding="ascii")
        out=self.directory/"official"
        result=self.call("run","checkcif","--","--cif",source,"--output",out)
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        record=json.loads(result.stdout)
        self.assertEqual(record["state"],"incomplete")
        self.assertIn("no network submission performed",record["error"])
        self.assertFalse((out/"submitted.cif").exists())

    def test_local_intake_form_is_real_and_not_an_upload(self):
        out=self.directory/"问卷 output"
        result=self.call("run","intake-form","--","--language","zh-CN","--output",out)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        form=Path(json.loads(result.stdout)["form"])
        self.assertTrue(form.is_file())
        self.assertIn("0.050",form.read_text("utf-8"))
        self.assertFalse((out/"submission.json").exists())

    def test_resume_without_consent_does_not_create_lock_or_upload(self):
        result=self.call('run','resume-delivery','--','--run',self.directory)
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('not been authorized',result.stdout)
        self.assertEqual(list(self.directory.iterdir()),[])

    def test_relocation_needs_no_machine_paths_or_scientific_dependencies(self):
        other=self.directory/"another machine 中文"
        (other/"scripts").mkdir(parents=True)
        shutil.copy2(ENTRY,other/"scripts/toolbox.py")
        shutil.copytree(ROOT/"assets",other/"assets")
        shutil.copytree(ROOT/"references",other/"references")
        shutil.copy2(ROOT/"language.json",other/"language.json")
        shutil.copy2(ROOT/"release_info.json",other/"release_info.json")
        # Real registered CLIs are copied, not replaced with test stubs.
        for entry in toolbox.load_catalog()["tools"]:
            shutil.copy2(ROOT/"scripts"/entry["script"],other/"scripts"/entry["script"])
        result=self.call("plan","metadata","--","sample.pcf",entry=other/"scripts/toolbox.py",isolated=True)
        self.assertEqual(result.returncode,0,result.stderr)
        # Windows may return the canonical AppData directory casing.
        self.assertEqual(os.path.normcase(json.loads(result.stdout)["argv"][2]),os.path.normcase(str(other/"scripts/inspect_experiment_metadata.py")))

    def test_new_sop_and_catalog_links_resolve(self):
        for file in ["SKILL.md","SKILL.zh-CN.md","SKILL.en.md",
                     "references/toolbox.md","references/toolbox.en.md",
                     "references/operating-protocol.zh-CN.md","references/operating-protocol.en.md"]:
            path=ROOT/file
            for link in re.findall(r"\]\(([^)]+)\)",path.read_text("utf-8")):
                if not link.startswith(("http:","https:","#")):
                    self.assertTrue((path.parent/link.split("#",1)[0]).exists(),(file,link))


if __name__ == "__main__":
    unittest.main()
