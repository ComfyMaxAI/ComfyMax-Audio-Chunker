# Stage 1 verification — 16 September 2026

Current status: the supplied real song has now completed Stage 1 successfully after fixes, with nine tests passing. See `REAL_SONG_TEST.md` for results and remaining phrase/timing limitations. Listening approval is pending. Stage 2 has not started.

The remainder of this document records the earlier synthetic smoke checks.

Installed at `D:\ComfyMax-Audio-Chunker`, with private Python 3.11.15 and `.venv`. ComfyUI's environment was not modified. Primary packages: Demucs 4.0.1, faster-whisper 1.2.1, torch/torchaudio 2.8.0+cu128, numpy 2.2.6 and soundfile 0.13.1. See `installed-versions.txt` for the full resolved environment.

## Completed checks

| Check | Result |
| --- | --- |
| Dependency consistency (`pip check`) | Pass |
| Seven unit/integration tests | Pass |
| Command-line help | Pass |
| CUDA hardware discovery | RTX 5060 Ti recognized; PyTorch contains sm_120 |
| Actual Demucs + Whisper processing on CPU | Pass |
| PowerShell launcher with cached models and `-Offline` | Pass |
| Original SHA-256 before/after processing | Identical |
| Continuous region coverage from 0 to decoded duration | Pass |
| Real-song lyric/timestamp accuracy | Not tested |
| Full GPU inference | Not tested; ComfyUI was using most GPU memory |

## Actual model smoke test

Input: generated 12-second stereo PCM WAV, with two seconds of silence, eight seconds of a three-tone chord and two seconds of silence. This is an instrumental test signal, not a real song and not synthesized singing.

First run: `runs\synthetic-smoke-20260916-153958\analysis`

- Demucs `htdemucs`, CPU; faster-whisper `small`, CPU int8, English.
- About 28.2 seconds including first model downloads/loading.
- Produced vocal stem, analysis mix, human-readable report and structured JSON.
- One estimated instrumental region from 0.000 to 12.000 seconds.
- Whisper hallucinated “You” at 10.58–11.98 seconds. It was flagged as suspect and excluded from phrase candidates; it did not create a vocal region.
- Source SHA-256: `21bd0c74689143b7e5784aaca7e95fa1763a5c8a640153206a3aa0171fb2dfe9`, unchanged.

Offline run: `runs\offline-smoke`, using the PowerShell launcher and previously downloaded weights. Completed successfully in approximately 12.7 seconds with the same region and suspect-word result. This exercised the offline settings; the machine's network was not physically disconnected.

## Next required test

Provide a path to a real mixed song. Run the default small model first, inspect the isolated vocal stem and listen around the estimated boundaries. If lyrics are poor, compare the medium model. Record missed vocals, bleed and timing errors before deciding whether the stage is acceptable. Stage 1 should not be called reliable on singing from the synthetic test alone.
