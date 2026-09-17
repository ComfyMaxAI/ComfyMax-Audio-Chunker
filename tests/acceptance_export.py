"""Exercise the real-song GUI export on an isolated project copy."""
import json,os,shutil,sys,time
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
    w=MarkerEditor(); w.loaded(open_audio(target)); w.show()
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
    assert frames==data['timeline']['frames'] and all(counts.values())
    assert [r['start_frame'] for r in manifest['scenes']]+[manifest['scenes'][-1]['end_frame']]==expected['boundaries']
    assert [r['type'] for r in manifest['scenes']]==[v.lower() for v in expected['types']]
    w.save(True); w.close()
    assert (source/'project.json').read_bytes()==original
    assert all(digest(inside(source,a['path']))==a['sha256'] for a in data['assets'].values())
    result=dict(result='PASS',scenes=len(manifest['scenes']),sources=counts,sample_rate=rate,channels=manifest['channels'],total_frames=frames,duration=frames/rate,
                every_sample_matches_selected_source=True,approved_bounds_preserved=True,source_project_and_audio_unchanged=True,export_folder=str(folder),
                note='Acceptance copy uses saved Rain boundaries and initial stem-based type suggestions; these are test selections, not user approval.')
    report.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result))

if __name__=='__main__': main()
