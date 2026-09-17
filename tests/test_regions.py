import unittest
import numpy as np
from comfymax_audio_chunker.regions import activity, merge_intervals, partition, phrases


class RegionsTest(unittest.TestCase):
    def test_mixed_stem_lists_and_whisper_tuples(self):
        self.assertEqual(merge_intervals([[1.,3.],(2.,4.),[6.,8.],(6.,7.)],10),[[1.,4.],[6.,8.]])

    def test_silence_is_one_instrumental_region(self):
        x = np.zeros((1000,2),dtype=np.float32)
        active,_ = activity(x,x,100)
        self.assertEqual(active, [])
        self.assertEqual([(r['start'],r['end'],r['kind']) for r in partition(active,10)],[(0,10,'instrumental')])

    def test_intro_vocal_outro_and_antiphase(self):
        mix = np.ones((1000,2),dtype=np.float32)*.2
        v = np.zeros_like(mix)
        v[200:600,0]=.1
        v[200:600,1]=-.1
        active,_=activity(v,mix,100)
        self.assertEqual(len(active),1)
        self.assertAlmostEqual(active[0][0],1.88)
        self.assertAlmostEqual(active[0][1],6.12)
        regions=partition(active,10)
        self.assertEqual([r['kind'] for r in regions],['instrumental','vocal','instrumental'])
        self.assertAlmostEqual(sum(r['duration'] for r in regions),10)

    def test_interval_clamping_overlap_and_contiguity(self):
        intervals=merge_intervals([(8,12),(-1,2),(1,4),(4,6)],10)
        self.assertEqual(intervals,[[0,6],[8,10]])
        regions=partition(intervals,10)
        for a,b in zip(regions,regions[1:]):
            self.assertEqual(a['end'],b['start'])

    def test_subframe_tail_covered(self):
        x=np.ones((103,2),dtype=np.float32)*.1
        active,_=activity(x,x,100)
        self.assertEqual(partition(active,1.03)[-1]['end'],1.03)

    def test_phrases_pause_punctuation_suspect(self):
        def w(i,a,b,text,s=False):
            return dict(id=i,start=a,end=b,word=text,suspect=s)
        result=phrases([w(0,1,2,' Hello'),w(1,2,3,' world.'),w(2,3.1,4,' Again'),
                        w(3,5,6,' sing'),w(4,6,7,' hallucination',True)])
        self.assertEqual([p['text'] for p in result],['Hello world.','Again','sing'])

if __name__ == '__main__':
    unittest.main()
