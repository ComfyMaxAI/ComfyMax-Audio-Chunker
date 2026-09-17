# ComfyMax Audio Chunker — Stage 2 design

## Purpose and scope

Build an interactive **Lyrics + Audio Alignment Editor**: listen, compare, correct and review before proposing scene cuts. The waveform and its playhead are the shared reference for every view. The original mix is the default listening source; isolated vocals are an optional listening aid.

Stage 1 is approved as the starting point. This document is the Stage 2 design, not a GUI implementation. Automatic chunk generation, scene export and forced lyric alignment are deferred. No existing analysis or audio is modified by this design work.

## One practical window

```text
ComfyMax Audio Chunker — Rain from the skies            Open   Save

[Play/Pause] [Replay phrase] [Previous] [Next] [Loop]
Full mix / Vocals       01:08.240 / 03:29.331
Context: before [0.5 s] after [0.5 s]       Saved

Whole-song overview: [=========== current view ================]
Time ruler:          0:50          1:00          1:10
WAVEFORM             ~~~~~~~ shared playhead and selection ~~~~~
Detected regions:    [Vocal........][Instrumental][Vocal.......]
Transcript spans:    [phrase 8][phrase 9........][phrase 10.....]
                     Zoom − / + / Fit       Adjust timing [off]

TRANSCRIPT                                      KNOWN LYRICS [optional]
Play  Start       End         Text / status      Paste or load text
 ▷    01:07.120   01:20.060   my cheek all I…     [Reference text…]
 ▷    01:20.060   01:27.920   still and you…      [Apply selection
                                                  to selected phrase]
SELECTED PHRASE
Whisper original: [read-only text]
Your correction:  [editable text, several lines if needed]
[Mark reviewed] [Restore original] [Mark as non-lyric]
```

The waveform stays visible while the transcript scrolls. Give it roughly the upper third of the working window, with draggable panel dividers. Hide the reference pane by default; opening it shares the lower area without shrinking the waveform. Use ordinary controls, readable text, restrained colors and text labels in addition to color. Avoid decorative panels, animations and nested toolbars.

The selected phrase is shaded on the waveform; lighter shading shows playback context. Detected vocal/instrumental regions and transcript spans occupy separate lanes. Instrumental spans retain labels and shading even when there is no text. Thin boundaries remain visible at any zoom; small regions gain labels or details on hover/selection.

Reserve a separate timeline marker lane for future scene cuts. It is hidden while empty. Phrase bounds, detected region bounds and future scene cuts are distinct objects and must never be confused.

## Main interaction

1. **Open a Stage 1 analysis or saved editor project.** Load the waveform, every Whisper transcript segment, word diagnostics and detected regions. Do not rerun the models.
2. **Click a phrase row or its timeline span.** Select it, reveal it in the waveform and immediately play that phrase with context. The explicit play icon does the same. Keyboard navigation selects without unexpectedly playing; Enter plays the selected phrase.
3. **Listen and correct.** Type in the correction field while the original stays visible. Typing, changing punctuation or pasting a different number of words never changes the phrase's start/end times.
4. **Replay or loop.** Replay always starts at the selected phrase's context start, regardless of the current playhead. Loop repeats the same bounded interval until stopped or another phrase is selected.
5. **Mark reviewed and move on.** Review is an explicit user action, not an inferred consequence of typing. The next/previous controls select and audition the adjacent transcript phrase; instrumental gaps remain on the timeline.

Clicking inside the correction field only positions the text cursor; it must not restart audio. Text selection, reference selection and timestamp editing likewise do not trigger playback. Keep the selected editing phrase stable during playback; use a separate subtle indicator for the phrase under the playhead. Optional “Follow playback” scrolls only when enabled and pauses while the user edits.

## Playback rules

| Control | Behavior |
| --- | --- |
| Context before/after | Separate values, default 0.5 seconds each, range 0–3 seconds; saved per project |
| Phrase playback | Play from `max(0, start − before)` to `min(song duration, end + after)` |
| Play/Pause | Resume or pause the current playback operation; preserve position |
| Replay phrase | Restart the selected phrase with its current context |
| Timeline click | Seek; continue if playing, remain paused if paused |
| Timeline drag | Select an audition range; does not move phrase boundaries |
| Loop | Repeat the selected phrase or manually selected audition range |
| Full mix / Vocals | Preserve time and selection; stop/flush old audio before resuming the other source |
| Space | Play/pause only when focus is outside text/time inputs; typing spaces remains normal |
| Ctrl+Enter | Replay selected phrase even while editing text |
| Escape | Stop playback/loop without discarding text |
| Ctrl+S / Ctrl+Z / Ctrl+Y | Save / undo / redo, with text-editor undo taking precedence while typing |

Show progress/loading errors without freezing the controls. Rapidly clicking several phrases must leave only the last one playing. Stop playback at the audio engine's scheduled end sample; do not depend on a visual timer to enforce the end. At the end, leave the playhead at the playback end rather than jumping to the next phrase automatically.

Use the existing `analysis_mix.wav` as the full-mix playback proxy: it is the complete mix decoded for analysis, not the vocal stem. The existing `vocals.wav` shares that timeline. Both must have their sample rate and frame count validated on import. Keep the original source file path and hash for provenance and later export. Do not use the MP3 listening preview for alignment; avoid decoder delay and seeking inconsistencies between files.

## Corrections and timing

**Default: timing locked.** Display timestamps to milliseconds, but retain the original imported precision in saved data. A text-only change must leave both stored endpoints exactly unchanged. An empty correction is a deliberate blank; it is different from “no correction.” Restore Original removes the correction override and is undoable.

Word timestamps describe the original Whisper words. After changing the text, show **“Phrase timed; corrected words not individually aligned.”** Do not redistribute old word timestamps across new words or display misleading word-by-word highlighting. Original word timings remain inspectable as evidence.

**Adjust timing** is an explicit mode. It exposes draggable start/end handles and editable time fields. Changes affect only that phrase, never neighboring phrases or detected regions. Require `0 ≤ start < end ≤ duration`; reject invalid field values and constrain dragging. Show overlaps as review warnings without silently pushing other phrases, since sung parts may overlap. Timing changes clear the phrase's reviewed status. Undo and “Restore imported timing” restore earlier endpoints.

Manual phrase split/join follows the core correction workflow within Stage 2. Split at the playhead only inside the selected phrase; ask the user to divide the corrected text rather than guessing which new word owns which timestamp. Join selected adjacent transcript rows with explicit confirmation if a time gap lies between them; no audio is removed. Retain source segment IDs and original text for all descendants. These actions organize lyrics, not scenes, and are not required to begin the first correction/playback milestone.

“Mark as non-lyric” dismisses hallucinated text from the normal phrase list without deleting it. A “Show dismissed” option restores visibility and offers undo. It does not relabel the audio region. Missing vocals can be added as a manually timed phrase from a waveform selection; that phrase has no Whisper original. Detected regions remain visible independently, including a “Vocal — no transcript” indication where appropriate.

## Known original lyrics

The optional pane accepts paste or a UTF-8 text file. Preserve line breaks, repeated choruses and Unicode. Keep it clearly labeled **Reference lyrics — not aligned**.

Users can select reference text and choose **Apply to selected phrase**. This replaces only that phrase's correction, retaining its timestamps, and can be undone. It never bulk-replaces the transcript or pretends that one reference line equals one timed phrase. For repeated lines, the user chooses the intended occurrence.

Keep reference text independent from both the original transcript and phrase corrections. Replacing reference lyrics later does not change existing corrections. Basic search and side-by-side reading are sufficient initially; automatic matching, lyric synchronization and forced alignment are later features.

## Project data: original plus editable working copy

Create a new project folder containing:

```text
Song.comfymax/
  project.json               editable state, settings and asset references
  source/analysis.json        exact immutable copy of the Stage 1 result
  audio/analysis_mix.wav      copied playback proxy
  audio/vocals.wav            optional copied vocal stem
  cache/waveform-peaks.*      disposable, regenerable display data
  recovery/                  last good save and recovery state
```

Copy the Stage 1 proxies by default for portability; the original mix itself remains at its original location and is identified by hash. The project remains playable if the original MP3 moves. Relocating the original requires a matching hash; a different file is a new source, not a silent replacement. If a proxy is missing, show a clear relink/rebuild action, never play another file under the same timestamps without checking it.

`project.json` has a separate project schema version, project UUID, save revision, source hash, analysis snapshot hash, asset paths, the authoritative timeline, editable phrases, reference lyrics and playback/view settings. Store asset paths relative to the project where possible. Saving or reopening does not rewrite the immutable analysis snapshot.

Each editable phrase contains:

| Field | Meaning |
| --- | --- |
| `id` | Stable UUID, independent of row order |
| `source_segment_ids`, `source_word_ids` | References into the immutable Stage 1 snapshot; may be empty for manual phrases |
| `imported_start`, `imported_end` | Original editor-import boundaries; immutable |
| `start`, `end` | Current boundaries in seconds from the first decoded sample |
| `original_text` | Initial editor-row text; source snapshot remains authoritative |
| `corrected_text` | `null` means original; `""` means intentionally empty |
| `origin` | Imported segment, manual, split or joined |
| `review_status` | Unreviewed or reviewed; separate from model confidence |
| `dismissed` | Reversible non-lyric flag |
| `word_alignment_status` | Original-word estimates or phrase-only after edits |
| `parent_phrase_ids` | Lineage for split/join without overwriting source evidence |

Stage 1's `segments` initialize the editing rows, with their complete text and timestamps. Its `phrases` are filtered suggestions and must not be the only import source: doing so would discard uncertain opening words already encountered in the real-song test. Preserve all original segments, words, confidence values, regions and phrase candidates in the snapshot, including zero-duration or malformed entries as flagged source evidence. Rows without a valid playable span require manual timing before audition; do not invent one.

Text edits mark the row edited and unreviewed but do not affect timing. User review does not change the model's confidence values. Keep detected regions immutable in the snapshot; future region corrections, if added, are a separate override layer. A future `chunk_boundaries` collection starts empty and is independent of all phrase edits.

## Saving and failure behavior

Autosave after a short typing pause and at committed timing edits. Show Saving / Saved / Save failed plainly. Write a validated temporary project file and atomically replace the working file; retain the last good save. Failed saves keep edits in memory and offer retry or Save As. Never display “Saved” after a failure.

Undo/redo covers text, timing, dismissal, pasted-reference application and phrase structure. Original source evidence remains available after reopening even when session undo history is no longer available. On close with pending or failed saves, offer Save, Discard or Cancel. Recovery after a crash must prefer the latest valid revision and identify recovered edits. Prevent simultaneous writers from silently overwriting each other.

Rerunning Stage 1 creates a new analysis/project version. It must not overwrite corrections in an existing project. Reconciliation across model runs is outside the first editor release.

## Implementation sequence

1. **Project import and reliable audition:** load/save project, waveform overview/detail, full-mix/vocal switch, all transcript rows, detected regions, click-to-play, context and loop.
2. **Comfortable correction:** original/corrected comparison, reference pane, keyboard behavior, review status, undo and autosave/recovery.
3. **Manual alignment:** explicit timing adjustment, manual missing-phrase creation, dismissal, then split/join.
4. **Acceptance on the supplied song:** only after this editor workflow is comfortable should automatic chunk proposals be designed and implemented.

Keep the UI, project document, audio transport and waveform cache as separate components. Audio and expensive waveform work run outside the UI event loop. The UI reads the audio engine's playback clock; it must not run an independent drifting playhead timer. Opening an existing project needs no models, GPU or network. Continue using the standalone project and its dedicated Python environment; do not attach to ComfyUI. Toolkit and packaging choices can be finalized during implementation without changing this interaction/data contract.

## Acceptance checks before automatic chunking

- Open the complete 3:29 Rain from the skies analysis; the intro, middle instrumental passage, outro and every original transcript segment remain accessible.
- Click phrases at the beginning, middle and end. They play the chosen source with configurable context, clamped at song bounds; loop and rapid selection changes behave predictably.
- Correct several lines, including changing their word counts. Save/reopen and verify unchanged numeric timestamps, unchanged source-analysis hash and preserved original text.
- Paste known lyrics, apply selected text to one phrase, undo it, replace the reference, and verify that no unrelated phrase changes.
- While typing spaces, cursor keys and newlines, playback does not start or seek unexpectedly. Selecting another phrase commits the current edit safely.
- Inspect instrumental regions while no phrase is selected and while filtering the transcript. They remain visible; no lyrics are invented for them.
- Adjust one timestamp deliberately, undo it, and verify no other phrase or region moved. Test invalid values and genuine overlapping phrases.
- Simulate a save failure and recovery; no last-good project or original transcription is lost.
- Compare scheduled playback boundaries with the decoded PCM timeline, and verify the displayed playhead has no accumulating drift. Account for device latency separately; timestamp display precision is not proof of audible alignment.

The acceptance target is a dependable human review tool. It does not require perfect automatic lyrics, perfectly detected phrases or scene-length decisions.
