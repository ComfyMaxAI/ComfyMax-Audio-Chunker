# Scene proposals and manual chunk editing

**Historical workflow — superseded.** The current application uses manual markers and explicit Create Scenes without proposals or lyric approval. See MARKER_EDITOR.md. The following describes the earlier implementation.

**Workflow update:** lyrics must first be corrected, split as needed, individually reviewed, then explicitly marked **Lyrics Review Complete**. See LYRICS_PREPARATION.md. Existing proposals remain historical until regenerated against the completed review. Further scene-editor expansion is paused.

Close any previously running editor, then launch `D:\ComfyMax-Audio-Chunker\Launch Editor.cmd`.

Open `D:\ComfyMax-Audio-Chunker\projects\Rain-from-the-Skies-scenes.comfymax\project.json` for the saved 24-scene proposal. This copy includes your saved lyric corrections. Your existing Rain project remains unchanged; it can also generate its own proposals using the Scenes tab.

## Use the Scenes tab

- **Generate proposals / Regenerate Proposals** builds a full-song segmentation. Regeneration asks before replacing your manual cuts and can be undone.
- Each scene lists its number, start, end, duration, associated current corrected lyrics and warnings. Hover over lyrics to read the full text. Detected vocal sections without text say **Vocal — no transcript**, rather than being mislabeled Instrumental.
- Select a row, then **Play Scene**, or double-click it. **Previous Scene / Next Scene** select and play their scene. Enter in the scene table or Ctrl+Enter in the Scenes tab also plays it. Loop and Full mix/Vocals use the existing transport. Scene playback uses exact scene boundaries, without phrase context padding.
- The amber **scene lane** is below detected regions and transcript phrases. Click a scene block to select it. Click a cut marker to select that cut; drag it to move it. Phrase timestamps and detected regions never move with a cut.
- Selecting a scene selects its ending cut, unless it is the final scene. Set the seconds field and choose **Move Cut**, or use **Delete Cut** to merge its neighboring scenes. Song start/end are fixed. Moves cannot cross neighboring cuts.
- To add a cut, enter a position or seek on the waveform and choose **Use playhead**, then **Add Cut**. Positions are rounded to the nearest audio sample.
- Undo/Redo share the existing edit history. All cut changes autosave and survive project reopen, recovery and Save As. Regeneration is explicit: correcting lyric text updates scene labels without silently moving cuts.

Manual edits may create scenes longer than 15 seconds. These are highlighted red, labeled **OVER 15 SECONDS**, and counted below the table. Cuts inside timed lyric phrases and scenes under 5 seconds are also flagged. No audio export is provided in this milestone.

## Proposal rules

Instrumental spans divide evenly into a count near duration / 5.5 seconds. This avoids unnecessarily short remainder scenes; exact 5–6 seconds is not always possible. Vocal proposals never exceed 15 seconds. The proposal planner strongly favors nonblank current lyric phrase starts/ends over arbitrary positions, with duration preferences around 10 seconds and a penalty below 5 seconds. Corrected empty text is respected.

Detected vocal spans and current nonblank lyric spans identify activity. Gaps shorter than 3 seconds are grouped for proposal planning so breaths and detector dropouts do not create tiny scenes; the original detected region lane is unchanged. Instrumental/vocal transitions remain candidates only outside reviewed phrases. Reviewed phrases are indivisible, though adjacent phrases may share a scene. Phrases over 15 seconds block review completion until manually split. The generator refuses any segmentation that would require a reviewed phrase to be split. Original word timings are not reassigned to corrected words.

Scene cuts are stored separately in `chunk_boundaries` as sorted integer positions in the project's sample clock. Scene rows and associated text are derived from those cuts. They are not transcript or region boundaries.

## Rain from the Skies result

24 scenes cover all 209.331247 seconds with no gaps or overlap. Maximum duration: 14.620 seconds. There are no cuts inside a nonblank timed transcript phrase. The intro has four 5.920-second scenes, the interlude four 4.980-second scenes, and the outro two approximately 4.956-second scenes. The six slightly-under-5-second scenes carry informational warnings. Scene 22 (193.540–199.420) contains detected vocals without transcript and needs listening review.

Existing Whisper rows sometimes end midway through a sung sentence. Preserving their boundaries cannot guarantee a musical phrase ending; audition and manual cut movement remain essential. No subjective claim of full-song listening approval is made.

## Verification

33 automated regression tests cover proposals, phrase integrity, overlong phrases, detector dropouts, balanced instrumentals, sample roundoff, invalid cuts, and the existing correction/audio/project workflows.

The separate complete-song GUI acceptance test generated all proposals, verified every scene's samples against both playback sources, checked Play/Previous/Next, numeric add/move, marker dragging, delete, undo/redo, regeneration cancellation/replacement, over-15-second warnings, autosave and reopen. All phrase data, original analysis, detected regions and the source project remained unchanged. Brief device playback checks passed for scenes 1, 5, 13, 21 and 24 on Main Out 1/2 (Studio 24c), including source switching and loop bounds. The editor layout was rendered and inspected.

Run regression tests in PowerShell:

```powershell
Set-Location D:\ComfyMax-Audio-Chunker
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The future New Song workflow and audio export remain deferred.
