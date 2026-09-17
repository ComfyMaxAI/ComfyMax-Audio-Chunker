import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import soundfile as sf

try:
    from comfymax_audio_chunker.editor.audio import Cursor, Transport
    from comfymax_audio_chunker.editor.project import Document, digest, playable
    EDITOR = True
except ImportError:
    EDITOR = False


@unittest.skipUnless(EDITOR,'Install editor extras')
class AudioTests(unittest.TestCase):
    def test_end_sample_and_zero_tail(self):
        source=np.arange(40,dtype=np.float32).reshape(20,2)
        output=np.empty((12,2),dtype=np.float32)
        c=Cursor(3,10,3)
        self.assertEqual(c.render(source,output),7)
        np.testing.assert_array_equal(output[:7],source[3:10])
        np.testing.assert_array_equal(output[7:],0)
        self.assertEqual(c.frame,10)

    def test_loop_wrap_inside_callback(self):
        source=np.arange(12,dtype=np.float32).reshape(6,2)
        output=np.empty((11,2),dtype=np.float32)
        c=Cursor(1,4,2,True)
        c.render(source,output)
        np.testing.assert_array_equal(output,source[[2,3,1,2,3,1,2,3,1,2,3]])

    def test_stream_clock_not_wall_clock(self):
        t=Transport({'mix':np.zeros((1000,2),dtype=np.float32)},100)
        class Clock: time=12.25
        t.stream=Clock(); t.active=True
        t.anchors.append((12.,300,200,500,False,50))
        self.assertEqual(t.position(),325)
        t.stream.time=1000.
        self.assertEqual(t.position(),350) # Cannot run ahead of queued audio.

    def test_loop_clock(self):
        t=Transport({'mix':np.zeros((100,2),dtype=np.float32)},100)
        class Clock: time=1.07
        t.stream=Clock(); t.active=True
        t.anchors.append((1.,18,10,20,True,30))
        self.assertEqual(t.position(),15)


@unittest.skipUnless(EDITOR,'Install editor extras')
class ProjectTests(unittest.TestCase):
    def source(self,root):
        run=root/'run'; run.mkdir()
        audio=np.zeros((4800,2),dtype=np.float32)
        for name in ('analysis_mix','vocals'): sf.write(run/f'{name}.wav',audio,48000,subtype='FLOAT')
        d=dict(schema_version='1.0',stage=1,source={'path':'C:/songs/song.mp3','sha256_after':'original'},
            timeline={'analysis_frames':4800,'analysis_sample_rate':48000},
            artifacts={'analysis_mix':'analysis_mix.wav','vocals':'vocals.wav'},
            segments=[{'id':1,'start':.01,'end':.09,'text':'suspect words','suspect':True},
                      {'id':2,'start':.05,'end':.05,'text':'zero length'}],
            words=[{'id':0,'segment_id':1}],phrases=[],regions=[{'start':0,'end':.1,'kind':'instrumental'}])
        p=run/'analysis.json'; p.write_text(json.dumps(d),encoding='utf-8')
        return p

    def test_import_all_rows_snapshot_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=self.source(root)
            doc=Document.create(source,root/'Song.comfymax')
            self.assertEqual(len(doc.phrases),2)
            self.assertTrue(doc.phrases[0]['suspect'])
            self.assertFalse(playable(doc.phrases[1],doc.duration))
            self.assertEqual((doc.root/'source/analysis.json').read_bytes(),source.read_bytes())
            phrases=copy.deepcopy(doc.phrases)
            doc.data['settings']['before']=1.25; doc.save(); doc.close()
            reopened=Document.open(root/'Song.comfymax')
            self.assertEqual(reopened.phrases,phrases)
            self.assertEqual(reopened.data['settings']['before'],1.25)
            reopened.close()

    def test_lock_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=self.source(root)
            doc=Document.create(source,root/'Song.comfymax')
            with self.assertRaisesRegex(ValueError,'already open'): Document.open(doc.root)
            with self.assertRaisesRegex(ValueError,'never overwritten'): Document.create(source,doc.root)
            doc.close()

    def test_changed_proxy_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=self.source(root)
            doc=Document.create(source,root/'Song.comfymax'); doc.close()
            sf.write(root/'Song.comfymax/audio/vocals.wav',np.ones((4800,2),dtype=np.float32)*.1,48000,subtype='FLOAT')
            with self.assertRaisesRegex(ValueError,'audio has changed'): Document.open(root/'Song.comfymax')

    def test_failed_save_preserves_primary_and_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); doc=Document.create(self.source(root),root/'Song.comfymax')
            primary=digest(doc.root/'project.json')
            with patch('comfymax_audio_chunker.editor.project.os.replace',side_effect=OSError('disk full')):
                with self.assertRaises(OSError): doc.save()
            self.assertEqual(digest(doc.root/'project.json'),primary)
            doc.close()
            (root/'Song.comfymax/project.json').write_text('{bad')
            recovered=Document.open(root/'Song.comfymax')
            self.assertTrue(recovered.recovered)
            recovered.save(); recovered.close()

    def test_bad_timeline_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=self.source(root)
            sf.write(source.parent/'vocals.wav',np.zeros((100,2)),48000)
            with self.assertRaisesRegex(ValueError,'match the Stage 1'): Document.create(source,root/'bad.comfymax')
            self.assertFalse((root/'bad.comfymax').exists())
