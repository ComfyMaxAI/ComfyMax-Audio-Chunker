# Export Scenes

Launch `D:\ComfyMax-Audio-Chunker\Launch Editor.cmd` and open your project.

1. Finish placing markers and choose Vocal or Instrumental for each interval.
2. Press **Create Scenes**. If you change a marker or type afterward, create scenes again.
3. Press **Export Scenes** and select an output folder.
4. Wait for **Export complete**. A uniquely named project export subfolder contains `scenes.json` and `scene_001.wav`, `scene_002.wav`, etc. Existing exports are never overwritten.

**Every scene uses the Demucs vocal stem, including Instrumental scenes. Vocal/Instrumental is metadata only.** The listening track and volume setting do not affect export.

Every scene must have a valid type and positive duration no longer than 15 seconds. Scenes must cover the complete song in order. Invalid scenes are identified before export; the first affected scene is selected. Export never changes markers or silently regenerates scenes.

Audio uses the existing aligned Stage 1 proxies. Both tracks must retain their imported checksums, identical sample rates, frame counts and channel counts. The common sample origin comes from the Stage 1 preparation; export does not guess alignment or repair mismatched files.

Each file copies precisely its approved sample interval, with no padding, overlaps, fades, normalization or resampling. Output is 32-bit floating-point WAV, preserving the proxy samples without clipping. For Rain this is 44,100 Hz stereo. Consecutive files reconstruct the song's complete timeline; the audio content always comes from the vocals stem.

The application verifies every WAV's format, duration and every sample against its selected source before publishing the final folder. Interrupted exports are not presented as completed exports. Keep `scenes.json` and the WAVs together when moving the folder.

The JSON contains `format: "comfymax-scenes"`, `version: 1`, project title and scene records with `scene`, `start`, `end`, `duration`, lowercase `type`, `audio_source` (always `vocals`) and relative `audio_file`. Additional sample rate/channel and integer frame fields preserve exact boundary information. Times are seconds from the first decoded sample.

This remains a standalone application. No ComfyMax integration is added. Export verification checks audio files and timing; actual MiniMax ingestion is a downstream test.
