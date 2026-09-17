import copy
import unittest
from comfymax_audio_chunker.editor.scenes import propose,scene_rows,validate_cuts
from comfymax_audio_chunker.editor.lyrics_workflow import review_fingerprint


def song(duration,spans=(),regions=()):
    data={'timeline':{'sample_rate':1000,'frames':round(duration*1000)},'phrases':[
        dict(id=str(i),start=a,end=b,original_text='Original',corrected_text=text)
        for i,(a,b,text) in enumerate(spans)],'chunk_boundaries':[]}
    analysis={'regions':[dict(start=a,end=b,kind=kind) for a,b,kind in regions]}
    return data,analysis


class SceneTests(unittest.TestCase):
    def generate(self,data,analysis):
        for p in data['phrases']: p['review_status']='reviewed'
        data['lyrics_review']={'fingerprint':review_fingerprint(data)}
        before=copy.deepcopy((data,analysis)); cuts=propose(data,analysis)
        self.assertEqual((data,analysis),before)
        data=copy.deepcopy(data); data['chunk_boundaries']=cuts
        rows=scene_rows(data,analysis)
        self.assertEqual(sum(r['end_frame']-r['start_frame'] for r in rows),data['timeline']['frames'])
        self.assertTrue(all(r['duration']<=15 for r in rows))
        return cuts,rows

    def test_instrumental_evenly_distributed_no_tail(self):
        cuts,rows=self.generate(*song(23.68))
        self.assertEqual(len(rows),4)
        self.assertTrue(all(abs(r['duration']-5.92)<.001 for r in rows))

    def test_natural_phrases_and_corrected_blank(self):
        cuts,rows=self.generate(*song(32,[(0,2,''),(6,14,'Corrected words'),(14,26,'Next phrase')],[(6,26,'vocal')]))
        self.assertIn(6000,cuts); self.assertIn(14000,cuts); self.assertIn(26000,cuts)
        self.assertEqual(rows[0]['lyrics'],'Instrumental')
        self.assertEqual(rows[1]['lyrics'],'Corrected words')
        self.assertFalse(any('inside' in w for r in rows for w in r['warnings']))

    def test_overlong_phrase_cannot_be_split_automatically(self):
        with self.assertRaisesRegex(ValueError,'split it manually'):
            self.generate(*song(31,[(0,31,'One long phrase')],[(0,31,'vocal')]))

    def test_detector_dropout_does_not_cut_phrase(self):
        cuts,rows=self.generate(*song(12,[(0,12,'One phrase')],[(0,6,'vocal'),(6.1,12,'vocal')]))
        self.assertEqual(cuts,[])

    def test_manual_over_limit_and_invalid_cuts(self):
        data,analysis=song(40); data['chunk_boundaries']=[20000]
        self.assertTrue(all('OVER 15 SECONDS' in r['warnings'] for r in scene_rows(data,analysis)))
        for cuts in ([0],[40000],[20000,10000],[10000,10000],[1.1],[True]):
            with self.assertRaises(ValueError): validate_cuts(cuts,40000)

    def test_vocals_without_lyrics_and_short_song(self):
        cuts,rows=self.generate(*song(21,[],[(0,21,'vocal')]))
        self.assertTrue(all(r['lyrics']=='Vocal — no transcript' for r in rows))
        cuts,rows=self.generate(*song(2))
        self.assertEqual(cuts,[]); self.assertEqual(rows[0]['duration'],2)

    def test_region_roundoff_does_not_create_false_vocals(self):
        data,analysis=song(20,[],[(0,10.000000000000002,'vocal')])
        data['chunk_boundaries']=[10000]
        self.assertEqual(scene_rows(data,analysis)[1]['lyrics'],'Instrumental')

    def test_exact_fifteen_second_reviewed_phrase_stays_whole(self):
        cuts,rows=self.generate(*song(30,[(3,18,'A complete reviewed phrase')],[(0,22,'vocal')]))
        self.assertIn(3000,cuts); self.assertIn(18000,cuts)
        self.assertFalse(any(3000<c<18000 for c in cuts))

    def test_adjacent_short_reviewed_phrases_can_combine(self):
        cuts,rows=self.generate(*song(10,[(0,4,'First'),(4,10,'Second')],[(0,10,'vocal')]))
        self.assertEqual(cuts,[]); self.assertEqual(rows[0]['lyrics'],'First\nSecond')
