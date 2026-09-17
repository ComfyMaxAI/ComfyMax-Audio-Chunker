# ComfyMax — manual waveform markers

The workflow is **Load Song → Demucs → edit waveform markers → Create Scenes**. Audio export comes later. Lyrics never control markers or require approval.

## Open the application

Close the previous editor and double-click `D:\ComfyMax-Audio-Chunker\Launch Editor.cmd`.

- **Load Song** selects an MP3/WAV (also FLAC/M4A), then a new project folder. The existing local Demucs routine prepares the full-mix playback copy and isolated vocals. No Whisper transcription or region analysis is needed. Preparation runs in the background; wait for it to finish before closing the application. First use requires the Demucs weights; this computer already has them cached.
- **Open Project** opens existing work, including Rain. Existing cuts are carried forward once as editable markers. Old lyrics, corrections, split lineage, review state and original analysis remain preserved. Existing proposed scenes are not treated as newly created scenes: use Create Scenes explicitly.
- **Import Stage 1** reuses a completed analysis without repeating separation.

PowerShell alternative:

```powershell
Set-Location D:\ComfyMax-Audio-Chunker
powershell -NoProfile -ExecutionPolicy Bypass -File .\launch-editor.ps1 -Project '.\projects\Rain-from-the-Skies.comfymax\project.json'
```

## Place and adjust markers

1. Use **Play/Pause** or Space. Click the waveform to seek. The whole-song overview moves the detailed view; Zoom +/− and Ctrl+mouse wheel change zoom. Ordinary mouse wheel pans the detailed timeline.
2. Switch **Full Mix / Vocals** at any time. The two audio sources share one sample clock. Switching uses the existing playback stream without seeking or restarting; paused position also stays unchanged. The next audio callback uses the new source, subject to normal device buffering.
3. Press **Place Marker at Playhead** or **M**. This works during playback without stopping it. Song start and song end are fixed, so the full song is always covered.
4. Drag an amber marker line, or select a marker, enter an exact time in seconds and press **Move Marker**. Delete removes an interior marker only. Markers may cross one another and are kept in time order; duplicate positions are rejected.
5. Select a marker and use **Audition Around Marker**, or double-click its table row. Before/after context is configurable. Loop audition repeats that range; Escape stops playback. To resume whole-song playback outside an audition, seek outside its range.

The marker list displays exact timestamps and the duration to the next boundary. Times are displayed to six decimal places; the sample index and additional precision are in the timestamp tooltip. Marker positions are stored as integer samples on the playback timeline. Intervals above 15 seconds are red and labeled **OVER 15 SECONDS**. They are warned about, not automatically split or moved.

## Create Scenes explicitly

Marker edits do not create scenes. Press **Create Scenes** when ready. Each consecutive pair of boundaries becomes one scene, including the intervals from song start and to song end. The Scenes tab lists number, start, end, duration, Type and any over-15-second warning. The interval's Vocal/Instrumental type is copied at creation time.

## Vocal / Instrumental interval types

The **Type** dropdown next to **Interval to next marker** applies to the interval AFTER that row's boundary. For example, the Start row controls Start → first marker. The final End row has no following interval, so it has no Type dropdown. Markers themselves remain time positions only.

Choose **Vocal** or **Instrumental** directly in the table. Changes support undo/redo and autosave. They do not move markers, change durations, modify audio, seek or stop playback. If scenes already exist, changing a type marks them out of date until you explicitly press Create Scenes again.

When a vocal stem is available, initial suggestions come from its detected energy relative to the full mix. The detector uses 50 ms windows, an absolute/relative energy threshold and a stem-to-mix ratio; an interval is suggested Vocal when at least 10% overlaps detected vocal activity. This is a convenience, not a semantic guarantee: bleed can look vocal and quiet vocals may be missed. Hover over a dropdown to see whether its value is suggested or manual. Choosing a dropdown value, even the current one, makes it a manual choice. Without a vocal stem, new intervals default to Vocal and remain editable. There are no lyric dependencies or extra model downloads.

Unchanged intervals keep their saved types. Splitting a manually typed interval carries that choice to both parts. When moving/deleting markers changes interval coverage, the manual type with the largest overlap is retained; ties choose the earlier interval. If there is no overlapping manual choice, the changed interval receives a new suggestion. Manual choices survive reopening and are never replaced merely because audio is analyzed again. Review the type after combining differently classified intervals.

Types are stored as interval records with start/end sample bounds and provenance, independently of marker time values. Created scenes have their own copied types. Created scene types are included as metadata in `scenes.json`; all audio comes from vocals.

Use **Back to Markers** to make changes. Previously created scenes remain visible but are clearly marked out of date; their playback is disabled until **Create Scenes Again** replaces them with the current intervals. No automatic proposal algorithm runs. Undo/Redo includes both marker edits and explicit scene creation.

**Export Scenes** exports the explicitly created, current scene timestamps: all scenes use Demucs vocals; Vocal/Instrumental is metadata only. Choose an output folder to create a unique subfolder with sequential WAV files and `scenes.json`. Every scene must be at most 15 seconds. See **EXPORT_SCENES.md** for validation and format details. The source song and proxies are never overwritten.

## Optional transcript and saving

**Show transcript** opens a read-only listening aid using existing corrected text when available. Double-click a transcript row to hear it. Transcript timestamps, text and review states do not control markers or scene creation. No lyric correction, splitting or approval is required.

Edits autosave after a short pause. Save, Save As, atomic recovery and single-writer project protection remain available. Save As creates a new folder and copies the playback assets. The marker state and the last explicitly created scene snapshot are separate project fields; this prevents silent scene regeneration. Original legacy evidence is preserved in the project.

## Validation

69 automated tests passed, covering the marker model, interval type dropdowns, suggestions, manual override preservation, type inheritance after marker edits, migration of older projects, scene snapshots, undo/redo, autosave/recovery, unchanged timings/audio, plus existing project and Stage 1 checks.

The interval-type acceptance test used a separate copy of the saved Rain scene project: 25 intervals received 15 Vocal and 10 Instrumental initial suggestions. A real keyboard change in the dropdown was tested, then undone/redone, saved, reopened in a new editor instance and used to recreate scenes. All marker positions, durations, audio assets, original lyric data and the user's source project remained unchanged. The test-only override is not a recommendation for the song.

The complete Rain song was tested on a separate project copy: manual placement, numeric movement, waveform dragging, deletion, audition, real-device source switching, explicit Create Scenes, stale-scene handling, scene audition, optional transcript and reopen. Test markers were deliberately chosen to exercise controls, not as proposed or approved segmentation. The source project and lyrics/regions remained unchanged. The new Load Song path was also exercised separately on the complete Rain MP3.

The rendered interface was visually inspected. Final marker placement and listening approval remain the user's decision. The final export acceptance test produced 25 verified WAV files on a separate Rain project copy: 15 Vocal and 10 Instrumental, covering all 9,231,508 frames at 44,100 Hz stereo. Every exported sample matched its selected source. Test classifications were stem suggestions, not user approval.

## Dark appearance and waveform navigation

The editor follows ComfyMax’s dark Streamlit palette: charcoal panels, light text, rounded controls and red accents. The wide-handled horizontal slider directly below the detailed waveform pans the visible window without seeking audio or editing markers. Zoom controls the window width; Fit song disables scrolling. Overview navigation and zoom keep the slider synchronized.

The September 17 export revision uses vocals for every scene, preserving type only as metadata. Existing exports are not rewritten.
