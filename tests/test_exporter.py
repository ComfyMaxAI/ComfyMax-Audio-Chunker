import copy,json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
from comfymax_audio_chunker.editor.exporter import export_project,validate_scenes,verify_export,ExportValidationError
from comfymax_audio_chunker.editor.markers import initial_state,create_scenes,set_interval_type
from comfymax_audio_chunker.editor.project import digest


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name); self.project=self.root/'project'; self.project.mkdir()
        self.parent=self.root/'exports'; self.parent.mkdir(); rate=8000; frames=32000
        x=np.linspace(-1.2,1.2,frames,dtype=np.float32)
        self.mix=np.column_stack((x,-x)); self.vocals=np.column_stack((x*1.3,x*.1))
        assets={}
        for key,audio in (('mix',self.mix),('vocals',self.vocals)):
            p=self.project/f'{key}.wav'; sf.write(p,audio,rate,subtype='FLOAT'); assets[key]={'path':p.name,'sha256':digest(p)}
        self.data=dict(title='Test song',timeline={'sample_rate':rate,'frames':frames},assets=assets,
                       chunk_boundaries=[10001,20003])
        state=initial_state(self.data); state=set_interval_type(state,0,'Instrumental',frames)
        state=set_interval_type(state,1,'Vocal',frames); state=set_interval_type(state,2,'Instrumental',frames)
        self.data['marker_editor']=create_scenes(state,frames)
    def tearDown(self): self.temp.cleanup()

    def test_exact_mixed_sources_manifest_and_reconstruction(self):
        before=copy.deepcopy(self.data); result=export_project(self.project,self.data,self.parent)
        folder=Path(result['folder']); manifest=json.loads((folder/'scenes.json').read_text())
        self.assertEqual(self.data,before); self.assertEqual(manifest['format'],'comfymax-scenes'); self.assertEqual(manifest['version'],1)
        self.assertEqual(manifest['sample_rate'],8000); self.assertEqual(manifest['channels'],2)
        self.assertEqual([r['type'] for r in manifest['scenes']],['instrumental','vocal','instrumental'])
        self.assertEqual([r['audio_source'] for r in manifest['scenes']],['vocals','vocals','vocals'])
        decoded=[]
        for i,row in enumerate(manifest['scenes'],1):
            self.assertEqual(row['audio_file'],f'scene_{i:03d}.wav')
            wave,rate=sf.read(folder/row['audio_file'],dtype='float32',always_2d=True); decoded.append(wave)
            self.assertEqual(len(wave),row['frames']); self.assertEqual(len(wave)/rate,row['duration'])
        reconstructed=np.concatenate(decoded); expected=self.vocals
        np.testing.assert_array_equal(reconstructed,expected); self.assertEqual(len(reconstructed),32000)
        self.assertGreater(float(np.max(reconstructed)),1) # Float export preserves peaks without clipping.
        self.assertEqual(len(list(folder.iterdir())),4)

    def test_portable_folder_and_never_overwrite_previous_export(self):
        first=export_project(self.project,self.data,self.parent); second=export_project(self.project,self.data,self.parent)
        self.assertNotEqual(first['folder'],second['folder'])
        moved=self.root/'moved'; shutil.move(first['folder'],moved)
        manifest=json.loads((moved/'scenes.json').read_text())
        for row in manifest['scenes']:
            self.assertFalse(Path(row['audio_file']).is_absolute()); self.assertTrue((moved/row['audio_file']).is_file())

    def test_missing_stale_and_unassigned_scenes_block_export(self):
        variants=[]
        missing=copy.deepcopy(self.data); missing['marker_editor']['scenes']=None; variants.append(missing)
        stale=copy.deepcopy(self.data); stale['marker_editor']['interval_types'][0]['type']='Vocal'; variants.append(stale)
        untyped=copy.deepcopy(self.data); untyped['marker_editor']['scenes']['types'][1]=None; variants.append(untyped)
        for data in variants:
            with self.assertRaises(ExportValidationError): export_project(self.project,data,self.parent)
        self.assertEqual(list(self.parent.iterdir()),[])

    def test_validation_identifies_scene_and_fifteen_second_limit(self):
        data=copy.deepcopy(self.data); data['timeline']['sample_rate']=1000
        data['marker_editor']['scenes']['boundaries']=[0,1000,20003,32000]
        with self.assertRaises(ExportValidationError) as caught: validate_scenes(data)
        self.assertTrue(any(n==2 and '15 seconds' in message for n,message in caught.exception.issues))
        exact=copy.deepcopy(data); exact['timeline']['frames']=30000; exact['chunk_boundaries']=[15000]
        exact.pop('marker_editor'); exact['marker_editor']=create_scenes(initial_state(exact),30000)
        self.assertEqual([r['duration'] for r in validate_scenes(exact)],[15,15])

    def test_bad_order_and_coverage_rejected(self):
        for bounds in ([1,10001,20003,32000],[0,10001,20003,31999],[0,20003,10001,32000],[0,10001,10001,32000],[0,float('nan'),20003,32000]):
            data=copy.deepcopy(self.data); data['marker_editor']['scenes']['boundaries']=bounds
            with self.assertRaises(ExportValidationError): validate_scenes(data)

    def test_missing_misaligned_or_changed_proxy_rejected(self):
        data=copy.deepcopy(self.data); data['assets'].pop('vocals')
        with self.assertRaisesRegex(ExportValidationError,'vocal proxy is missing'): export_project(self.project,data,self.parent)
        path=self.project/'vocals.wav'; sf.write(path,self.vocals,16000,subtype='FLOAT')
        with self.assertRaisesRegex(ExportValidationError,'sample rate or frame count'): export_project(self.project,self.data,self.parent)
        sf.write(path,np.roll(self.vocals,100,axis=0),8000,subtype='FLOAT')
        with self.assertRaisesRegex(ExportValidationError,'changed since import'): export_project(self.project,self.data,self.parent)
        self.assertEqual(list(self.parent.iterdir()),[])

    def test_channel_mismatch_rejected(self):
        path=self.project/'vocals.wav'; sf.write(path,self.vocals[:,0],8000,subtype='FLOAT')
        self.data['assets']['vocals']['sha256']=digest(path)
        with self.assertRaisesRegex(ExportValidationError,'channel layouts'): export_project(self.project,self.data,self.parent)

    def test_failed_verification_cleans_only_own_partial_folder(self):
        sentinel=self.parent/'keep.txt'; sentinel.write_text('existing work')
        with patch('comfymax_audio_chunker.editor.exporter.verify_export',side_effect=RuntimeError('verification failed')):
            with self.assertRaisesRegex(RuntimeError,'verification failed'): export_project(self.project,self.data,self.parent)
        self.assertEqual(list(self.parent.iterdir()),[sentinel]); self.assertEqual(sentinel.read_text(),'existing work')

    def test_actual_wrong_duration_is_detected(self):
        result=export_project(self.project,self.data,self.parent); folder=Path(result['folder'])
        sf.write(folder/'scene_002.wav',self.vocals[:10],8000,subtype='FLOAT')
        paths={'vocals':self.project/'vocals.wav','full_mix':self.project/'mix.wav'}
        with self.assertRaisesRegex(RuntimeError,'Scene 2'): verify_export(folder,result['manifest'],paths)

    def test_nonfinite_source_samples_rejected_without_completed_output(self):
        bad=self.vocals.copy(); bad[15000,0]=np.nan; path=self.project/'vocals.wav'
        sf.write(path,bad,8000,subtype='FLOAT'); self.data['assets']['vocals']['sha256']=digest(path)
        with self.assertRaisesRegex(RuntimeError,'Scene 2'): export_project(self.project,self.data,self.parent)
        self.assertEqual(list(self.parent.iterdir()),[])
