"""Same backend bytes in a different release must not reuse old UI assets."""
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch, Mock
import tempfile
import unittest
from launch_console import healthy

class ReleaseReuseTests(unittest.TestCase):
    def check(self, root_value):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);script=root/'release/scripts/crystal_console.py';script.parent.mkdir(parents=True);script.write_text('same backend')
            workspace=root/'workspace';workspace.mkdir()
            h={'service':'cairystal-console','pid':123,'code_hash':hashlib.sha256(script.read_bytes()).hexdigest(),
               'workspace_hash':hashlib.sha256(str(workspace).casefold().encode()).hexdigest()}
            if root_value is not None:h['skill_root']=str(script.parent.parent.resolve()) if root_value=='same' else str(root/'old_release')
            opener=Mock();opener.open.return_value=io.BytesIO(json.dumps(h).encode())
            with patch('launch_console.urllib.request.build_opener',return_value=opener):
                return healthy({'url':'http://127.0.0.1:12345/','pid':123},workspace,script)
    def test_other_release_is_not_reused(self):self.assertFalse(self.check('old'))
    def test_same_release_can_be_reused(self):self.assertTrue(self.check('same'))
    def test_old_protocol_without_release_is_not_reused(self):self.assertFalse(self.check(None))

if __name__=='__main__':unittest.main()
