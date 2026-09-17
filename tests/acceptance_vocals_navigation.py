"""Exercise the real-song GUI export on an isolated project copy."""
import copy,json,os,shutil,sys,time
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QFontDatabase,QFont
from PySide6.QtWidgets import QStyle,QStyleOptionSlider
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
import soundfile as sf
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox
from comfymax_audio_chunker.editor.project import inside,digest
from comfymax_audio_chunker.editor.marker_app import MarkerEditor,open_audio

def main():
    source,target,destination,report=map(Path,sys.argv[1:])
    original=(source/'project.json').read_bytes(); data=json.loads(original)
    target.mkdir(parents=True,exist_ok=False); destination.mkdir(parents=True,exist_ok=True)
    for name in ('recovery','cache'): (target/name).mkdir()
    for name in [data['analysis']['path']]+[a['path'] for a in data['assets'].values()]:
        dest=inside(target,name); dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(inside(source,name),dest)
    (target/'project.json').write_bytes(original)
    app=QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',10)); app.setStyle('Fusion')
    w=MarkerEditor(); w.loaded(open_audio(target)); w.resize(1460,1000); w.show(); QTest.qWait(50)
    before=copy.deepcopy(w.state); position=w.transport.position(); history=w.history.index()
    assert before==data['marker_editor']
    w.set_view(0,w.doc.duration); assert w.navigation.maximum()==0 and not w.navigation.isEnabled()
    w.set_view(0,20); assert w.navigation.isEnabled()
    w.navigation.setValue(w.navigation.maximum()); assert abs(w.detail.start-(w.doc.duration-20))<1e-9
    assert w.overview.start==w.detail.start
    w.navigation.setValue(w.navigation.maximum()//2); assert 0<w.detail.start<w.doc.duration-20
    # Drag the large actual slider handle with Qt mouse events.
    option=QStyleOptionSlider(); w.navigation.initStyleOption(option)
    handle=w.navigation.style().subControlRect(QStyle.CC_Slider,option,QStyle.SC_SliderHandle,w.navigation)
    old=w.detail.start; point=handle.center()
    QTest.mousePress(w.navigation,Qt.LeftButton,pos=point)
    QTest.mouseMove(w.navigation,QPoint(point.x()+100,point.y()))
    QTest.mouseRelease(w.navigation,Qt.LeftButton,pos=QPoint(point.x()+100,point.y()))
    assert w.detail.start>old
    w.detail.zoom(2/3); assert w.navigation.value()==round(w.detail.start*1000)
    w.overview.viewChanged.emit(10,30); assert w.navigation.value()==10000
    assert w.state==before and w.transport.position()==position and w.history.index()==history
    for frame in before['markers']:
        seconds=frame/w.transport.rate
        if w.detail.start<=seconds<=w.detail.start+w.detail.span:
            assert abs(w.detail.t(w.detail.x(seconds))-seconds)<1e-9
    w.tabs.setCurrentIndex(0); QTest.qWait(50); w.grab().save(str(report.with_suffix('.png')))
    assert w.palette().window().color().name()=='#0e1117'
    w.save(True); w.close()
    w=MarkerEditor(); w.loaded(open_audio(target)); assert w.state==before

    w.create_scene_snapshot(); expected=w.state['scenes'].copy()
    with patch.object(QFileDialog,'getExistingDirectory',return_value=str(destination)),patch.object(QMessageBox,'information') as done,patch.object(QMessageBox,'warning') as failed:
        w.export_button.click(); deadline=time.monotonic()+120
        while (w.busy or w.jobs) and time.monotonic()<deadline: QTest.qWait(25)
        assert not w.busy and not w.jobs
        failed.assert_not_called(); done.assert_called_once()
    folder=Path(w.last_export['folder']); manifest=json.loads((folder/'scenes.json').read_text())
    rate=manifest['sample_rate']; counts={'vocals':0,'full_mix':0}; frames=0
    for row in manifest['scenes']:
        counts[row['audio_source']]+=1
        key='mix' if row['audio_source']=='full_mix' else 'vocals'
        actual,sr=sf.read(folder/row['audio_file'],dtype='float32',always_2d=True)
        reference,rr=sf.read(inside(target,data['assets'][key]['path']),start=row['start_frame'],stop=row['end_frame'],dtype='float32',always_2d=True)
        assert sr==rr==rate and np.array_equal(actual,reference)
        assert row['duration']<=15 and len(actual)==row['frames']
        frames+=len(actual)
    assert frames==data['timeline']['frames'] and counts['full_mix']==0 and counts['vocals']==len(manifest['scenes'])
    assert [r['start_frame'] for r in manifest['scenes']]+[manifest['scenes'][-1]['end_frame']]==expected['boundaries']
    assert [r['type'] for r in manifest['scenes']]==[v.lower() for v in expected['types']]
    w.save(True); w.close()
    assert (source/'project.json').read_bytes()==original
    assert all(digest(inside(source,a['path']))==a['sha256'] for a in data['assets'].values())
    result=dict(result='PASS',scenes=len(manifest['scenes']),sources=counts,sample_rate=rate,channels=manifest['channels'],total_frames=frames,duration=frames/rate,
                every_sample_matches_selected_source=True,approved_bounds_preserved=True,source_project_and_audio_unchanged=True,export_folder=str(folder),
                navigation_and_zoom_passed=True,save_reopen_markers_types_scenes_unchanged=True,note='Copy of the current saved Rain project; all existing marker positions and final scene types preserved.')
    report.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result))

if __name__=='__main__': main()
