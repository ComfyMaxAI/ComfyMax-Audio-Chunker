"""Manual integration smoke test, actual models; NOT real-song acceptance.

Run from project root: .\.venv\Scripts\python.exe tests\smoke_models.py
Downloads htdemucs and Whisper small on first use. Forces CPU.
"""
from pathlib import Path
from datetime import datetime
import json
import subprocess
import sys
import numpy as np
import soundfile as sf

root=Path(__file__).resolve().parents[1]
folder=root/'runs'/('synthetic-smoke-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
folder.mkdir(parents=True,exist_ok=False)
sr=44100
t=np.arange(sr*8)/sr
wave=sum(.04*np.sin(2*np.pi*f*t) for f in [220,277.18,329.63])
envelope=np.minimum(np.minimum(t/.2,(8-t)/.2),1).clip(0,1)
mono=np.r_[np.zeros(sr*2),wave*envelope,np.zeros(sr*2)].astype(np.float32)
song=folder/'synthetic-instrumental.wav'
sf.write(song,np.column_stack([mono,mono]),sr,subtype='PCM_16')
result=subprocess.run([sys.executable,'-m','comfymax_audio_chunker',str(song),
                       '--output',str(folder/'analysis'),'--device','cpu','--language','en'])
if result.returncode:
    raise SystemExit(result.returncode)
data=json.loads((folder/'analysis'/'analysis.json').read_text(encoding='utf-8'))
assert data['source']['unchanged']
assert abs(data['timeline']['duration']-12)<1/sr
assert data['regions'][0]['start']==0
assert data['regions'][-1]['end']==12
assert all(a['end']==b['start'] for a,b in zip(data['regions'],data['regions'][1:]))
print('MODEL PIPELINE SMOKE PASS:',folder)
print('This checks runtime and timeline integrity, not singing accuracy. Real-song acceptance still required.')
