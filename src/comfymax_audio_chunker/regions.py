"""Reviewable vocal activity estimates, independent of model APIs."""
import numpy as np


def merge_intervals(intervals, duration, gap=0.0, padding=0.0):
    merged = []
    for start, end in sorted(intervals, key=lambda interval: (interval[0], interval[1])):
        start, end = float(start), float(end)
        start, end = max(0., start-padding), min(duration, end+padding)
        if end <= start:
            continue
        if merged and start <= merged[-1][1] + gap:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def partition(intervals, duration):
    """Cover the entire decoded timeline exactly once, including intro/outro."""
    result, cursor = [], 0.
    for start, end in merge_intervals(intervals, duration):
        if start > cursor:
            result.append(dict(start=cursor, end=start, kind="instrumental"))
        result.append(dict(start=start, end=end, kind="vocal"))
        cursor = end
    if cursor < duration:
        result.append(dict(start=cursor, end=duration, kind="instrumental"))
    for r in result:
        r.update(duration=r["end"]-r["start"], estimated=True, needs_review=True)
    return result


def activity(vocals, mix, sr, floor_db=-48., relative_db=-30., ratio_db=-22.):
    """50 ms RMS over both channels (avoids anti-phase mono cancellation).

    Detect energy in the isolated stem relative to its peak and the full mix.
    Not a semantic singing detector: bleed can be active, quiet vocals missed.
    """
    hop = max(1, round(sr * .05))
    def rms(x):
        return np.array([np.sqrt(np.mean(np.square(x[i:i+hop], dtype=np.float64)))
                         for i in range(0, len(x), hop)])
    v, m = rms(vocals), rms(mix)
    db = 20*np.log10(np.maximum(v, 1e-10))
    ratio = 20*np.log10(np.maximum(v, 1e-10)/np.maximum(m, 1e-10))
    threshold = max(floor_db, float(np.max(db)) + relative_db)
    mask = (db > threshold) & (ratio > ratio_db)
    edges = np.diff(np.r_[False, mask, False].astype(int))
    intervals = [(a*hop/sr, min(b*hop/sr, len(mix)/sr))
                 for a,b in zip(np.where(edges == 1)[0], np.where(edges == -1)[0])]
    intervals = merge_intervals(intervals, len(mix)/sr, gap=.25)
    intervals = [(a,b) for a,b in intervals if b-a >= .20]
    intervals = merge_intervals(intervals, len(mix)/sr, padding=.12)
    return intervals, dict(frame_seconds=hop/sr, threshold_db=threshold,
                           floor_db=floor_db, relative_db=relative_db, ratio_db=ratio_db,
                           bridge_gap_seconds=.25, minimum_seconds=.20, padding_seconds=.12)


def overlap_fraction(start, end, intervals):
    if end <= start:
        return 0.
    return sum(max(0., min(end,b)-max(start,a)) for a,b in intervals)/(end-start)


def phrases(words, pause=.65):
    """Candidate phrase groups; Whisper punctuation is not a guaranteed boundary."""
    result, current = [], []
    def emit():
        if current:
            result.append(dict(start=current[0]["start"], end=max(w["end"] for w in current),
                               text="".join(w["word"] for w in current).strip(),
                               needs_review=True, word_ids=[w["id"] for w in current]))
    for word in words:
        if word["suspect"]:
            emit(); current=[]
            continue
        if current and (word["start"]-current[-1]["end"] >= pause or
                        current[-1]["word"].rstrip().endswith((".", "!", "?", "。", "！", "？"))):
            emit(); current=[]
        current.append(word)
    emit()
    return result
