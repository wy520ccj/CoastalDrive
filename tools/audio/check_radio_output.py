"""用WASAPI回录真实OpenAL输出，核对选台后的声音而非仅检查句柄。"""

import argparse
import json
import sys
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import soundcard as sc

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from direct.showbase.ShowBase import ShowBase
from panda3d.core import loadPrcFileData

from simulation import Snapshot
from soundscape import Soundscape
from vehicle_state import CarState

RATE = 48000


def reference(name):
    path = ROOT / "assets/game/audio/music" / f"{name}.wav"
    with wave.open(str(path), "rb") as clip:
        values = np.frombuffer(clip.readframes(44100*5), dtype="<i2").reshape(-1, 2)
    mono = values.mean(axis=1) / 32768
    return np.interp(np.arange(RATE*5) * 44100 / RATE, np.arange(len(mono)), mono)


def correlation(recorded, expected):
    # 允许设备缓冲和重采样的延迟，比较波形而不是仅比较总音量。
    n = 1 << (len(recorded) + len(expected) - 1).bit_length()
    cross = np.fft.irfft(np.fft.rfft(recorded, n) * np.conj(np.fft.rfft(expected, n)), n)
    energy = np.sqrt(np.sum(recorded**2) * np.sum(expected**2))
    return float(np.max(np.abs(cross)) / energy) if energy else 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    loadPrcFileData("radio-output", "window-type none\naudio-library-name p3openal_audio")
    base = ShowBase(windowType="none")
    sound = Soundscape(base, effects_volume=0, music_volume=100)
    speaker = sc.default_speaker()
    loopback = sc.get_microphone(speaker.id, include_loopback=True)
    names = ("sunset-run", "midnight-circuit")
    refs = [reference(name) for name in names]
    rows = []
    state = Snapshot(0, 0, CarState((0, 0, 1)), (), contact_epoch=1)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool, loopback.recorder(
                samplerate=RATE, channels=2, blocksize=480) as recorder:
            for station, phase, preview in ((1, "menu", False), (2, "menu", False),
                                             (2, "driving", False), (1, "paused", True)):
                sound.music.stop()
                sound.music.select(station)
                future = pool.submit(recorder.record, RATE*4)
                started = time.perf_counter()
                previous = started
                while time.perf_counter() - started < 4.25:
                    now = time.perf_counter()
                    sound.update(state, SimpleNamespace(value=phase), None,
                                 now-previous, music_preview=preview)
                    previous = now
                    base.taskMgr.step()
                    time.sleep(.008)
                captured = future.result()
                # 与起始4秒素材相关；第5秒仅供补偿缓冲延迟。
                scores = [correlation(captured.mean(axis=1), ref) for ref in refs]
                matched = int(np.argmax(scores)) + 1
                passed = matched == station and scores[station-1] > .35
                row = {"phase": phase, "preview": preview, "station": station,
                       "playing": sound.music.playing[:], "waveform_match": matched,
                       "correlations": scores, "passed": passed}
                rows.append(row)
                path = args.output / f"{phase}-{station}.wav"
                with wave.open(str(path), "wb") as clip:
                    clip.setnchannels(2)
                    clip.setsampwidth(2)
                    clip.setframerate(RATE)
                    clip.writeframes((np.clip(captured, -1, 1) * 32767).astype("<i2").tobytes())
                sound.music.stop()
        report = {"passed": all(row["passed"] for row in rows), "device": speaker.name,
                  "kind": "real OpenAL WASAPI loopback matched against both song waveforms",
                  "cases": rows}
        (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["passed"] else 1
    finally:
        sound.close()
        base.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
