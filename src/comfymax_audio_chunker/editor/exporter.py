"""Verified, sample-exact mixed-source scene exports. No UI or integration code."""
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid

import numpy as np
import soundfile as sf
from .markers import boundaries,validate_marker_state,scenes_current
from .project import inside,digest


class ExportValidationError(ValueError):
    def __init__(self,issues):
        self.issues=issues
        super().__init__('\n'.join((f'Scene {number}: ' if number else '')+message for number,message in issues))


def validate_scenes(data):
    """Return approved rows; no rounding, repair, padding or implicit regeneration."""
    timeline=data.get('timeline',{}); rate=timeline.get('sample_rate'); total=timeline.get('frames')
    if type(rate) is not int or type(total) is not int or rate<=0 or total<=0:
        raise ExportValidationError([(None,'Project audio timeline is invalid.')])
    state=data.get('marker_editor',{}); snapshot=state.get('scenes')
    if not isinstance(snapshot,dict):
        raise ExportValidationError([(None,'Create Scenes before exporting.')])
    bounds=snapshot.get('boundaries'); kinds=snapshot.get('types'); issues=[]; rows=[]
    if not isinstance(bounds,list) or len(bounds)<2:
        raise ExportValidationError([(None,'Scene boundaries are missing. Return to Markers and Create Scenes again.')])
    if bounds[0]!=0: issues.append((1,'Must start at song start (sample 0); the beginning is missing.'))
    if bounds[-1]!=total: issues.append((len(bounds)-1,'Must end at song end; coverage does not match the full timeline.'))
    for i,(a,b) in enumerate(zip(bounds,bounds[1:]),1):
        valid=type(a) is int and type(b) is int and 0<=a<b<=total
        if not valid: issues.append((i,'Invalid start/end samples or non-chronological boundaries.'))
        elif b-a>15*rate: issues.append((i,f'Duration {(b-a)/rate:.6f} seconds exceeds 15 seconds. Add or move markers, then Create Scenes again.'))
        kind=kinds[i-1] if isinstance(kinds,list) and i-1<len(kinds) else None
        if kind not in ('Vocal','Instrumental'): issues.append((i,'Assign Vocal or Instrumental, then Create Scenes again.'))
        if valid and kind in ('Vocal','Instrumental'):
            rows.append(dict(scene=i,start=a/rate,end=b/rate,duration=(b-a)/rate,
                             type=kind.lower(),audio_source='vocals',
                             audio_file=f'scene_{i:03d}.wav',start_frame=a,end_frame=b,frames=b-a))
    if isinstance(kinds,list) and len(kinds)>len(bounds)-1: issues.append((None,'Scene type count does not match the scene intervals.'))
    try:
        validate_marker_state(state,total)
        if not scenes_current(state,total):
            current=boundaries(state,total); records=state.get('interval_types',[])
            first=next((i for i,(a,b) in enumerate(zip(bounds,bounds[1:]),1)
                        if i>=len(current) or (a,b)!=(current[i-1],current[i]) or
                        i>len(records) or not isinstance(kinds,list) or i>len(kinds) or kinds[i-1]!=records[i-1]['type']),1)
            issues.append((first,'Created scenes are out of date. Press Create Scenes again to use current markers and types.'))
    except (ValueError,KeyError,TypeError) as exc:
        issues.append((None,'Invalid marker/type data: '+str(exc)))
    if issues: raise ExportValidationError(issues)
    # A single shared boundary array guarantees adjacency. Assert coverage too.
    if sum(r['frames'] for r in rows)!=total:
        raise ExportValidationError([(None,'Scene durations do not reconstruct the complete timeline.')])
    return rows


def validate_sources(root,data):
    """Verify both immutable proxies against the common first-sample clock."""
    root=Path(root).resolve(); timeline=data['timeline']; paths={}; hashes={}; infos={}
    for key,label in (('mix','Full-mix proxy'),('vocals','Demucs vocal proxy')):
        asset=data.get('assets',{}).get(key)
        if not isinstance(asset,dict): raise ExportValidationError([(None,f'{label} is missing. Prepare/import both aligned tracks before exporting.')])
        try:
            path=inside(root,asset['path']); info=sf.info(path)
        except (OSError,RuntimeError,KeyError,ValueError) as exc:
            raise ExportValidationError([(None,f'{label} cannot be read: {exc}')]) from exc
        if info.frames!=timeline['frames'] or info.samplerate!=timeline['sample_rate']:
            raise ExportValidationError([(None,f'{label} has a different sample rate or frame count. Restore the aligned Stage 1 audio; export will not resample or pad it.')])
        checksum=digest(path)
        if checksum!=asset.get('sha256'):
            raise ExportValidationError([(None,f'{label} changed since import. Restore the original aligned proxy; export cannot verify its sample origin.')])
        paths['full_mix' if key=='mix' else 'vocals']=path; hashes[path]=checksum; infos[key]=info
    if infos['mix'].channels!=infos['vocals'].channels or infos['mix'].channels<1:
        raise ExportValidationError([(None,'Full mix and vocals have different channel layouts. Restore the matched Stage 1 proxies.')])
    return paths,hashes,infos['mix'].samplerate,infos['mix'].channels


def verify_export(folder,manifest,paths,progress=None):
    """Check actual files, metadata, frame counts and every source-selected sample."""
    folder=Path(folder); on_disk=json.loads((folder/'scenes.json').read_text(encoding='utf-8'))
    if on_disk!=manifest: raise RuntimeError('Export manifest failed verification.')
    total=0
    for row in manifest['scenes']:
        if progress: progress(f"Verifying scene {row['scene']} of {len(manifest['scenes'])}…")
        file=folder/row['audio_file']
        if not file.is_file(): raise RuntimeError(f"Scene {row['scene']}: exported WAV is missing.")
        info=sf.info(file)
        if (info.frames,info.samplerate,info.channels,info.subtype)!=(row['frames'],manifest['sample_rate'],manifest['channels'],'FLOAT'):
            raise RuntimeError(f"Scene {row['scene']}: exported frame count or WAV format does not match the approved interval.")
        if abs(info.duration-row['duration'])>0.5/manifest['sample_rate']:
            raise RuntimeError(f"Scene {row['scene']}: actual WAV duration does not match scenes.json.")
        with sf.SoundFile(file) as output,sf.SoundFile(paths[row['audio_source']]) as source:
            source.seek(row['start_frame']); remaining=row['frames']
            while remaining:
                count=min(65536,remaining); actual=output.read(count,dtype='float32',always_2d=True)
                expected=source.read(count,dtype='float32',always_2d=True)
                if len(actual)!=count or not np.array_equal(actual,expected):
                    raise RuntimeError(f"Scene {row['scene']}: samples do not match the selected source interval.")
                remaining-=count
        total+=info.frames
    if total!=manifest['total_frames']: raise RuntimeError('Exported WAVs do not reconstruct the full timeline.')


def export_project(root,data,output_parent,progress=None):
    data=copy.deepcopy(data); rows=validate_scenes(data)
    if progress: progress('Checking full-mix and vocal proxy alignment and checksums…')
    paths,hashes,rate,channels=validate_sources(root,data)
    parent=Path(output_parent).expanduser().resolve()
    if not parent.is_dir(): raise ValueError('Choose an existing output folder.')
    title=str(data.get('title','Song'))
    safe=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',title).strip(' .')[:70] or 'Song'
    name=f"{safe}-export-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    destination=parent/name
    stage=Path(tempfile.mkdtemp(prefix='.comfymax-export-',dir=parent))
    manifest=dict(format='comfymax-scenes',version=1,project=title,sample_rate=rate,channels=channels,
                  audio_encoding='float32',total_frames=data['timeline']['frames'],
                  duration=data['timeline']['frames']/rate,scenes=rows)
    try:
        for row in rows:
            if progress: progress(f"Exporting scene {row['scene']} of {len(rows)} from {row['audio_source']}…")
            with sf.SoundFile(paths[row['audio_source']]) as source:
                source.seek(row['start_frame']); remaining=row['frames']
                with sf.SoundFile(stage/row['audio_file'],mode='w',samplerate=rate,channels=channels,format='WAV',subtype='FLOAT') as output:
                    while remaining:
                        count=min(65536,remaining); audio=source.read(count,dtype='float32',always_2d=True)
                        if len(audio)!=count or not np.all(np.isfinite(audio)):
                            raise RuntimeError(f"Scene {row['scene']}: source audio is truncated or contains invalid samples.")
                        output.write(audio); remaining-=count
        with (stage/'scenes.json').open('w',encoding='utf-8') as handle:
            json.dump(manifest,handle,indent=2,ensure_ascii=False,allow_nan=False); handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        verify_export(stage,manifest,paths,progress)
        for path,checksum in hashes.items():
            if digest(path)!=checksum: raise RuntimeError('A source proxy changed during export. Nothing has been published.')
        if destination.exists(): raise FileExistsError('Export destination already exists. Choose Export Scenes again to create a new folder.')
        stage.rename(destination)
        return dict(folder=str(destination),scene_count=len(rows),sample_rate=rate,channels=channels,
                    total_frames=data['timeline']['frames'],manifest=manifest)
    except BaseException:
        # Only this invocation's staging folder is eligible for cleanup.
        if stage.exists() and stage.resolve().parent==parent and stage.name.startswith('.comfymax-export-'):
            shutil.rmtree(stage)
        raise
