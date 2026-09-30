"""真实OpenAL载入与声音生命周期短探针，记录PCM资源质量。"""

import argparse
import json
import math
import sys
import time
import wave
from array import array
from dataclasses import replace
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from direct.showbase.ShowBase import ShowBase
from panda3d.core import AudioSound, loadPrcFileData

from impact_events import ImpactEvent
from session import Phase
from simulation import Snapshot
from soundscape import Soundscape
from vehicle_state import CarState


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    loadPrcFileData("audio-check", "window-type none\naudio-library-name p3openal_audio")
    base = ShowBase(windowType="none")
    sound = Soundscape(base)
    log = StringIO()
    sound.set_impact_diagnostic(log)
    try:
        handles = list(sound.engine_audio.loops) + list(sound.driving_audio.sounds.values())
        handles += list(sound.music.tracks) + list(sound.cues.sounds.values())
        for pool in sound.impact_audio.samples.values():
            for _, voices, _ in pool:
                handles.extend(voices)
        ready = sum(s.status() == AudioSound.READY for s in handles)
        if ready != len(handles):
            raise RuntimeError(f"OpenAL未载入全部素材：{ready}/{len(handles)}")
        state = Snapshot(0, 0, CarState((0, 0, 1)), (), contact_epoch=1)
        updates = []
        # 完整加速、换挡、不同材质撞击以及菜单/暂停/结算/重开。
        for tick in range(400):
            current = Phase.COUNTDOWN if tick < 20 else Phase.DRIVING
            if 250 <= tick < 260:
                current = Phase.PAUSED
            if tick >= 350:
                current = Phase.RESULTS
            player = replace(state.player, rpm=min(6500, 900 + tick * 22),
                             speed=min(40, tick / 8), throttle=.85, gear=1 + tick // 100)
            impacts = ()
            if tick in (60, 120, 200, 350):
                material = ("vehicle" if tick in (60, 350) else
                            "metal_barrier" if tick == 120 else "hard_solid")
                impacts = (ImpactEvent(1, tick, 0, (1,), material, 12000, 12000,
                                       10, 3, (0, 2, .4), (0, -1, 0), "front", 1),)
            if tick == 160:
                sound.music.select(2)
            state = replace(state, time=tick / 60, player=player, impacts=impacts)
            start = time.perf_counter_ns()
            sound.update(state, current, None, 1 / 60, countdown_ticks=max(0, 360-tick*20))
            updates.append((time.perf_counter_ns() - start) / 1e6)
            base.taskMgr.step()
        assets = []
        for path in sorted((ROOT / "assets/game/audio").rglob("*.wav")):
            if path.parent.name not in ("engine", "driving", "impact", "music", "cues"):
                continue
            with wave.open(str(path), "rb") as clip:
                pcm = array("h", clip.readframes(clip.getnframes()))
                rms = math.sqrt(sum(x*x for x in pcm) / len(pcm))
                dc_ratio = abs(sum(pcm) / len(pcm)) / rms
                assets.append({"path": path.relative_to(ROOT).as_posix(),
                               "seconds": clip.getnframes() / clip.getframerate(),
                               "channels": clip.getnchannels(),
                               "peak": max(abs(x) for x in pcm) / 32768,
                               "dc_rms_ratio": dc_ratio})
        sound.close()
        stopped = all(s.status() != AudioSound.PLAYING for s in handles)
        decisions = [json.loads(line) for line in log.getvalue().splitlines()]
        report = {"passed": ready == len(handles) and stopped and
                  all(a["peak"] < .9 and a["dc_rms_ratio"] < .1 for a in assets),
                  "backend": base.sfxManagerList[0].getType().getName(),
                  "ready_handles": ready, "total_handles": len(handles),
                  "all_stopped": stopped, "assets": assets,
                  "update_mean_ms": sum(updates) / len(updates),
                  "update_p95_ms": sorted(updates)[round(len(updates) * .95)-1],
                  "decisions": decisions,
                  "kind": "real OpenAL load/control probe; not subjective sound acceptance"}
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("passed", "backend", "ready_handles",
                                               "total_handles", "update_p95_ms")}, indent=2))
        return 0 if report["passed"] else 1
    finally:
        sound.close()
        base.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
