import copy
import unittest
from unittest.mock import patch
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox
import test_corrections as fixtures
from comfymax_audio_chunker.editor.lyrics_workflow import split_state,review_complete,review_fingerprint,validate_history
from comfymax_audio_chunker.editor.scenes import propose,phrase_spans
from comfymax_audio_chunker.editor.project import Document,atomic_json


class PhraseWorkflowTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.CorrectionTests.setUpClass.__func__)
    setUp=fixtures.CorrectionTests.setUp
    tearDown=fixtures.CorrectionTests.tearDown

    def split(self):
        w=self.window; w.corrected.setPlainText('First 😀 line\nSecond line')
        cursor=w.corrected.textCursor(); cursor.setPosition(len('First 😀 line'.encode('utf-16-le'))//2)
        w.corrected.setTextCursor(cursor); w.split_button.click(); w.split_time.setValue(.045)
        self.assertTrue(w.split_confirm.isEnabled()); w.split_confirm.click()

    def certify(self):
        w=self.window
        for i,p in enumerate(w.doc.phrases):
            w.table.selectRow(i)
            if p['end']<=p['start']: w.corrected.setPlainText('')
            w.mark_reviewed()
        w.complete_button.click()

    def test_unicode_split_lineage_undo_redo_and_independent_text(self):
        w=self.window; original=copy.deepcopy(w.doc.phrases[0]); self.split()
        self.assertEqual(len(w.doc.phrases),3)
        a,b=w.doc.phrases[:2]
        self.assertEqual(a['corrected_text'],'First 😀 line'); self.assertEqual(b['corrected_text'],'\nSecond line')
        self.assertEqual((a['start'],a['end'],b['start'],b['end']),(.01,.045,.045,.09))
        self.assertTrue(all(p['review_status']=='unreviewed' for p in (a,b)))
        self.assertEqual(a['source_word_ids'],original['source_word_ids']); self.assertEqual(b['original_text'],original['original_text'])
        validate_history(w.doc.data)
        w.corrected.setPlainText('Independent first half'); w.mark_reviewed()
        self.assertEqual(b['corrected_text'],'\nSecond line'); self.assertEqual(b['review_status'],'unreviewed')
        w.undo_edit(); w.undo_edit(); w.undo_edit()
        self.assertEqual(len(w.doc.phrases),2); self.assertEqual(w.doc.phrases[0]['corrected_text'],'First 😀 line\nSecond line')
        w.redo_edit(); self.assertEqual(len(w.doc.phrases),3)
        w.corrected.setPlainText('edited'); w.restore_original()
        self.assertEqual(w.doc.phrases[0]['corrected_text'],'First 😀 line')

    def test_review_gate_changes_and_undo(self):
        w=self.window
        self.assertFalse(w.generate_button.isEnabled())
        with self.assertRaises(ValueError): propose(w.doc.data,w.doc.analysis)
        with patch.object(QMessageBox,'warning') as warning:
            w.complete_button.click(); warning.assert_called_once()
        self.split(); self.certify(); self.assertTrue(review_complete(w.doc.data)); self.assertTrue(w.generate_button.isEnabled())
        cuts=propose(w.doc.data,w.doc.analysis)
        self.assertFalse(any(a<c<b for a,b,p in phrase_spans(w.doc.data) for c in cuts))
        w.table.selectRow(0); w.corrected.setPlainText('Changed again')
        self.assertFalse(review_complete(w.doc.data)); self.assertFalse(w.generate_button.isEnabled())
        w.undo_edit(); self.assertTrue(review_complete(w.doc.data)); self.assertTrue(w.generate_button.isEnabled())
        w.undo_edit(); self.assertFalse(review_complete(w.doc.data))
        w.redo_edit(); self.assertTrue(review_complete(w.doc.data))

    def test_autosave_reopen_nested_split_and_history_validation(self):
        w=self.window; self.split(); w.table.selectRow(0)
        cursor=w.corrected.textCursor(); cursor.setPosition(5); w.corrected.setTextCursor(cursor)
        w.begin_split(); w.split_time.setValue(.025); w.confirm_split()
        self.assertEqual(len(w.doc.phrases),4); self.assertEqual(len(w.doc.data['phrase_history']),2)
        QTest.qWait(1400); self.assertFalse(w.dirty)
        expected=copy.deepcopy(w.doc.data); w.doc.close(); w.doc=Document.open(w.doc.root)
        self.assertEqual(w.doc.phrases,expected['phrases']); self.assertEqual(w.doc.data['phrase_history'],expected['phrase_history'])
        bad=copy.deepcopy(w.doc.data); bad['phrases'][0]['original_text']='tampered'
        with self.assertRaises(ValueError): validate_history(bad)

    def test_invalid_text_or_time_never_splits(self):
        w=self.window; before=copy.deepcopy(w.doc.data); pid=w.doc.phrases[0]['id']
        for index,frame in [(0,2000),(5,0),(5,4800),(999,2000)]:
            with self.assertRaises(ValueError): split_state(w.doc.data,pid,index,frame)
        self.assertEqual(w.doc.data,before)

    def test_pending_recovery_keeps_split_lineage(self):
        w=self.window; self.split(); state=copy.deepcopy(w.doc.data); state['revision']+=1
        atomic_json(w.doc.root/'recovery/pending.json',state)
        w.doc.close(); w.doc=Document.open(w.doc.root)
        self.assertTrue(w.doc.recovered); self.assertEqual(len(w.doc.phrases),3)
        validate_history(w.doc.data)

    def test_duration_zero_and_over_limit_warning(self):
        w=self.window
        self.assertEqual(w.table.item(1,3).text(),'0.000 s')
        original=copy.deepcopy(w.doc.phrases[0])
        try:
            w.doc.phrases[0]['end']=16.01; w.refresh_phrase_table(); w.refresh_correction()
            self.assertEqual(w.table.item(0,3).text(),'16.000 s')
            self.assertIn('OVER 15 SECONDS',w.table.item(0,3).toolTip())
            self.assertIn('OVER 15 SECONDS',w.phrase_heading.text())
            self.assertFalse(review_complete(w.doc.data))
        finally:
            w.doc.phrases[0]=original; w.refresh_phrase_table()
