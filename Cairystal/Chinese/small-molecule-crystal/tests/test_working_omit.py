import unittest
from pathlib import Path
from ab_auto import generate_requests,load_policy
from working_omit import select,notes


def request(rows,code='934',previous=False,npd=0,printed=''):
    packet={'all_atoms':[],'regions':[],'AB_alerts':[{'code':code,'level':'B','text':printed}],
            'restraint_tension':{'needs_review':True},'gate':{'metrics':{'NPD_atoms':npd}},
            'reflection_evidence':{'weighted_outliers':rows}}
    parsed={'atoms':[],'sfac':[],'rows':[['OMIT','2','1','0']] if previous else []}
    return generate_requests(packet,parsed,load_policy())[0]


class WorkingOmit(unittest.TestCase):
    def setUp(self):
        self.rows=[{'hkl':[n,1,3],'status':'o','delta_over_sigmaW':-11.,'theta_degrees':2.}
                   for n in range(21)]

    def test_existing_disorder_restraint_routes_exact_twenty(self):
        self.assertEqual(request(self.rows[:20])[0]['parameters']['hkls'],[r['hkl'] for r in self.rows[:20]])

    def test_no_partial_list_when_total_exceeds_twenty(self):
        self.rows[-1]['theta_degrees']=6
        self.assertFalse(request(self.rows,'919'))

    def test_excludes_exactly_ten_and_inconsistent_native_count(self):
        self.assertFalse(request(self.rows[:1],printed='2 Check'))
        self.rows[0]['delta_over_sigmaW']=10.
        self.assertFalse(request(self.rows[:1]))

    def test_no_recursive_pruning_or_npd(self):
        self.assertFalse(request(self.rows[:1],previous=True))
        self.assertFalse(request(self.rows[:1],npd=1))

    def test_global_fit_alone_cannot_select(self):
        r=select([],[],[{'reflection_omit':True}],{'AB_alerts':[{'code':'939'}]},Path('.'))
        self.assertFalse(r['selected'])

    def test_both_languages_document_signed_evidence_and_count(self):
        text=notes({'hkls':[[0,1,3]],'weighted_evidence':[self.rows[0]],'used_reflections':[2000,1999]})
        for language in ('zh','en'):
            for value in ('0, 1, 3','-11.00','2000','1999'):
                self.assertIn(value,text[language])
