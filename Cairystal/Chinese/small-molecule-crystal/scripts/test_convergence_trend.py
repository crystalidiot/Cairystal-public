import unittest
from convergence_trend import analyse,ONLY_REASON

def evidence(values=(.060,.047,.037,.029),parameters=None):
    parameters=parameters or ['z HW11']*len(values)
    text='\n'.join(f'Mean shift/esd = 0.001 Maximum = {v} for {p}' for v,p in zip(values,parameters))
    gate=dict(execution_complete=True,failures=[],review_reasons=[ONLY_REASON],metrics={'NPD_atoms':0,'last_abs_max_shift_esd':abs(values[-1])})
    return text,gate

class TrendTests(unittest.TestCase):
    def test_decaying_coordinate(self):
        t,g=evidence();r=analyse(t,g,'L.S. 12\n');self.assertTrue(r['eligible']);self.assertEqual(r['suggested_extra_cycles'],20);self.assertFalse(r['scientific_acceptance'])
    def test_signed_negative_decay(self):
        t,g=evidence((-.060,-.047,-.037,-.029));self.assertTrue(analyse(t,g,'L.S. 12')['eligible'])
    def test_oscillation(self):
        t,g=evidence((-.060,.047,-.037,.029));self.assertFalse(analyse(t,g,'')['eligible'])
    def test_stall_or_growth(self):
        for v in [( .04,.039,.038,.037),(.03,.04,.05,.06),(.06,.04,.04,.03)]:
            t,g=evidence(v);self.assertFalse(analyse(t,g,'')['eligible'])
    def test_other_parameter_or_short_history(self):
        for t,g in [evidence(parameters=['z H1','z H1','x H2','x H2']),evidence((.04,.03))]:self.assertFalse(analyse(t,g,'')['eligible'])
    def test_gate_failures_and_unknown(self):
        for key,value in [('failures',['error']),('execution_complete',False),('review_reasons',[ONLY_REASON,'other'])]:
            t,g=evidence();g[key]=value;self.assertFalse(analyse(t,g,'')['eligible'])
        for npd in [1,None]:
            t,g=evidence();g['metrics']['NPD_atoms']=npd;self.assertFalse(analyse(t,g,'')['eligible'])
    def test_floor_block_damp(self):
        for card in ['BLOC 1','XNPD -0.01','DAMP 0 0','CGLS 20']:
            t,g=evidence();self.assertFalse(analyse(t,g,card)['eligible'])
    def test_stale_gate_large_or_converged(self):
        t,g=evidence();g['metrics']['last_abs_max_shift_esd']=.04;self.assertFalse(analyse(t,g,'')['eligible'])
        for values in [(.9,.7,.5,.3),(.04,.02,.01,.005)]:
            t,g=evidence(values);self.assertFalse(analyse(t,g,'')['eligible'])
    def test_high_correlation(self):
        t,g=evidence();t+='\nLargest correlation matrix elements\n 0.945 z H1 / z H2\n';self.assertFalse(analyse(t,g,'')['eligible'])
    def test_realistic_correlation(self):
        t,g=evidence();t+='\nLargest correlation matrix elements\n -0.669 z H1 / z H2\n';self.assertTrue(analyse(t,g,'')['eligible'])

if __name__=='__main__':unittest.main()
