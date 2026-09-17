"""Sample-bounded playback; the UI follows the device clock, not a timer."""
from collections import deque
from dataclasses import dataclass
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf


@dataclass
class Cursor:
    start: int
    end: int
    frame: int
    loop: bool = False

    def render(self, source, output):
        output.fill(0)
        offset = 0
        while offset < len(output):
            if self.frame >= self.end:
                if self.loop and self.end > self.start:
                    self.frame = self.start
                else:
                    break
            n = min(len(output)-offset, self.end-self.frame)
            output[offset:offset+n] = source[self.frame:self.frame+n]
            self.frame += n
            offset += n
        return offset


def load_audio(document):
    arrays, peaks = {}, {}
    for key, asset in document.data['assets'].items():
        wave, rate = sf.read(document.root / asset['path'], dtype='float32', always_2d=True)
        if not np.all(np.isfinite(wave)):
            raise ValueError(f'{key} audio contains invalid samples')
        arrays[key] = np.ascontiguousarray(wave)
        # Preserve both channels' extrema, including anti-phase stereo.
        block = 256
        count = (len(wave)+block-1)//block
        padded = np.pad(wave, ((0, count*block-len(wave)), (0,0)))
        groups = padded.reshape(count, block, wave.shape[1])
        peaks[key] = (groups.min(axis=(1,2)), groups.max(axis=(1,2)), block/rate)
    return arrays, peaks


class Transport:
    def __init__(self, arrays, rate):
        self.arrays, self.rate = arrays, rate
        self.total = len(arrays['mix'])
        self.source = 'mix'
        self.volume = .7
        self.stream = None
        self.cursor = Cursor(0, self.total, 0)
        self.anchors = deque(maxlen=1024)
        self.guard = threading.Lock()
        self.parked = 0
        self.active = False
        self.warning = ''

    def _callback(self, output, frames, timing, status):
        with self.guard:
            c = self.cursor
            self.anchors.append((timing.outputBufferDacTime, c.frame, c.start, c.end, c.loop, frames))
            c.render(self.arrays[self.source], output)
            np.multiply(output, self.volume, out=output)
            np.clip(output, -1., 1., out=output)
            if status:
                self.warning = str(status)

    def position(self):
        if not self.active or self.stream is None:
            return self.parked
        now = self.stream.time
        with self.guard:
            anchors = list(self.anchors)
        candidates = [a for a in anchors if a[0] <= now]
        if not candidates:
            return self.parked
        when, frame, start, end, loop, length = candidates[-1]
        elapsed = min(length, max(0, int((now-when)*self.rate)))
        if loop:
            return start + (frame-start+elapsed) % (end-start)
        return min(end, frame+elapsed)

    def halt(self):
        self.parked = self.position()
        self.active = False
        if self.stream is not None:
            old, self.stream = self.stream, None
            old.abort()  # Flush queued samples before a seek/source change.
            old.close()

    def play(self, start, end, position=None, loop=False):
        start, end = max(0, int(start)), min(self.total, int(end))
        if start >= end:
            return
        self.halt()
        position = start if position is None else max(start, min(int(position), end-1))
        self.cursor = Cursor(start, end, position, loop)
        self.parked = position
        self.anchors.clear()
        self.warning = ''
        try:
            self.stream = sd.OutputStream(samplerate=self.rate, channels=2, dtype='float32',
                                          blocksize=512, latency='low', callback=self._callback)
            self.active = True
            self.stream.start()
        except BaseException:
            self.halt()
            raise

    def pause(self):
        self.halt()

    def resume(self):
        c = self.cursor
        self.play(c.start, c.end, self.parked if self.parked < c.end else c.start, c.loop)

    def seek(self, frame):
        was_active = self.active
        c = self.cursor
        self.halt()
        self.parked = max(0, min(self.total, int(frame)))
        # Seeking outside an audition changes to the full song; no hidden jump back.
        if not c.start <= self.parked < c.end:
            self.cursor = Cursor(0, self.total, self.parked, c.loop)
        if was_active and self.parked < self.total:
            self.resume()

    def switch(self, source):
        if source not in self.arrays or source == self.source:
            return
        # Both arrays share the exact sample clock. Switch on the existing
        # callback stream without seeking, flushing, or restarting playback.
        with self.guard:
            self.source = source

    def set_loop(self, enabled):
        # Rebuild from the audible frame so queued old loop state is flushed.
        was_active = self.active
        self.halt()
        self.cursor.loop = enabled
        if was_active:
            self.resume()

    def poll(self):
        pos = self.position()
        if self.active and not self.cursor.loop and pos >= self.cursor.end:
            self.halt()
            self.parked = self.cursor.end
        return pos
