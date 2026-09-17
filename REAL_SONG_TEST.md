# Rain from the skies — Stage 1 real-song test

**Result: the local pipeline completes successfully. Listening approval and phrase-timing validation remain pending. Stage 2 has not started.**

Source: `C:\Users\danie\Downloads\Rain from the skies 2rain from the skies.mp3`

Final run: `D:\ComfyMax-Audio-Chunker\runs\rain-from-the-skies-small-final`

## Verified results

| Item | Result |
| --- | --- |
| Decoded duration | 3:29.331 (209.331247 seconds) |
| Vocal isolation | Demucs htdemucs, RTX 5060 Ti / CUDA |
| Transcription | faster-whisper small, English, CPU int8 |
| Network | Final run used cached models with offline mode |
| Processing time | 35.9 seconds, excluding prior installation/downloads |
| Word entries | 235, including 13 flagged as suspect |
| Phrase candidates | 16 |
| Vocal/instrumental regions | 15, covering the full decoded timeline continuously |
| Source preservation | SHA-256 identical before and after |
| Automated tests after fixes | 9 passed |

Original SHA-256: `00eb2d530720d0fbcade164e20db625d6619a9c88c156a092cd97a9baaea4df9`.

The vocal stem and analysis mix have identical frame counts and duration. All reported region, word, segment and phrase timestamps are finite and within the song. These checks establish structural integrity, not perceptual accuracy.

## Main estimated instrumental spans

| Start | End | Duration |
| --- | --- | --- |
| 0:00.000 | 0:23.680 | 23.680 seconds |
| 1:47.820 | 2:08.180 | 20.360 seconds |
| 3:19.420 | 3:29.331 | 9.911 seconds |

Several shorter gaps are also recorded. “Instrumental” means no detected vocal activity; silence is included. These are estimates, not approved scene boundaries.

## Findings requiring review

- Phrase candidates are still coarse. Two spans are about 19.06 and 28.74 seconds long. This stage has deliberately not forced them into 5–15 second chunks. They need listening review and potentially better phrase segmentation before automatic cut proposals can be trusted.
- Some plausible opening words are low confidence and excluded from phrase candidates. They remain visible in the full segment/word transcript. A phrase candidate may therefore start after the true beginning of a sung line.
- The final small-model run produced “the” at the start and “You” at the end. Both are flagged as suspect and do not create vocal regions.
- Small and medium models disagree on several lyrics. Medium did not consistently improve the transcript; intermediate runs included substitutions such as “cheese” for “cheek.” The medium comparison files are retained in `runs\rain-from-the-skies-medium-03`, using the earlier, stricter confidence filter. They are diagnostic comparisons, not the final recommended output.
- Runs varied in some words and brief detected stem activity. Demucs separation and Whisper results are not guaranteed to be bitwise repeatable. The recorded Torch seed is not a guarantee of complete determinism.
- No independent auditory review or reference-lyric alignment was performed by the assistant. The supplied listening preview is for your review. A numerical accuracy score would be unjustified without ground truth.

## Fixes made from this real-song test

1. Vocal activity intervals were lists, while word intervals were tuples. Sorting their combined list failed. Sorting now uses the numeric endpoints explicitly.
2. A numeric-library Boolean in segment flags prevented JSON serialization. Flags and interval endpoints now use standard Python types.
3. High speech-oriented `no_speech_prob` values were incorrectly excluding clearly supported singing from phrase grouping. This metric remains in the report, but a high value alone no longer rejects a segment. Poor decoding, repetition, acoustic support and word confidence still affect suspect flags.

Regression tests cover mixed interval types and the recognized-word-to-JSON path, including high no-speech scores on acoustically supported vocals.

## Review files

- `Rain-from-the-skies-analysis.txt`: readable final report.
- `Rain-from-the-skies-analysis.json`: final structured analysis; its artifact filenames refer to the original run directory above.
- `Rain-from-the-skies-vocals-review.mp3`: compressed listening preview of the isolated vocals. The uncompressed float WAV is retained as `vocals.wav` in the final run folder. This preview is not a scene export.

Listen especially at the first entrance around 0:24, the transition around 1:47–2:08, the sustained/repeated outro vocals, and the long phrase candidate around 1:08–1:37. Decide whether the analysis is useful enough or whether phrase detection needs another Stage 1 iteration before approving Stage 2.

## Repeat this test

```powershell
Set-Location D:\ComfyMax-Audio-Chunker
powershell -NoProfile -ExecutionPolicy Bypass -File .\analyze.ps1 -Song "C:\Users\danie\Downloads\Rain from the skies 2rain from the skies.mp3" -Model small -Language en -Offline
```

This creates a new timestamped run and does not overwrite the existing results.
