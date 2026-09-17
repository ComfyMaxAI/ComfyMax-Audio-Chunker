"""Rain interval types: migration, real dropdown input, persistence, regeneration."""
import copy,json,os,shutil,sys
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from comfymax_audio_chunker.editor.project import Document,inside,digest
from comfymax_audio_chunker.editor.marker_app import MarkerEditor,open_audio
from comfymax_audio_chunker.editor.markers import boundaries,created_scenes,scenes_current,intervals


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
        font=Path('C:/Windows/Fonts')/name
        if font.exists(): QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont('Segoe UI',10))
    w=MarkerEditor(); w.loaded(open_audio(target)); w.resize(1360,960); w.show(); w.activateWindow(); QTest.qWait(50)
    doc=w.doc; original_phrases=copy.deepcopy(doc.phrases); old_boundaries=boundaries(w.state,w.transport.total)
    old_durations=[r['duration'] for r in intervals(old_boundaries,w.transport.rate)]
    assets={key:digest(inside(doc.root,value['path'])) for key,value in doc.data['assets'].items()}
    initial=[r['type'] for r in w.state['interval_types']]
    assert set(initial)=={'Vocal','Instrumental'}
    assert len(initial)==len(old_boundaries)-1
    assert w.marker_table.cellWidget(w.marker_table.rowCount()-1,3) is None
    w.create_scene_snapshot(); snapshot=copy.deepcopy(w.state['scenes']); w.tabs.setCurrentIndex(0)
    # Actual keyboard interaction with the embedded dropdown, not a model call.
    first=w.marker_table.cellWidget(0,3); desired='Vocal' if first.currentText()=='Instrumental' else 'Instrumental'
    with patch.object(w.transport,'halt',side_effect=AssertionError('type must not stop audio')),patch.object(w.transport,'seek',side_effect=AssertionError('type must not seek')):
        first.setFocus(); QTest.keyClick(first,Qt.Key_Home if desired=='Vocal' else Qt.Key_End)
    assert w.state['interval_types'][0]['type']==desired and w.state['interval_types'][0]['source']=='manual'
    assert w.state['scenes']==snapshot and not scenes_current(w.state,w.transport.total)
    assert boundaries(w.state,w.transport.total)==old_boundaries
    w.history.undo(); assert [r['type'] for r in w.state['interval_types']]==initial
    w.history.redo(); w.create_scene_snapshot(); rows=created_scenes(w.state,w.transport.rate)
    assert rows[0]['type']==desired and w.scene_table.item(0,4).text()==desired
    assert [r['duration'] for r in rows]==old_durations
    QTest.qWait(1400); assert not w.dirty
    expected=copy.deepcopy(w.state); w.tabs.setCurrentIndex(0); w.select_marker(old_boundaries[1]); w.set_view(0,40)
    QTest.qWait(30); w.grab().save(str(report.with_suffix('.png')))
    w.save(True); w.close()
    # Open a second GUI instance: the classifier must not replace saved manual types.
    reopened=MarkerEditor(); reopened.loaded(open_audio(target))
    assert reopened.state==expected
    reopened.create_scene_snapshot(); assert reopened.state==expected
    assert reopened.doc.phrases==original_phrases
    assert {key:digest(inside(reopened.doc.root,value['path'])) for key,value in reopened.doc.data['assets'].items()}==assets
    reopened.save(True); reopened.close(); assert (source/'project.json').read_bytes()==original
    result=dict(result='PASS',interval_count=len(rows),suggestions={'Vocal':initial.count('Vocal'),'Instrumental':initial.count('Instrumental')},
                manual_override_survived=True,positions_unchanged=True,durations_unchanged=True,
                audio_assets_unchanged=True,lyrics_unchanged=True,source_project_unchanged=True,
                save_reopen_regeneration_passed=True,scene_records_include_type=True,
                note='The override is test-only. Stem activity is a suggestion, not verified musical classification.')
    report.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result))

if __name__=='__main__': main()
