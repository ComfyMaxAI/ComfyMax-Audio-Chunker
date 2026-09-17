"""Real-project GUI acceptance in a separate copy; never edits the source project.

python tests/acceptance_corrections.py SOURCE_PROJECT NEW_TEST_FOLDER REPORT_JSON
Uses Qt's offscreen test platform unless QT_QPA_PLATFORM is already set.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QFont, QPalette, QColor, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog
from comfymax_audio_chunker.editor.project import Document, digest, inside
from comfymax_audio_chunker.editor.app import Editor
from comfymax_audio_chunker.editor.audio import load_audio


def main():
    source,target,report=map(lambda p:Path(p).resolve(),sys.argv[1:])
    manifest=source/'project.json'
    original_bytes=manifest.read_bytes(); data=json.loads(original_bytes)
    target.mkdir(parents=True,exist_ok=False)
    for name in ('source','audio','cache','recovery'): (target/name).mkdir()
    for name in [data['analysis']['path']]+[a['path'] for a in data['assets'].values()]:
        dest=inside(target,name); dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(inside(source,name),dest)
    (target/'project.json').write_bytes(original_bytes)
    (target/'recovery/last-good.json').write_bytes(original_bytes)
    app=QApplication.instance() or QApplication([]); app.setStyle('Fusion')
    # The offscreen Windows test platform does not discover system fonts itself.
    font=Path('C:/Windows/Fonts/segoeui.ttf')
    if font.exists(): QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont('Segoe UI',10))
    palette=app.palette()
    for role,color in [(QPalette.Window,'#f3f5f7'),(QPalette.WindowText,'#263342'),(QPalette.Text,'#182532'),
                       (QPalette.Base,'#ffffff'),(QPalette.AlternateBase,'#f0f3f7'),(QPalette.Button,'#edf0f4'),
                       (QPalette.ButtonText,'#182532'),(QPalette.Highlight,'#315f92'),(QPalette.HighlightedText,'#ffffff')]:
        palette.setColor(role,QColor(color))
    app.setPalette(palette)
    doc=Document.open(target)
    evidence=copy.deepcopy(doc.analysis); initial=copy.deepcopy(doc.phrases)
    original_hash=digest(doc.root/'source/analysis.json')
    window=Editor(); window.resize(1280,960)
    arrays,peaks=load_audio(doc); window.loaded((doc,arrays,peaks))
    window.show(); window.activateWindow(); QTest.qWait(80)
    try:
        window.table.selectRow(1)
        window.corrected.setFocus(); window.corrected.selectAll()
        QTest.keyClicks(window.corrected,'Ever since you went away')
        QTest.keyClick(window.corrected,Qt.Key_Return)
        QTest.keyClicks(window.corrected,'A test correction with extra words')
        corrected=window.corrected.toPlainText()
        assert window.doc.phrases[1]['corrected_text']==corrected
        assert not window.transport.active
        QTest.keyClick(window.corrected,Qt.Key_Z,Qt.ControlModifier)
        assert window.doc.phrases[1]['corrected_text']==initial[1]['corrected_text']
        QTest.keyClick(window.corrected,Qt.Key_Y,Qt.ControlModifier)
        assert window.doc.phrases[1]['corrected_text']==corrected
        window.mark_reviewed(); assert window.doc.phrases[1]['review_status']=='reviewed'

        window.reference_toggle.setChecked(True)
        # Test UTF-8 file loading with line breaks, repeated lines and Unicode.
        lyrics='Ever since you went away\nEvery day is such a cloudy day\n\nEver since you went away\nÉté — test reference only'
        lyrics_file=target/'reference-test.txt'; lyrics_file.write_text(lyrics,encoding='utf-8')
        with patch.object(QFileDialog,'getOpenFileName',return_value=(str(lyrics_file),'')):
            window.load_reference_button.click()
        assert window.doc.data['reference_lyrics']==lyrics
        window.table.selectRow(2)
        begin=len('Ever since you went away\n'); end=begin+len('Every day is such a cloudy day')
        cursor=window.reference.textCursor(); cursor.setPosition(begin); cursor.setPosition(end,QTextCursor.KeepAnchor)
        window.reference.setTextCursor(cursor); window.apply_reference_button.click()
        assert window.doc.phrases[2]['corrected_text']=='Every day is such a cloudy day'
        window.undo_edit(); assert window.doc.phrases[2]['corrected_text']==initial[2]['corrected_text']
        window.redo_edit()
        window.restore_original(); assert window.doc.phrases[2]['corrected_text'] is None
        window.undo_edit(); assert window.doc.phrases[2]['corrected_text']=='Every day is such a cloudy day'
        window.mark_reviewed()
        window.replace_reference('Replacement reference\ndoes not rewrite corrections')
        assert window.doc.phrases[1]['corrected_text']==corrected
        assert window.doc.phrases[2]['corrected_text']=='Every day is such a cloudy day'
        window.undo_edit() # Retain the demonstration reference in the screenshot.

        QTest.qWait(1500)
        assert not window.dirty
        assert window.status.text().startswith('Saved')
        window.grab().save(str(report.with_suffix('.png')))
        for old,new in zip(initial,window.doc.phrases):
            for key in ('id','start','end','imported_start','imported_end','original_text','source_segment_ids','source_word_ids'):
                assert new[key]==old[key],key
        assert window.doc.analysis==evidence
        assert digest(target/'source/analysis.json')==original_hash
        assert window.doc.data['chunk_boundaries']==[]
        assert len(window.doc.analysis['regions'])==15
        assert len(window.doc.phrases)==22

        saved_rows=copy.deepcopy(window.doc.phrases)
        window.doc.close(); window.doc=Document.open(target)
        assert window.doc.phrases==saved_rows
        assert window.doc.data['reference_lyrics']==lyrics
        assert window.doc.phrases[1]['review_status']=='reviewed'
        assert window.doc.phrases[2]['review_status']=='reviewed'

        # A real-sized interrupted save: primary remains old; checkpoint is newer.
        window.corrected.setFocus(); window.corrected.selectAll()
        QTest.keyClicks(window.corrected,'Recovered real-song edit')
        primary=target/'project.json'
        from comfymax_audio_chunker.editor import project
        real_replace=project.os.replace
        def fail_primary(src,dst):
            if Path(dst)==primary: raise OSError('Acceptance test: interrupted primary replacement')
            return real_replace(src,dst)
        with patch.object(project.os,'replace',side_effect=fail_primary):
            assert not window.save(silent=True)
        assert window.dirty
        window.doc.close(); window.doc=Document.open(target)
        assert window.doc.recovered
        assert window.doc.phrases[2]['corrected_text']=='Recovered real-song edit'
        assert window.doc.phrases[2]['start']==initial[2]['start']
        assert window.save(silent=True)

        result=dict(result='PASS',source_project=str(source),test_copy=str(target),
            phrases=22,original_words=len(evidence['words']),regions=15,
            checks=['side-by-side text and timestamp invariance','typing/newlines without playback',
                    'Ctrl+Z / Ctrl+Y','UTF-8 reference load and explicit selection application',
                    'reference replacement does not alter corrections','Mark Reviewed and Restore Original',
                    'autosave and reopen','newest valid interrupted-save recovery'],
            source_analysis_sha256=original_hash,source_project_unchanged=manifest.read_bytes()==original_bytes,
            original_whisper_data_unchanged=True,automatic_chunking=False,
            note='Test corrections are demonstration text in a separate copy, not verified lyrics.')
        assert result['source_project_unchanged']
        report.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
    finally:
        window.autosave.stop(); window.dirty=False; window.doc.recovered=False
        window.close()


if __name__=='__main__': main()
