"""Full Rain marker workflow acceptance on a copy, with explicit test markers."""
import copy,json,os,shutil,sys
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from comfymax_audio_chunker.editor.project import Document,inside,digest
from comfymax_audio_chunker.editor.marker_app import MarkerEditor
from comfymax_audio_chunker.editor.audio import load_audio
from comfymax_audio_chunker.editor.markers import created_scenes,scenes_current,boundaries


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
    analysis_hash=digest(target/'source/analysis.json'); w=MarkerEditor(); w.loaded((doc,*load_audio(doc)))
    w.resize(1280,900); w.show(); w.activateWindow(); QTest.qWait(80)
    assert w.state['scenes'] is None and w.scene_table.rowCount()==0
    assert w.create_button.isEnabled() # No lyric review checkpoint needed.
    for seconds in (5.9,11.8,23.68,35.68,47.14,107.82,127.74,193.54):
        w.seek(seconds); w.add_button.click()
    assert w.state['scenes'] is None and w.scene_table.rowCount()==0
    rate=w.transport.rate; original_markers=list(w.state['markers'])
    w.select_marker(round(11.8*rate)); w.marker_time.setValue(12); w.move_button.click()
    w.set_view(0,30); QTest.qWait(30)
    start=QPoint(round(w.detail.x(12)),w.detail.height()-16); end=QPoint(round(w.detail.x(13)),w.detail.height()-16)
    QTest.mousePress(w.detail,Qt.LeftButton,pos=start); QTest.mouseMove(w.detail,end); QTest.mouseRelease(w.detail,Qt.LeftButton,pos=end)
    assert abs(w.selected_marker/rate-13)<.04
    w.delete_button.click(); w.history.undo(); w.history.redo(); w.history.undo()
    selected=w.selected_marker
    w.select_marker(round(35.68*rate)); w.before.setValue(1); w.after.setValue(2)
    with patch.object(w.transport,'play') as play:
        w.audition_button.click(); play.assert_called_once_with(round(34.68*rate),round(37.68*rate),loop=False)
    # Real device check: no seek/restart or stream replacement on source switch.
    w.play_range(round(35*rate),round(40*rate)); QTest.qWait(250)
    stream=w.transport.stream; before=w.transport.position(); cursor=w.transport.cursor
    w.source.setCurrentIndex(w.source.findData('vocals'))
    assert w.transport.stream is stream and w.transport.cursor is cursor and w.transport.position()>=before
    QTest.qWait(150); w.source.setCurrentIndex(0); assert w.transport.stream is stream
    w.stop(); parked=w.transport.parked; w.source.setCurrentIndex(1); assert w.transport.parked==parked
    w.source.setCurrentIndex(0)
    w.create_button.click(); expected=bounds=boundaries(w.state,w.transport.total)
    assert w.state['scenes']['boundaries']==bounds
    rows=created_scenes(w.state,rate); assert len(rows)==len(bounds)-1
    assert rows[0]['start_frame']==0 and rows[-1]['end_frame']==w.transport.total
    assert any(r['over_limit'] for r in rows) # User intervals are warned, never auto-split.
    for i,r in enumerate(rows):
        w.scene_table.selectRow(i)
        with patch.object(w.transport,'play') as play:
            w.scene_play.click(); play.assert_called_once_with(r['start_frame'],r['end_frame'],loop=False)
    old_snapshot=copy.deepcopy(w.state['scenes']); w.seek(150); w.add_at_playhead()
    assert w.state['scenes']==old_snapshot and not scenes_current(w.state,w.transport.total)
    assert not w.scene_play.isEnabled() and 'Markers have changed' in w.scene_status.text()
    w.create_scene_snapshot(); assert scenes_current(w.state,w.transport.total)
    w.transcript_toggle.setChecked(True); assert w.tabs.count()==3
    assert doc.phrases==phrases and doc.analysis==evidence
    w.transcript_toggle.setChecked(False); w.tabs.setCurrentIndex(0); w.select_marker(round(35.68*rate)); w.set_view(20,35)
    QTest.qWait(1400); assert not w.dirty
    w.grab().save(str(report.with_suffix('.png')))
    final=copy.deepcopy(w.state); w.save(True); w.close()
    reopened=Document.open(target)
    assert reopened.data['marker_editor']==final and reopened.phrases==phrases
    assert digest(target/'source/analysis.json')==analysis_hash
    reopened.close(); assert (source/'project.json').read_bytes()==original
    report.write_text(json.dumps(dict(result='PASS',source_project_unchanged=True,lyrics_and_regions_unchanged=True,
        total_duration=rows[-1]['end'],markers=len(final['markers']),scenes=len(final['scenes']['boundaries'])-1,
        tests=['manual placement','numeric move','waveform drag','delete/undo/redo','marker audition',
        'live and paused source switching preserves stream/position','no automatic scenes','explicit Create Scenes',
        'whole-song fixed endpoints','over-15s warnings without automatic splitting','stale scenes until explicit recreation',
        'scene auditions','optional transcript independent','autosave/reopen'],
        note='Markers are test-only, not proposed or approved song segmentation. No audio exported.'),indent=2),encoding='utf-8')
    print(report.read_text())

if __name__=='__main__': main()
