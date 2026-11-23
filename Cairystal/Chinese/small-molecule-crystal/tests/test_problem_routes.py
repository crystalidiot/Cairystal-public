import json
from pathlib import Path
import unittest
from route_problem import normalize_alert, select_routes
from toolbox import load_catalog

ROOT=Path(__file__).resolve().parents[1]

class ProblemRouteTests(unittest.TestCase):
    def setUp(self):self.data=json.loads((ROOT/'assets/console/workflow-data.json').read_text('utf-8'))

    def test_alert_level_does_not_change_route(self):
        for name in ['242','PLAT242','242_ALERT_2_B','242_ALERT_2_C']:
            out=select_routes(self.data,[name])
            self.assertIn('light_atoms',{x['id'] for x in out['routes']})
            self.assertFalse(out['automatic_repairs_performed'])

    def test_unknown_alert_is_retained(self):
        out=select_routes(self.data,['000'])
        self.assertEqual(out['unmapped_alerts'],['000'])
        self.assertEqual(out['status'],'needs_review_no_matching_route')

    def test_reference_only_is_not_an_implemented_repair(self):
        covered={c for r in self.data['branches'] for c in r.get('alerts',[])}
        code=next(c for c in self.data['reference_pages'] if c not in covered)
        out=select_routes(self.data,[code])
        self.assertEqual(out['unmapped_alerts'],[code]);self.assertEqual(out['routes'],[])
        self.assertEqual(out['documented_alerts'][0]['code'],code)
        self.assertFalse(out['automatic_repairs_performed'])

    def test_review_findings_route_without_changing_packet(self):
        p={'stage':'02_post_solution','findings':[{'route':'light_atoms'}]}
        before=json.dumps(p)
        out=select_routes(self.data,review=p)
        self.assertEqual([x['id'] for x in out['routes']],['light_atoms'])
        self.assertEqual(json.dumps(p),before)

    def test_reject_non_review_document(self):
        with self.assertRaises(ValueError):select_routes(self.data,review={'stage':'not_a_review'})

    def test_every_route_has_real_tools_references_and_return_step(self):
        steps={s['id'] for s in self.data['steps']}
        tools={t['id'] for t in load_catalog()['tools']}
        ids={b['id'] for b in self.data['branches']}
        self.assertEqual(len(ids),len(self.data['branches']))
        for b in self.data['branches']:
            with self.subTest(route=b['id']):
                self.assertTrue(set(b['tools'])<=tools)
                self.assertIn(b['return_to'],steps)
                self.assertTrue(b['actions'] and b['validation'] and b['stop'] and b['availability'])
                for ref in b['references']:
                    self.assertTrue((ROOT/ref.split('#')[0]).is_file(),ref)
        for s in self.data['steps']:self.assertTrue(set(s['branches'])<=ids)

    def test_requested_knowledge_is_reachable_by_actual_problem(self):
        expected={'196':'temperature','035':'absolute','939':'weights','306':'water','420':'oh','234':'adp_magnitude','214':'adp_shape','934':'outliers','080':'convergence'}
        for code,route in expected.items():
            self.assertIn(route,{r['id'] for r in select_routes(self.data,[code])['routes']})
        self.assertIn('cf3',{r['id'] for r in select_routes(self.data,query='CF₃')['routes']})

if __name__=='__main__':unittest.main()
