"""离线转换两首独立授权作品，保留原编曲并统一播放响度。"""

import hashlib
import json
import subprocess
import wave
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "assets/source/audio-music"
OUTPUT = ROOT / "assets/game/audio"


def prepare():
    SOURCE.mkdir(parents=True, exist_ok=True)
    tracks = json.loads(Path(__file__).with_name("music_sources.json").read_text(encoding="utf-8"))
    entries = []
    for track in tracks:
        source = SOURCE / track["source_file"]
        if not source.exists():
            with urlopen(track["download_url"], timeout=60) as response:
                source.write_bytes(response.read())
        if hashlib.sha256(source.read_bytes()).hexdigest() != track["source_sha256"]:
            raise ValueError(f"源曲目SHA256不符：{source}")
        # 两遍EBU响度处理：避免切台仅因原母带响度不同而突响，保留全曲结构。
        meter = subprocess.run([
            "ffmpeg", "-hide_banner", "-i", str(source), "-af",
            "loudnorm=I=-18:TP=-4.5:LRA=11:print_format=json", "-f", "null", "-"
        ], capture_output=True, text=True, encoding="utf-8", check=True)
        measured, _ = json.JSONDecoder().raw_decode(meter.stderr[meter.stderr.rindex("{"):])
        filters = ("loudnorm=I=-18:TP=-4.5:LRA=11:linear=true:"
                   f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
                   f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
                   f"offset={measured['target_offset']},afade=t=in:d=0.04")
        target = OUTPUT / "music" / f"{track['station_asset']}.wav"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-af", filters, "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(target)
        ], check=True)
        with wave.open(str(target), "rb") as clip:
            duration = clip.getnframes() / clip.getframerate()
        entries.append({"path": target.relative_to(OUTPUT).as_posix(),
                        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                        "duration": duration})
        print(f"{track['title']}: {duration:.2f}s")
    credits = {"tracks": tracks, "processing": "Full compositions; -18 LUFS / -4.5 dBTP, "
               "40 ms attack fade; 44.1 kHz stereo 16-bit PCM; no radio/static effect"}
    (OUTPUT / "music-sources.json").write_text(json.dumps(credits, ensure_ascii=False, indent=2)
                                              + "\n", encoding="utf-8")
    return entries


if __name__ == "__main__":
    prepare()
