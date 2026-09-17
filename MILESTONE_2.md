# Stage 2 milestone 2 — Comfortable correction

## Launch

Close any previously running editor, then double-click `D:\ComfyMax-Audio-Chunker\Launch Editor.cmd`. Choose **Open project** and select `D:\ComfyMax-Audio-Chunker\projects\Rain-from-the-Skies.comfymax\project.json`.

Alternatively, in PowerShell:

```powershell
Set-Location D:\ComfyMax-Audio-Chunker
powershell -NoProfile -ExecutionPolicy Bypass -File .\launch-editor.ps1 -Project '.\projects\Rain-from-the-Skies.comfymax\project.json'
```

The existing dedicated Python 3.11 environment includes the required editor dependencies. No new dependencies are needed for milestone 2. On a fresh installation, run `setup.ps1`, which also installs the editor dependencies.

## Correct lyrics while listening

1. Click a transcript row to audition the phrase with the configured before/after context. Full mix/vocals switching, looping, waveform navigation and instrumental regions remain available.
2. Compare **Whisper original — preserved** with **Your correction**. Edit the right-hand field. Every phrase's start/end and original word timestamps remain unchanged. The transcript table displays your correction immediately.
3. Press **Ctrl+Enter** to replay while typing. Spaces and Enter remain normal text input. **Escape** stops audio without discarding edits. Outside text/time inputs, **Space** toggles playback; **Enter** in the transcript table auditions the selected phrase.
4. Use **Mark Reviewed** once satisfied. Further text changes clear the review status. **Restore Original** removes the correction and returns to the original text; this action can be undone. An intentionally empty correction stays empty rather than falling back to Whisper text.
5. Enable **Reference Lyrics** to paste complete known lyrics or load a UTF-8 `.txt` file. Find text with the search field. Select only the desired words and click **Apply selection to selected phrase**. Reference text is unaligned; importing or editing it never automatically overwrites phrases.
6. Use **Undo/Redo** or **Ctrl+Z/Ctrl+Y** for corrections, reference edits, application of reference text, review and restore actions. Adjacent typing is grouped into useful undo steps. Undoing another phrase's change selects that phrase without starting playback. Undo history lasts for the current open session.

## Saving and recovery

Edits autosave after approximately 1.2 seconds without typing. **Ctrl+S** or **Save** saves immediately; the bottom status line reports saving, saved or failure. A complete recovery checkpoint is written before atomic replacement of the main manifest, and the previous valid manifest is retained as `recovery/last-good.json`.

On reopen, the editor chooses the newest valid revision among the main manifest, pending checkpoint and last-good backup, and reports recovery. A failed save retains edits in memory. Retry **Save**, or use **Save As** to copy the project and its audio into a new folder. Existing folders are not overwritten. Closing or opening another project with unsaved changes offers Save, Discard or Cancel. Discard affects unsaved changes, not earlier successful autosaves. Only one editor can write a project at a time.

Keystrokes made after the last completed checkpoint can be lost if the process or computer stops suddenly. Recovery cannot repair missing or damaged audio assets. Original Stage 1 analysis and audio are never overwritten by correction commands.

## Validation on Rain from the Skies

All 26 automated tests passed, including correction undo/redo, keyboard behavior, intentional blank text, autosave, interrupted-save recovery, invalid-checkpoint fallback, Save As and close choices, plus the existing project/audio tests.

The real-song GUI acceptance test used a separate copy of the existing project: 22 transcript phrases, 235 original word entries and 15 detected regions. It exercised multiline correction, UTF-8 reference import, explicit selection application, review, restore, autosave/reopen and interrupted primary-save recovery. All original timestamps, source IDs, Whisper data and the user's source project remained unchanged. Test corrections were demonstration text, not verified original lyrics. The UI was rendered and inspected; this milestone's new correction workflow was tested through Qt automation, not a new subjective listening session.

Run the regression tests with:

```powershell
Set-Location D:\ComfyMax-Audio-Chunker
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Scope and future architecture

Corrected lyrics are phrase-timed only: corrected words are not automatically assigned the original Whisper word timestamps. Stage 1 timing inaccuracies are retained for later manual alignment work. Reference lyrics are optional and not matched automatically.

The project/document layer, audio transport and correction panel remain separate. The future single-application **New Song** entry point can run Stage 1 and pass its result into project creation; **Open Project** opens an existing document directly. That workflow, manual timing edits, automatic chunking and scene export are not built in this milestone.
