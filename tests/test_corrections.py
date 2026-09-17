"""Correction, keyboard, persistence and interrupted-save regression tests."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from comfymax_audio_chunker.editor.app import Editor
from comfymax_audio_chunker.editor.audio import load_audio
from comfymax_audio_chunker.editor.project import Document, digest, atomic_json
import test_editor as fixtures


class CorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.root=Path(self.temporary.name)
        self.source=fixtures.ProjectTests().source(self.root)
        doc=Document.create(self.source,self.root/'song.comfymax')
        self.rows=copy.deepcopy(doc.phrases)
        self.original=copy.deepcopy(doc.analysis)
        self.snapshot_hash=digest(doc.root/'source/analysis.json')
        self.window=Editor()
        arrays,peaks=load_audio(doc)
        self.window.loaded((doc,arrays,peaks))
        self.window.show(); self.window.activateWindow(); QTest.qWait(25)
        self.window.table.selectRow(0)

    def tearDown(self):
        self.window.autosave.stop()
        if self.window.doc:
            self.window.dirty=False; self.window.doc.recovered=False
        self.window.close(); self.window.deleteLater()
        self.app.processEvents()
        self.temporary.cleanup()

    def assert_originals(self):
        doc=self.window.doc
        for old,new in zip(self.rows,doc.phrases):
            for key in ('start','end','imported_start','imported_end','original_text','source_segment_ids','source_word_ids'):
                self.assertEqual(old[key],new[key])
        self.assertEqual(self.original,doc.analysis)
        self.assertEqual(digest(doc.root/'source/analysis.json'),self.snapshot_hash)

    def type_correction(self,text):
        self.window.corrected.setFocus(); self.window.corrected.selectAll()
        QTest.keyClicks(self.window.corrected,text)

    def test_typing_newlines_undo_redo_and_review(self):
        w=self.window; self.type_correction('Different word count')
        QTest.keyClick(w.corrected,Qt.Key_Return)
        QTest.keyClicks(w.corrected,'second line')
        QTest.keyClick(w.corrected,Qt.Key_Space)
        expected='Different word count\nsecond line '
        self.assertEqual(w.doc.phrases[0]['corrected_text'],expected)
        self.assertFalse(w.transport.active); self.assertEqual(w.transport.position(),0)
        QTest.keyClick(w.corrected,Qt.Key_Z,Qt.ControlModifier)
        self.assertIsNone(w.doc.phrases[0]['corrected_text'])
        QTest.keyClick(w.corrected,Qt.Key_Y,Qt.ControlModifier)
        self.assertEqual(w.doc.phrases[0]['corrected_text'],expected)
        w.review_button.click(); self.assertEqual(w.doc.phrases[0]['review_status'],'reviewed')
        w.corrected.moveCursor(QTextCursor.End); QTest.keyClicks(w.corrected,'more')
        self.assertEqual(w.doc.phrases[0]['review_status'],'unreviewed')
        w.undo_edit(); self.assertEqual(w.doc.phrases[0]['review_status'],'reviewed')
        self.assert_originals()

    def test_reference_application_and_independence(self):
        w=self.window
        text='Première ligne\nSecond line\nPremière ligne'
        w.replace_reference(text)
        cursor=w.reference.textCursor(); cursor.setPosition(0); cursor.setPosition(len('Première ligne\nSecond line'),QTextCursor.KeepAnchor)
        w.reference.setTextCursor(cursor); w.apply_reference_button.click()
        self.assertEqual(w.doc.phrases[0]['corrected_text'],'Première ligne\nSecond line')
        w.undo_edit(); self.assertIsNone(w.doc.phrases[0]['corrected_text'])
        w.redo_edit()
        w.replace_reference('A replacement reference')
        self.assertEqual(w.doc.phrases[0]['corrected_text'],'Première ligne\nSecond line')
        self.assertIsNone(w.doc.phrases[1]['corrected_text'])
        self.assert_originals()

    def test_restore_original_and_intentional_empty(self):
        w=self.window; self.type_correction('corrected')
        w.restore_button.click(); self.assertIsNone(w.doc.phrases[0]['corrected_text'])
        w.undo_edit(); self.assertEqual(w.doc.phrases[0]['corrected_text'],'corrected')
        w.break_edit_group(); w.corrected.selectAll(); QTest.keyClick(w.corrected,Qt.Key_Backspace)
        self.assertEqual(w.doc.phrases[0]['corrected_text'],'')
        self.assertEqual(w.doc.phrases[0]['word_alignment_status'],'phrase_only')
        w.mark_reviewed(); self.assertTrue(w.save(silent=True))
        saved=json.loads((w.doc.root/'project.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['phrases'][0]['corrected_text'],'')
        self.assertEqual(saved['phrases'][0]['review_status'],'reviewed')
        self.assert_originals()

    def test_switching_phrase_commits_and_undo_does_not_play(self):
        w=self.window; self.type_correction('first edit')
        w.table.selectRow(1)
        self.type_correction('second edit')
        w.undo_edit(); self.assertIsNone(w.doc.phrases[1]['corrected_text'])
        w.undo_edit(); self.assertEqual(w.selected,0); self.assertIsNone(w.doc.phrases[0]['corrected_text'])
        self.assertFalse(w.transport.active)
        self.assert_originals()

    def test_ctrl_enter_replay_space_in_text_and_escape(self):
        w=self.window; w.corrected.setFocus()
        with patch.object(w,'replay') as replay, patch.object(w,'toggle') as toggle, patch.object(w.transport,'halt') as halt:
            QTest.keyClick(w.corrected,Qt.Key_Return,Qt.ControlModifier)
            replay.assert_called_once()
            QTest.keyClick(w.corrected,Qt.Key_Space)
            toggle.assert_not_called()
            QTest.keyClick(w.corrected,Qt.Key_Escape)
            halt.assert_called_once()

    def test_autosave_and_reopen(self):
        w=self.window; self.type_correction('Auto saved line')
        w.replace_reference('Known lyrics\nAnother line'); w.mark_reviewed()
        QTest.qWait(1500)
        self.assertFalse(w.dirty)
        self.assertTrue(w.status.text().startswith('Saved'))
        root=w.doc.root; w.doc.close()
        reopened=Document.open(root); w.doc=reopened
        self.assertEqual(reopened.phrases[0]['corrected_text'],'Auto saved line')
        self.assertEqual(reopened.phrases[0]['review_status'],'reviewed')
        self.assertEqual(reopened.data['reference_lyrics'],'Known lyrics\nAnother line')
        self.assert_originals()

    def test_failed_primary_write_recovers_newest_and_save_as(self):
        w=self.window; self.type_correction('Survives interrupted save')
        primary=w.doc.root/'project.json'; original_hash=digest(primary)
        from comfymax_audio_chunker.editor import project
        real_replace=project.os.replace
        def replace(src,dst):
            if Path(dst)==primary: raise OSError('simulated interrupted primary write')
            return real_replace(src,dst)
        with patch.object(project.os,'replace',side_effect=replace):
            self.assertFalse(w.save(silent=True))
        self.assertTrue(w.dirty); self.assertIn('Save failed',w.status.text())
        self.assertEqual(digest(primary),original_hash)
        w.doc.close(); recovered=Document.open(primary); w.doc=recovered
        self.assertTrue(recovered.recovered)
        self.assertEqual(recovered.recovery_source,'recovery/pending.json')
        self.assertEqual(recovered.phrases[0]['corrected_text'],'Survives interrupted save')
        copied=recovered.save_as(self.root/'saved-elsewhere.comfymax')
        try:
            self.assertEqual(copied.phrases,recovered.phrases)
            self.assertEqual(digest(copied.root/'source/analysis.json'),self.snapshot_hash)
        finally: copied.close()
        self.assert_originals()

    def test_invalid_newer_recovery_ignored_and_close_cancel(self):
        w=self.window; original=copy.deepcopy(w.doc.data)
        damaged=copy.deepcopy(original); damaged['revision']+=100; damaged['phrases'][0]['corrected_text']={}
        atomic_json(w.doc.root/'recovery/pending.json',damaged)
        w.doc.close(); w.doc=Document.open(w.doc.root)
        self.assertFalse(w.doc.recovered)
        self.type_correction('pending text')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Cancel):
            self.assertFalse(w.prepare_leave())
        self.assertEqual(w.doc.phrases[0]['corrected_text'],'pending text')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Discard):
            self.assertTrue(w.prepare_leave())
        self.assertFalse((w.doc.root/'recovery/pending.json').exists())
