"""Real-song workflow test, with test-only review actions in a separate copy."""
import copy,json,os,shutil,sys
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from comfymax_audio_chunker.editor.project import Document,inside,digest
from comfymax_audio_chunker.editor.app import Editor
from comfymax_audio_chunker.editor.audio import load_audio
from comfymax_audio_chunker.editor.lyrics_workflow import review_complete,validate_history
from comfymax_audio_chunker.editor.scenes import propose,phrase_spans,scene_rows


def main():
    source,target,report=map(lambda p:Path(p).resolve(),sys.argv[1:])
    original=(source/'project.json').read_bytes(); data=json.loads(original)
    target.mkdir(parents=True,exist_ok=False)
    for name in ('source','audio','cache','recovery'): (target/name).mkdir()
    for name in [data['analysis']['path']]+[a['path'] for a in data['assets'].values()]:
        dest=inside(target,name); dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(inside(source,name),dest)
    (target/'project.json').write_bytes(original)
    app=QApplication.instance() or QApplication([]); app.setStyle('Fusion')
    for name in ('segoeui.ttf','seguisym.ttf'):
        path=Path('C:/Windows/Fonts')/name
        if path.exists(): QFontDatabase.addApplicationFont(str(path))
    app.setFont(QFont('Segoe UI',10))
    doc=Document.open(target); phrases=copy.deepcopy(doc.phrases); evidence=copy.deepcopy(doc.analysis)
    source_hash=digest(target/'source/analysis.json'); arrays,peaks=load_audio(doc)
    w=Editor(); w.loaded((doc,arrays,peaks)); w.resize(1420,1080); w.show(); w.activateWindow(); w.tabs.setCurrentIndex(0)
    QTest.qWait(60)
    assert w.table.horizontalHeaderItem(3).text()=='Duration'
    assert not w.generate_button.isEnabled() and not review_complete(doc.data)
    with patch.object(QMessageBox,'warning') as warning:
        w.complete_button.click(); assert warning.called
    # Split the corrected phrase at an explicitly chosen test cursor/time.
    # The chosen split is a mechanics test, not a claimed musical alignment.
    index=3; parent=copy.deepcopy(doc.phrases[index]); text=parent['corrected_text'] or parent['original_text']
    split_index=text.index(',')+1; split_time=39.5
    w.table.selectRow(index); cursor=w.corrected.textCursor(); cursor.setPosition(split_index); w.corrected.setTextCursor(cursor)
    w.split_button.click(); w.seek(split_time); w.split_playhead.click()
    assert abs(w.split_time.value()-split_time)<.000001
    with patch.object(w.transport,'play') as play:
        w.split_listen.click(); play.assert_called_once_with(round(38*w.transport.rate),round(41*w.transport.rate),loop=False)
    assert w.split_confirm.isEnabled()
    QTest.qWait(30); w.grab().save(str(report.with_suffix('.png')))
    w.split_confirm.click(); assert len(doc.phrases)==len(phrases)+1
    first,second=doc.phrases[index:index+2]
    assert (first['start'],first['end'],second['start'],second['end'])==(parent['start'],split_time,split_time,parent['end'])
    assert first['corrected_text']+second['corrected_text']==text
    assert first['review_status']==second['review_status']=='unreviewed'
    assert doc.data['phrase_history'][0]['parent']==parent
    assert all(p['word_alignment_status']=='phrase_only' for p in (first,second))
    with patch.object(w.transport,'play') as play:
        w.audition(index); assert play.call_count==1
        w.audition(index+1); assert play.call_count==2
    w.undo_edit(); assert doc.phrases==phrases
    w.redo_edit(); validate_history(doc.data)
    # Exercise independent correction and review, then restore test text.
    w.table.selectRow(index); second_snapshot=copy.deepcopy(doc.phrases[index+1])
    w.corrected.setPlainText('Temporary first-half test edit'); w.mark_reviewed()
    assert doc.phrases[index+1]==second_snapshot
    w.undo_edit(); w.undo_edit()
    # Simulated reviewer in this test copy only. No user project is certified.
    for i in range(len(doc.phrases)):
        w.table.selectRow(i); w.mark_reviewed()
    w.complete_button.click(); assert review_complete(doc.data) and w.generate_button.isEnabled()
    with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes): w.generate_button.click()
    cuts=doc.data['chunk_boundaries']; rows=scene_rows(doc.data,doc.analysis)
    assert all(r['duration']<=15 for r in rows)
    assert not any(a<c<b for a,b,p in phrase_spans(doc.data) for c in cuts)
    w.table.selectRow(index); w.corrected.setPlainText('A new edit reopens review')
    assert not review_complete(doc.data) and not w.generate_button.isEnabled()
    assert 'earlier lyric version' in w.scene_summary.text()
    w.undo_edit(); assert review_complete(doc.data)
    QTest.qWait(1400); assert not w.dirty; assert w.save(silent=True)
    expected=copy.deepcopy(doc.data); w.close(); reopened=Document.open(target)
    assert reopened.phrases==expected['phrases'] and reopened.data['phrase_history']==expected['phrase_history']
    assert review_complete(reopened.data); validate_history(reopened.data)
    assert reopened.analysis==evidence and digest(target/'source/analysis.json')==source_hash
    reopened.close(); assert (source/'project.json').read_bytes()==original
    report.write_text(json.dumps(dict(result='PASS',original_phrases=len(phrases),test_split_phrases=len(expected['phrases']),
        source_project_unchanged=True,whisper_evidence_unchanged=True,original_regions_unchanged=True,
        test_split={'parent_start':parent['start'],'chosen_time':split_time,'parent_end':parent['end']},
        tests=['Duration column','review gate before generation','explicit text and playhead split','listen around split',
               'independent children and audition','lineage','undo/redo','independent correction/review',
               'test-only completion','generated scenes <=15s with no reviewed-phrase splits',
               'text edit reopens review','autosave/reopen'],
        note='Review completion and split time are test-only, not user approval or verified musical alignment. No source project was marked complete.'),indent=2),encoding='utf-8')
    print(report.read_text())

if __name__=='__main__': main()
