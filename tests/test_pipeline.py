"""Real FFmpeg I/O with stubbed neural inference; no downloads in unit tests."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import soundfile as sf
from comfymax_audio_chunker import cli


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class PipelineTest(unittest.TestCase):
    def test_separation_only_skips_transcription(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); song=root/'song.wav'; sf.write(song,np.zeros((48000,2),dtype=np.float32),48000)
            before=cli.sha256(song)
            args=argparse.Namespace(song=song,output=root/'run',device='cpu',offline=True,separate_only=True,
                floor_db=-48.,relative_db=-30.,ratio_db=-22.,model='small',language=None)
            def separate(mix,sr,out,*unused):
                sf.write(out/'vocals.wav',mix,sr,subtype='FLOAT'); return mix,'cpu'
            with patch.object(cli,'separate',side_effect=separate),patch.object(cli,'transcribe',side_effect=AssertionError('No Whisper required')):
                self.assertEqual(cli.run(args),0)
            data=json.loads((args.output/'analysis.json').read_text(encoding='utf-8'))
            self.assertEqual(data['segments'],[]); self.assertEqual(data['regions'],[])
            self.assertIsNone(data['processing']['whisper_model']); self.assertEqual(cli.sha256(song),before)

    def test_vocal_words_from_model_through_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            song=root/'vocals.wav'
            sf.write(song,np.ones((48000,2),dtype=np.float32)*.1,48000)
            args=argparse.Namespace(song=song,output=root/'result',device='cpu',offline=True,
                    floor_db=-48.,relative_db=-30.,ratio_db=-22.,model='small',language='en')
            word=SimpleNamespace(start=.2,end=.8,word=' Hello',probability=.95)
            segment=SimpleNamespace(id=0,start=.2,end=.8,text='Hello',no_speech_prob=.95,
                                    avg_logprob=-.1,compression_ratio=1.,words=[word])
            model=SimpleNamespace(transcribe=lambda *a,**kw: (iter([segment]),SimpleNamespace(language='en',language_probability=1.)))
            def separate(mix,sr,out,*unused):
                sf.write(out/'vocals.wav',mix,sr,subtype='FLOAT')
                return mix,'cpu'
            with patch.object(cli,'separate',side_effect=separate), patch('faster_whisper.WhisperModel',return_value=model):
                self.assertEqual(cli.run(args),0)
            data=json.loads((args.output/'analysis.json').read_text(encoding='utf-8'))
            self.assertFalse(data['segments'][0]['suspect'])
            self.assertFalse(data['words'][0]['suspect'])
            self.assertEqual(data['phrases'][0]['text'],'Hello')
            self.assertEqual(data['regions'][0]['kind'],'vocal')

    def test_original_unchanged_json_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            song=root/'original mix.wav'
            sf.write(song,np.zeros((48000,2),dtype=np.float32),48000)
            original=cli.sha256(song)
            args=argparse.Namespace(song=song,output=root/'result',device='cpu',offline=True,
                    floor_db=-48.,relative_db=-30.,ratio_db=-22.,model='small',language='en')
            def separate(mix,sr,out,*unused):
                sf.write(out/'vocals.wav',mix,sr,subtype='FLOAT')
                return mix,'cpu'
            with patch.object(cli,'separate',side_effect=separate), patch.object(cli,'transcribe',return_value=([],[],{'language':'en','probability':1.})):
                self.assertEqual(cli.run(args),0)
                with self.assertRaises(FileExistsError):
                    cli.run(args)
            data=json.loads((args.output/'analysis.json').read_text(encoding='utf-8'))
            self.assertEqual(cli.sha256(song),original)
            self.assertTrue(data['source']['unchanged'])
            self.assertEqual(data['timeline']['analysis_frames'],44100)
            self.assertEqual(data['regions'][0]['end'],1.)
            self.assertEqual(data['regions'][0]['kind'],'instrumental')
            self.assertTrue((args.output/'analysis.txt').exists())
            self.assertFalse(list(args.output.glob('scene_*')))

    def test_failure_keeps_original_and_no_success_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            song=root/'song.wav'
            sf.write(song,np.zeros((800,2),dtype=np.float32),8000)
            args=argparse.Namespace(song=song,output=root/'failed',device='cpu',offline=True)
            with patch.object(cli,'separate',side_effect=RuntimeError('test model failure')):
                with self.assertRaisesRegex(RuntimeError,'test model failure'):
                    cli.run(args)
            failure=json.loads((args.output/'failure.json').read_text())
            self.assertTrue(failure['source_unchanged'])
            self.assertFalse((args.output/'analysis.json').exists())
