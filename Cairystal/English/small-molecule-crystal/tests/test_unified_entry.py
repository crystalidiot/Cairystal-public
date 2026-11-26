import hashlib,json,os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import project_launcher as launcher
import toolbox

class UnifiedEntryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.skill=self.root/'release/skill';self.skill.mkdir(parents=True)
        (self.skill/'assets').mkdir();(self.skill/'scripts').mkdir()
        (self.skill/'cairystal.py').write_text('test entry','utf-8')
        self.profile=self.root/'profile.json'
        self.profile.write_text(json.dumps({'python':'selected-python','module_dirs':['local-dependencies']}),'utf-8')
        (self.skill/'release_info.json').write_text(json.dumps({'release_id':'test-release'}),'utf-8')
        (self.skill/'assets/toolbox.json').write_text(json.dumps(toolbox.load_catalog()),'utf-8')
        manifest={'cairystal.py':hashlib.sha256((self.skill/'cairystal.py').read_bytes()).hexdigest()}
        (self.skill.parent/'release_manifest.json').write_text(json.dumps(manifest),'utf-8')
        self.record={'release':'test-release','skill':str(self.skill),'profile':str(self.profile),'profile_sha256':hashlib.sha256(self.profile.read_bytes()).hexdigest()}
        for name in ['Cairystal.current.json','Cairystal.fast.json']:
            (self.root/name).write_text(json.dumps(self.record),'utf-8')

    def dispatch(self,*args):
        with patch.object(launcher.subprocess,'call',return_value=7) as call:
            result=launcher.dispatch(self.root,args)
        self.assertEqual(result,7) # Native failure must survive the wrapper.
        return call.call_args

    def test_canonical_and_legacy_toolbox_same_command(self):
        self.assertEqual(self.dispatch('list','--json'),self.dispatch('toolbox','list','--json'))

    def test_fast_compatibility_does_not_change_explicit_mode(self):
        args=self.dispatch('--channel','fast','autorun','run','--config','job.json').args[0]
        self.assertEqual(args[-2:],['--execution-mode','fast'])
        args=self.dispatch('--channel','fast','run','autorun','--','run','--execution-mode','standard').args[0]
        self.assertEqual(args.count('--execution-mode'),1);self.assertEqual(args[-1],'standard')

    def test_literal_args_and_authorization_not_added(self):
        literal='中文 & ; $(test)'
        call=self.dispatch('checkcif','--cif',literal,'--output','new')
        self.assertIn(literal,call.args[0]);self.assertNotIn('--authorize-iucr-upload',call.args[0])
        self.assertFalse(call.kwargs['shell']);self.assertIn('local-dependencies',call.kwargs['env']['PYTHONPATH'])

    def test_legacy_profile_and_squeeze_contracts(self):
        args=self.dispatch('pipeline','start','--data-dir','input').args[0]
        self.assertEqual(args[-2],'--profile');self.assertEqual(os.path.normcase(args[-1]),os.path.normcase(str(self.profile)))
        self.assertTrue(self.dispatch('squeeze','--help').args[0][2].endswith('squeeze_workflow.py'))
        args=self.dispatch('squeeze-request','execute','--job','job').args[0]
        self.assertIn('squeeze',args);self.assertEqual(args[-2],'--profile');self.assertEqual(os.path.normcase(args[-1]),os.path.normcase(str(self.profile)))

    def test_mismatched_release_never_executes(self):
        self.record['release']='other'
        (self.root/'Cairystal.current.json').write_text(json.dumps(self.record),'utf-8')
        with patch.object(launcher.subprocess,'call') as call,self.assertRaises(ValueError):
            launcher.dispatch(self.root,['list'])
        call.assert_not_called()

    def test_modified_profile_or_source_never_executes(self):
        for path in [self.profile,self.skill/'cairystal.py']:
            old=path.read_bytes();path.write_bytes(old+b' ')
            with patch.object(launcher.subprocess,'call') as call,self.assertRaises(ValueError):
                launcher.dispatch(self.root,['list'])
            call.assert_not_called();path.write_bytes(old)

    def test_routes_use_current_registered_tools(self):
        catalog=toolbox.load_catalog();data=toolbox.workflow_map(catalog)
        self.assertEqual(data['release'],toolbox.release_identity()['release_id'])
        self.assertFalse(data['executed']);self.assertFalse(data['automatic_repairs_performed'])
        chemistry=next(x for x in data['steps'] if x['id']=='chemistry')
        self.assertIn('hydrogen-continue',chemistry['tools'])
        self.assertIn('chemistry-screen',chemistry['tools'])

    def test_stale_or_invalid_route_is_rejected(self):
        root=self.root/'map';(root/'assets/console').mkdir(parents=True)
        data=toolbox.workflow_map(toolbox.load_catalog())
        data['steps'][0]['tools'].append('not-registered')
        (root/'assets/console/workflow-data.json').write_text(json.dumps(data),'utf-8')
        with self.assertRaises(ValueError):toolbox.workflow_map(toolbox.load_catalog(),root)

if __name__=='__main__':unittest.main()
