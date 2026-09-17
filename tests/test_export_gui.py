import json,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog,QMessageBox
import test_markers as fixtures


class ExportGuiTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.MarkerGuiTests.setUpClass.__func__)
    setUp=fixtures.MarkerGuiTests.setUp
    tearDown=fixtures.MarkerGuiTests.tearDown

    def test_export_action_background_completion(self):
        w=self.w; self.assertFalse(w.export_button.isEnabled())
        w.seek(.04); w.add_at_playhead(); w.change_interval_type(0,'Instrumental'); w.change_interval_type(1,'Vocal'); w.create_scene_snapshot()
        destination=self.root/'exports'; destination.mkdir()
        with patch.object(QFileDialog,'getExistingDirectory',return_value=str(destination)),patch.object(QMessageBox,'information') as done,patch.object(QMessageBox,'warning') as failed:
            w.export_button.click()
            for _ in range(500):
                if not w.busy and not w.jobs: break
                QTest.qWait(20)
            self.assertFalse(w.busy); failed.assert_not_called(); done.assert_called_once()
        manifest=json.loads((Path(w.last_export['folder'])/'scenes.json').read_text())
        self.assertEqual([r['audio_source'] for r in manifest['scenes']],['vocals','vocals'])
        self.assertEqual(sum(r['frames'] for r in manifest['scenes']),4800)

    def test_stale_scene_validation_precedes_folder_dialog(self):
        w=self.w; w.create_scene_snapshot(); w.change_interval_type(0,'Vocal')
        with patch.object(QMessageBox,'exec',return_value=QMessageBox.Ok) as warning,patch.object(QFileDialog,'getExistingDirectory') as folder:
            w.export_button.click(); warning.assert_called_once(); folder.assert_not_called()
        self.assertEqual(w.scene_table.currentRow(),0); self.assertFalse(w.busy)
