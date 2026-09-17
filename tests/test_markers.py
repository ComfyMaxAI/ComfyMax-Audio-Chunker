import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from comfymax_audio_chunker.editor.markers import *
from comfymax_audio_chunker.editor.marker_app import MarkerEditor
from comfymax_audio_chunker.editor.project import Document,atomic_json
from comfymax_audio_chunker.editor.audio import Transport,load_audio
import test_editor as fixtures


class MarkerModelTests(unittest.TestCase):
    def test_migration_preserves_data_without_creating_scenes(self):
        data={'timeline':{'frames':1000},'chunk_boundaries':[100,400],'phrases':[{'text':'ignored'}]}
        before=copy.deepcopy(data); state=initial_state(data)
        self.assertEqual(data,before); self.assertEqual(state['markers'],[100,400]); self.assertIsNone(state['scenes'])
        self.assertEqual(len(state['interval_types']),3)

    def test_snapshot_changes_only_on_create_and_full_coverage(self):
        state={'markers':[100,400],'scenes':None}; state=create_scenes(state,1000)
        self.assertEqual([r['end_frame']-r['start_frame'] for r in created_scenes(state,100)],[100,300,600])
        moved=move_marker(state,100,200,1000)
        self.assertFalse(scenes_current(moved,1000)); self.assertEqual(moved['scenes'],state['scenes'])
        self.assertEqual(create_scenes(moved,1000)['scenes']['boundaries'],[0,200,400,1000])

    def test_invalid_markers_fixed_ends_and_overlimit(self):
        state={'markers':[],'scenes':None}
        for frame in (0,2000,-1,2001,1.2,True):
            with self.assertRaises(ValueError): add_marker(state,frame,2000)
        with self.assertRaises(ValueError): delete_marker(state,0,2000)
        self.assertTrue(created_scenes(create_scenes(state,2000),100)[0]['over_limit'])

    def test_switch_has_no_restart_or_seek(self):
        t=Transport({'mix':np.zeros((100,2),np.float32),'vocals':np.ones((100,2),np.float32)},100)
        sentinel=object(); t.stream=sentinel; t.active=True; t.cursor.frame=37
        with patch.object(t,'halt',side_effect=AssertionError('must not stop')),patch.object(t,'resume',side_effect=AssertionError('must not restart')):
            t.switch('vocals')
        self.assertIs(t.stream,sentinel); self.assertEqual(t.cursor.frame,37); self.assertTrue(t.active)
        t.active=False; t.stream=None; t.parked=23; t.switch('mix'); self.assertEqual(t.parked,23)


class MarkerGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]); cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        doc=Document.create(fixtures.ProjectTests().source(self.root),self.root/'project')
        self.evidence=copy.deepcopy(doc.phrases); self.w=MarkerEditor(); self.w.loaded((doc,*load_audio(doc)))
        self.w.show(); self.w.activateWindow(); QTest.qWait(20)
    def tearDown(self):
        self.w.dirty=False; self.w.doc.recovered=False; self.w.close(); self.w.deleteLater(); self.app.processEvents(); self.temp.cleanup()
    def test_markers_create_stale_recreate_without_lyric_approval(self):
        w=self.w; self.assertTrue(w.create_button.isEnabled()); self.assertIsNone(w.state['scenes'])
        w.seek(.025); w.add_at_playhead(); self.assertEqual(w.state['markers'],[1200]); self.assertEqual(w.scene_table.rowCount(),0)
        w.create_button.click(); self.assertEqual(w.scene_table.rowCount(),2)
        w.drag_marker(1200,2400); self.assertIn('Markers have changed',w.scene_status.text())
        self.assertEqual(w.state['scenes']['boundaries'],[0,1200,4800]); self.assertFalse(w.scene_play.isEnabled())
        w.create_scene_snapshot(); self.assertEqual(w.state['scenes']['boundaries'],[0,2400,4800])
        self.assertEqual(w.doc.phrases,self.evidence)
        w.history.undo(); self.assertFalse(scenes_current(w.state,4800)); w.history.undo(); self.assertTrue(scenes_current(w.state,4800))
    def test_marker_controls_audition_and_fixed_end(self):
        w=self.w; w.seek(.05); w.add_button.click(); w.marker_time.setValue(.06); w.move_button.click()
        self.assertEqual(w.selected_marker,2880)
        w.before.setValue(.01); w.after.setValue(.02)
        with patch.object(w.transport,'play') as play:
            w.audition_button.click(); play.assert_called_once_with(2400,3840,loop=False)
        w.delete_button.click(); self.assertEqual(w.state['markers'],[])
        w.select_marker(0); self.assertFalse(w.delete_button.isEnabled()); self.assertFalse(w.move_button.isEnabled())
    def test_autosave_recovery_and_readonly_aid(self):
        w=self.w; w.seek(.04); w.add_at_playhead(); w.create_scene_snapshot()
        w.transcript_toggle.setChecked(True); self.assertEqual(w.tabs.count(),3)
        QTest.qWait(1400); self.assertFalse(w.dirty)
        expected=copy.deepcopy(w.state); w.doc.close(); w.doc=Document.open(w.doc.root)
        self.assertEqual(w.doc.data['marker_editor'],expected); self.assertEqual(w.doc.phrases,self.evidence)
        pending=copy.deepcopy(w.doc.data); pending['revision']+=1; pending['marker_editor']=add_marker(expected,3500,4800)
        atomic_json(w.doc.root/'recovery/pending.json',pending); w.doc.close(); w.doc=Document.open(w.doc.root)
        self.assertTrue(w.doc.recovered); self.assertEqual(w.doc.data['marker_editor']['markers'],[1920,3500])
    def test_placing_marker_during_playback_does_not_stop_stream(self):
        w=self.w
        with patch.object(w.transport,'position',return_value=2000),patch.object(w.transport,'halt',side_effect=AssertionError('marker editing must not stop playback')):
            w.add_at_playhead()
        self.assertEqual(w.state['markers'],[2000]); self.assertIsNone(w.state['scenes'])
