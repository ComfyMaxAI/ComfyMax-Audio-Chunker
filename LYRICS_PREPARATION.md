# Lyrics preparation before scene generation

**Historical workflow — superseded.** The current application uses manual markers without lyric approval. See MARKER_EDITOR.md. The following describes the preserved earlier implementation, not the current main interface.

Restart `D:\ComfyMax-Audio-Chunker\Launch Editor.cmd` after closing the old editor. Open your current Rain project and use the **Lyrics** tab. This update does not change your existing saved lyrics, mark them reviewed, or generate new scenes automatically.

## Correct, split, review

The Lyrics table now includes **Duration = End − Start** after the Start/End columns. Phrases over 15 seconds have a red row and an explicit warning. They must be split before review completion.

1. Select a phrase and correct its text in **Your correction**. Ordinary text edits leave timestamps unchanged.
2. Place the text cursor at the intended split position, then click **Split Phrase**. Use a single cursor position, not a selected range. Both resulting portions must contain text.
3. Choose the audio position independently. Click the waveform to seek and press **Use playhead**, or enter the song time in seconds. The purple dashed **Phrase split** marker previews that time. There is no automatic matching of corrected words to audio.
4. Use **Listen around split** to hear 1.5 seconds before/after the chosen time, limited to the parent phrase. Adjust until the musical/text boundary is right. The preview shows both resulting texts and durations.
5. Click **Confirm Split**. The first phrase keeps the parent's original start and ends at your time; the second starts there and keeps the parent's end. The shared split point is rounded to the nearest audio sample. Only an interior time is accepted.
6. Correct and **Mark Reviewed** each child independently. You can split a child again. Both children begin unreviewed even if the parent was previously reviewed. **Cancel** leaves the original phrase intact.

Undo/Redo include splitting, independent edits, review marks and whole-lyrics completion. Autosave, recovery, reopen and Save As preserve the children and their lineage. Undoing a split restores its parent, including the parent's corrected text and review status.

## Original evidence remains intact

The original Stage 1 snapshot and word timestamps are never rewritten. Each split archives the complete parent phrase and records the two new IDs, parent/root IDs, selected text offset and exact sample position. Child phrases retain original source IDs and imported bounds as evidence, not as a claim of word alignment. The left text pane shows the full original Whisper source text for either child; the right pane shows that child's independent corrected portion.

For a split child, **Restore Split Text** returns to the portion created at that split, rather than inserting the full parent's original transcript into a shorter interval. To restore the unsplit parent, undo the split. Corrected/split words have no invented word timestamps.

## Lyrics Review Complete

After reviewing every row, click **Lyrics Review Complete**. Intentionally blank corrections also require review. The action reports remaining unreviewed phrases, over-15-second phrases or unusable nonblank timing. Overlapping phrases whose indivisible span exceeds 15 seconds cannot be certified.

This completion applies to the exact current phrase texts, times, identities and individual review states. Later edits or splits reopen review and disable Generate/Regenerate Proposals. Undo back to the certified version restores completion. Reference lyrics are comparison material, so changes to that pane alone do not invalidate phrase review.

Existing scenes are preserved and labeled as belonging to an earlier lyric version. After completing review, explicitly regenerate. Reviewed nonblank phrases are indivisible vocal units: adjacent units can combine when suitable, but generation cannot cut inside them. Every generated scene is at most 15 seconds. Instrumental spans retain balanced approximately 5–6-second division. Existing manual scene controls remain unchanged; this update does not add scene-editor features or audio export.

## Rain validation

The complete 22-row saved Rain project was tested on a separate copy. A corrected phrase spanning 35.900–43.800 was split at a deliberately chosen test time of 39.500 into 3.600- and 4.300-second children. The test exercised cursor/time choice, listen-around wiring, independent correction/review/audition, undo/redo, autosave/reopen, source preservation and the review gate. Scene generation after simulated review produced no scene over 15 seconds and no cut inside any reviewed phrase.

That test time was chosen to test the controls; it is not a verified musical alignment or a user-approved split. Test-only review completion was not applied to your project. Your saved source project, original Whisper evidence and detected regions remained unchanged. The rendered GUI was inspected. The workflow was tested through Qt automation; final listening and lyric approval remain yours.

The regression suite has 41 passing tests, including Unicode cursor offsets, nested splits, recovery lineage, zero/overlong durations, review invalidation/restoration, exact 15-second phrases and combining adjacent reviewed phrases.

```powershell
Set-Location D:\ComfyMax-Audio-Chunker
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
