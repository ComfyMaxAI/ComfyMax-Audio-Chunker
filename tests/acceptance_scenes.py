"""Complete real-song scene acceptance on a separate project copy."""
import copy,json,os,shutil,sys
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from comfymax_audio_chunker.editor.project import Document,inside,digest
from comfymax_audio_chunker.editor.app import Editor
from comfymax_audio_chunker.editor.audio import load_audio,Cursor
from comfymax_audio_chunker.editor.scenes import scene_rows
from comfymax_audio_chunker.editor.waveform import timestamp


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
    doc=Document.open(target); originals=copy.deepcopy(doc.phrases); regions=copy.deepcopy(doc.analysis)
    source_hash=digest(target/'source/analysis.json')
    arrays,peaks=load_audio(doc); w=Editor(); w.loaded((doc,arrays,peaks)); w.resize(1360,960)
    w.show(); w.activateWindow(); QTest.qWait(60); w.tabs.setCurrentIndex(1)
    # Simulate explicit reviewer actions only in this isolated acceptance copy.
    for i in range(len(doc.phrases)):
        w.table.selectRow(i); w.mark_reviewed()
    w.complete_button.click()
    w.generate_button.click(); proposed=list(doc.data['chunk_boundaries']); rows=scene_rows(doc.data,doc.analysis)
    assert rows[0]['start_frame']==0 and rows[-1]['end_frame']==doc.data['timeline']['frames']
    assert all(r['duration']<=15 for r in rows)
    assert not any('inside' in warning for r in rows for warning in r['warnings'])
    # Audition wiring and sample output for every scene, on both source tracks.
    for i,row in enumerate(rows):
        w.scene_table.selectRow(i)
        with patch.object(w.transport,'play') as play:
            w.scene_play.click(); play.assert_called_once_with(row['start_frame'],row['end_frame'],loop=False)
        for audio in arrays.values():
            cursor=Cursor(row['start_frame'],row['end_frame'],row['start_frame'])
            block=np.empty((8192,2),dtype=np.float32)
            while cursor.frame<cursor.end:
                begin=cursor.frame; count=cursor.render(audio,block)
                np.testing.assert_array_equal(block[:count],audio[begin:begin+count])
                if count<len(block): np.testing.assert_array_equal(block[count:],0)
    w.scene_table.selectRow(0)
    with patch.object(w.transport,'play') as play:
        w.scene_next.click(); assert w.selected_scene==1
        w.scene_previous.click(); assert w.selected_scene==0
        assert play.call_count==2
    # Manual numeric cut, drag on actual marker lane, delete and shared undo/redo.
    w.cut_time.setValue(2); w.cut_add.click(); assert 2*w.transport.rate in doc.data['chunk_boundaries']
    w.cut_time.setValue(2.5); w.cut_move.click(); assert round(2.5*w.transport.rate) in doc.data['chunk_boundaries']
    w.set_view(0,12); QTest.qWait(20)
    a=QPoint(round(w.detail.x(2.5)),w.detail.height()-18); b=QPoint(round(w.detail.x(3)),w.detail.height()-18)
    QTest.mousePress(w.detail,Qt.LeftButton,pos=a); QTest.mouseMove(w.detail,b); QTest.mouseRelease(w.detail,Qt.LeftButton,pos=b)
    assert abs(w.selected_cut/w.transport.rate-3)<.04
    w.cut_delete.click(); assert doc.data['chunk_boundaries']==proposed
    w.undo_edit(); assert doc.data['chunk_boundaries']!=proposed
    w.redo_edit(); assert doc.data['chunk_boundaries']==proposed
    # A deliberate manual over-limit merge must be very visible, but allowed.
    w.commit_cuts([],'test whole song scene'); assert 'OVER 15 SECONDS' in w.scene_table.item(0,5).text()
    w.undo_edit(); assert doc.data['chunk_boundaries']==proposed
    w.cut_time.setValue(3); w.cut_add.click()
    with patch.object(QMessageBox,'question',return_value=QMessageBox.Cancel): w.generate_button.click()
    assert doc.data['chunk_boundaries']!=proposed
    with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes): w.generate_button.click()
    assert doc.data['chunk_boundaries']==proposed
    assert doc.phrases==originals and doc.analysis==regions
    QTest.qWait(1400); assert not w.dirty
    w.scene_table.selectRow(4); w.scene_selection_changed(); QTest.qWait(30)
    w.grab().save(str(report.with_suffix('.png')))
    assert w.save(silent=True)
    w.close(); reopened=Document.open(target)
    assert reopened.data['chunk_boundaries']==proposed and reopened.phrases==originals
    assert digest(target/'source/analysis.json')==source_hash
    reopened.close(); assert (source/'project.json').read_bytes()==original
    report.write_text(json.dumps(dict(result='PASS',scene_count=len(rows),duration=sum(r['duration'] for r in rows),
        test_project=str(target),source_project_unchanged=True,all_phrase_data_unchanged=True,
        all_detected_regions_unchanged=True,all_scene_samples_verified_both_sources=True,
        audio_exported=False,scenes=rows),indent=2,ensure_ascii=False),encoding='utf-8')
    lines=['# Rain from the Skies — proposed scene segmentation','',
        f'{len(rows)} scenes covering the complete {timestamp(rows[-1]["end"])} song. No audio has been exported.','',
        'Generated from the current saved corrected lyrics and timestamps. Cuts remain proposals for audition and approval.','',
        '| Scene | Start | End | Duration | Associated corrected lyrics | Review |',
        '|---|---|---|---|---|---|']
    for r in rows:
        text=r['lyrics'].replace('\n',' / ').replace('|','\\|')
        lines.append(f"| {r['scene']:03d} | {timestamp(r['start'])} | {timestamp(r['end'])} | {r['duration']:.3f} s | {text} | {'; '.join(r['warnings'])} |")
    lines+=['','All proposals are at most 15 seconds; no proposal cuts inside a nonblank timed lyric phrase. Instrumental spans are evenly divided, including approximately 4.98-second interlude and 4.96-second outro scenes. Detected vocals without transcript are explicitly labeled for review. Whisper segment boundaries may still fall within a sung sentence, so audition remains necessary.']
    report.with_suffix('.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'result':'PASS','scene_count':len(rows),'durations':[round(r['duration'],3) for r in rows],
                      'warnings':[(r['scene'],r['warnings']) for r in rows if r['warnings']]}))

if __name__=='__main__': main()
