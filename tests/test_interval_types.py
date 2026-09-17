import copy
import unittest
from unittest.mock import patch
import numpy as np
from PySide6.QtTest import QTest
from comfymax_audio_chunker.editor.markers import *
from comfymax_audio_chunker.editor.interval_types import VocalActivity
from comfymax_audio_chunker.editor.project import Document,atomic_json
import test_markers as fixtures


class IntervalTypeModelTests(unittest.TestCase):
    def state(self):
        return initial_state({'timeline':{'frames':1000},'chunk_boundaries':[300,600]})

    def test_type_changes_no_boundaries_and_snapshot_requires_create(self):
        state=create_scenes(self.state(),1000); changed=set_interval_type(state,1,'Instrumental',1000)
        self.assertEqual(state['markers'],changed['markers']); self.assertEqual(state['scenes'],changed['scenes'])
        self.assertFalse(scenes_current(changed,1000))
        created=create_scenes(changed,1000)
        self.assertEqual([r['type'] for r in created_scenes(created,100)],['Vocal','Instrumental','Vocal'])
        self.assertEqual([r['duration'] for r in created_scenes(state,100)],[r['duration'] for r in created_scenes(created,100)])

    def test_manual_split_move_merge_and_reopen_do_not_reclassify(self):
        state=set_interval_type(self.state(),0,'Instrumental',1000)
        split=add_marker(state,100,1000,lambda a,b:'Vocal')
        self.assertEqual([r['type'] for r in split['interval_types'][:2]],['Instrumental','Instrumental'])
        moved=move_marker(split,100,200,1000,lambda a,b:'Vocal')
        self.assertEqual([r['source'] for r in moved['interval_types'][:2]],['manual','manual'])
        merged=delete_marker(moved,200,1000,lambda a,b:'Vocal')
        reopened=initial_state({'timeline':{'frames':1000},'marker_editor':merged},lambda a,b:'Vocal')
        self.assertEqual(merged,reopened)
        self.assertEqual(merged['interval_types'][0]['type'],'Instrumental')

    def test_conflicting_merge_largest_manual_overlap_and_final_boundary(self):
        state=set_interval_type(self.state(),0,'Instrumental',1000)
        state=set_interval_type(state,1,'Vocal',1000)
        merged=delete_marker(state,300,1000)
        self.assertEqual(merged['interval_types'][0]['type'],'Instrumental') # tie: earlier interval
        for index,value in ((3,'Vocal'),(0,'Speech')):
            with self.assertRaises(ValueError): set_interval_type(state,index,value,1000)
        bad=copy.deepcopy(state); bad['interval_types'][0]['end_frame']=301
        with self.assertRaises(ValueError): validate_marker_state(bad,1000)

    def test_stem_activity_and_missing_stem(self):
        rate=1000; mix=np.ones((4000,2),dtype=np.float32)*.1; vocal=np.zeros_like(mix)
        vocal[1500:2500]=.1; vocal[:,1]*=-1 # anti-phase must not cancel
        classify=VocalActivity({'mix':mix,'vocals':vocal},rate)
        self.assertEqual(classify(0,1000),'Instrumental'); self.assertEqual(classify(1500,2500),'Vocal')
        fallback=VocalActivity({'mix':mix},rate); self.assertFalse(fallback.available)
        self.assertEqual(fallback(0,1000),'Vocal')

    def test_migrate_untyped_scene_without_changing_its_boundaries(self):
        old={'markers':[500],'scenes':{'boundaries':[0,500,1000]}}
        state=initial_state({'timeline':{'frames':1000},'marker_editor':old},lambda a,b:'Instrumental' if a==0 else 'Vocal')
        self.assertEqual(state['scenes']['boundaries'],old['scenes']['boundaries'])
        self.assertEqual(state['scenes']['types'],['Instrumental','Vocal']); self.assertTrue(scenes_current(state,1000))


class IntervalTypeGuiTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.MarkerGuiTests.setUpClass.__func__)
    setUp=fixtures.MarkerGuiTests.setUp
    tearDown=fixtures.MarkerGuiTests.tearDown

    def test_dropdown_no_audio_change_undo_autosave_reopen_regenerate(self):
        w=self.w; w.seek(.04); w.add_at_playhead(); w.create_scene_snapshot()
        positions=list(w.state['markers']); previous=copy.deepcopy(w.state)
        self.assertEqual(w.marker_table.horizontalHeaderItem(3).text(),'Type')
        self.assertIsNone(w.marker_table.cellWidget(w.marker_table.rowCount()-1,3))
        combo=w.marker_table.cellWidget(0,3)
        with patch.object(w.transport,'halt',side_effect=AssertionError('must not affect audio')),patch.object(w.transport,'seek',side_effect=AssertionError('must not seek')):
            combo.setCurrentText('Vocal'); combo.textActivated.emit('Vocal')
        self.assertEqual(w.state['markers'],positions); self.assertEqual(w.state['interval_types'][0]['source'],'manual')
        self.assertEqual(w.state['scenes'],previous['scenes'])
        w.history.undo(); self.assertEqual(w.state,previous); w.history.redo()
        w.create_scene_snapshot(); self.assertEqual(w.scene_table.item(0,4).text(),'Vocal')
        QTest.qWait(1400); self.assertFalse(w.dirty)
        expected=copy.deepcopy(w.state); w.doc.close(); w.doc=Document.open(w.doc.root)
        self.assertEqual(w.doc.data['marker_editor'],expected)
        w.create_scene_snapshot(); self.assertEqual(w.state,expected)
        self.assertEqual(w.doc.phrases,self.evidence)

    def test_invalid_typed_checkpoint_falls_back(self):
        w=self.w; w.change_interval_type(0,'Instrumental'); w.save(True)
        state=copy.deepcopy(w.doc.data); state['revision']+=1; state['marker_editor']['interval_types'][0]['type']='invalid'
        atomic_json(w.doc.root/'recovery/pending.json',state)
        w.doc.close(); w.doc=Document.open(w.doc.root)
        self.assertFalse(w.doc.recovered); self.assertEqual(w.doc.data['marker_editor']['interval_types'][0]['type'],'Instrumental')
