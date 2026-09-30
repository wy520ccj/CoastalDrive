"""连续切台/续播的真实OpenAL回录及按键耗时，覆盖非整采样位置。"""

import argparse
import importlib.util
import json
import subprocess
import sys
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import soundcard as sc

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from check_radio_output import correlation
from direct.showbase.ShowBase import ShowBase
from panda3d.core import loadPrcFileData

from audio.music import MusicAudio

RATE = 48000


def reference(path, start):
    with wave.open(str(path), "rb") as clip:
        frames = clip.getnframes()
        clip.setpos(int(start*44100) % frames)
        raw = clip.readframes(44100*4)
        if len(raw) < 44100*4*4:
            clip.rewind()
            raw += clip.readframes((44100*4*4-len(raw))//4)
    values = np.frombuffer(raw, dtype="<i2").reshape(-1, 2).mean(axis=1)/32768
    return np.interp(np.arange(RATE*4)*44100/RATE, np.arange(len(values)), values)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    loadPrcFileData("radio-switch", "window-type none\naudio-library-name p3openal_audio")
    base = ShowBase(windowType="none")
    music_class = MusicAudio
    if args.baseline:
        source = subprocess.check_output(["git", "show", "fc2a16b:src/audio/music.py"],
                                         cwd=ROOT).decode("utf-8")
        module_path = args.output / "baseline_music.py"
        module_path.write_text(source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("radio_baseline", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        music_class = module.MusicAudio
    directory = ROOT / "assets/game/audio"
    music = music_class(base, directory)
    # 可重复触发旧WAV流式seek的奇数字节错位，不依赖偶然的暂停时机。
    music.positions[:2] = [.1234567, .2345678]
    speaker = sc.default_speaker()
    loopback = sc.get_microphone(speaker.id, include_loopback=True)
    rows, updates, overlaps = [], [], 0
    try:
        with ThreadPoolExecutor(max_workers=1) as pool, loopback.recorder(
                samplerate=RATE, channels=2, blocksize=480) as recorder:
            for station in (1, 2, 1, 2):
                position = music.positions[station-1]
                expected = reference(directory / "music" /
                                     ("sunset-run.wav" if station == 1 else "midnight-circuit.wav"),
                                     position)
                music.select(station)
                future = pool.submit(recorder.record, RATE*3)
                started = previous = time.perf_counter()
                while time.perf_counter()-started < 3.15:
                    now = time.perf_counter()
                    timer = time.perf_counter()
                    music.update("driving", now-previous, 1, 1)
                    updates.append((time.perf_counter()-timer)*1000)
                    overlaps += sum(music.playing) > 1
                    previous = now
                    base.taskMgr.step()
                    time.sleep(.008)
                captured = future.result()
                mono = captured.mean(axis=1)
                # 正常鼓镲允许高频；与原曲比较高频比例并匹配完整波形，检测解码错位。
                steady = mono[RATE//2:]
                hiss = float(np.sum(np.diff(steady, n=2)**2)/np.sum(steady**2))
                expected_hf = float(np.sum(np.diff(expected, n=2)**2)/np.sum(expected**2))
                match = correlation(mono, expected)
                row = {"station": station, "resume_seconds": position,
                       "waveform_correlation": match, "hiss_energy_ratio": hiss,
                       "reference_high_frequency_ratio": expected_hf,
                       "passed": match > .5 and hiss < expected_hf * 4 + .003}
                rows.append(row)
                with wave.open(str(args.output / f"switch-{len(rows)}-{station}.wav"), "wb") as clip:
                    clip.setparams((2, 2, RATE, 0, "NONE", "not compressed"))
                    clip.writeframes((np.clip(captured, -1, 1)*32767).astype("<i2").tobytes())
        report = {"passed": all(row["passed"] for row in rows) and overlaps == 0,
                  "baseline": args.baseline, "device": speaker.name, "cases": rows,
                  "overlap_updates": overlaps, "music_update_max_ms": max(updates),
                  "music_update_p95_ms": float(np.percentile(updates, 95))}
        (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["passed"] or args.baseline else 1
    finally:
        music.stop()
        base.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
