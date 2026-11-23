"""Indexed geometry must retain the former exhaustive check, including edges."""
import random
import unittest
from report_autoqa import border_crossings


def exhaustive(chars,edges):
    vertical=[e for e in edges if e.get('orientation')=='v' and e['bottom']-e['top']>8]
    return [{'kind':'table_border_crosses_text','text':c['text']} for c in chars
            if c['text'].strip() and any(c['x0']+1.5<e['x0']<c['x1']-1.5 and
               e['top']+1<c['top'] and e['bottom']-1>c['bottom'] for e in vertical)]


class BorderIndex(unittest.TestCase):
    def test_empty_and_whitespace(self):
        self.assertEqual(border_crossings([],[]),[])
        self.assertEqual(border_crossings([{'text':' '}],[{'orientation':'h'}]),[])

    def test_strict_boundaries_and_duplicate_edges(self):
        c={'text':'碳','x0':10.,'x1':20.,'top':20.,'bottom':30.}
        for x in [11.5,11.5000001,18.4999999,18.5,15.]:
            for top in [19.,18.9999999,21.]:
                for bottom in [31.,31.0000001,29.]:
                    e={'orientation':'v','x0':x,'top':top,'bottom':bottom}
                    self.assertEqual(border_crossings([c],[e,e]),exhaustive([c],[e,e]))

    def test_narrow_glyph_negative_positions_and_order(self):
        chars=[{'text':str(w),'x0':-8.,'x1':-8.+w,'top':5.,'bottom':10.} for w in [-2,0,1,3,4,10]]
        edges=[{'orientation':'v','x0':x,'top':0.,'bottom':20.} for x in [-7.,-6.,0.]]
        self.assertEqual(border_crossings(chars,edges),exhaustive(chars,edges))

    def test_randomized_equivalence(self):
        r=random.Random(20261117)
        for _ in range(120):
            chars=[];edges=[]
            for i in range(80):
                x=r.uniform(-10,100);y=r.uniform(-10,100)
                chars.append({'text':' ' if i%17==0 else str(i),'x0':x,'x1':x+r.uniform(0,15),'top':y,'bottom':y+r.uniform(3,12)})
            for _ in range(120):
                y=r.uniform(-10,100)
                edges.append({'orientation':r.choice(['h','v','v']),'x0':r.uniform(-10,110),'top':y,'bottom':y+r.uniform(0,100)})
            self.assertEqual(border_crossings(chars,edges),exhaustive(chars,edges))

    def test_real_overlap_still_found(self):
        chars=[{'text':'R','x0':10,'x1':20,'top':20,'bottom':30}]
        edges=[{'orientation':'v','x0':15,'top':5,'bottom':35}]
        self.assertEqual(border_crossings(chars,edges),[{'kind':'table_border_crosses_text','text':'R'}])


if __name__=='__main__':unittest.main()
