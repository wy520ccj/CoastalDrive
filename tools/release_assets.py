"""发行资源精简：完整PCM无损压缩，原始资源仍留在源码目录。"""

import hashlib
import json
import subprocess
import wave

from panda3d.core import Datagram, Filename, MovieAudio

PRUNED_ASSETS = (
    "ui/fonts/SourceHanSansSC-Regular.otf",
    "ui/fonts/fusion-pixel-12px-proportional-zh_hans.ttf",
    "ui/backgrounds/coastal-menu.png",
    "ui/backgrounds/workspace-coast-v1.png",
)


def verify_audio(original, compressed):
    cursor = MovieAudio.get(Filename.from_os_specific(str(compressed))).open()
    digest = hashlib.sha256()
    with wave.open(str(original), "rb") as source:
        if (cursor.audio_rate(), cursor.audio_channels()) != (source.getframerate(), source.getnchannels()):
            raise RuntimeError("FLAC采样率或声道改变")
        remaining = source.getnframes()
        if abs(cursor.length()-remaining/source.getframerate()) > 1/source.getframerate():
            raise RuntimeError("FLAC长度改变")
        while remaining:
            count = min(32768, remaining)
            data = Datagram()
            cursor.read_samples(count, data)
            pcm = data.get_message()
            if pcm != source.readframes(count):
                raise RuntimeError(f"FLAC完整采样不一致：{original.name}")
            digest.update(pcm)
            remaining -= count
    positions = (0., .10123, 1.98765, 17.5317, min(cursor.length()-.2, 65.123))
    with wave.open(str(original), "rb") as reference:
        for position in positions:
            reference.setpos(int(position*reference.getframerate()))
            cursor.seek(position)
            data = Datagram()
            cursor.read_samples(4096, data)
            if reference.readframes(4096) != data.get_message():
                raise RuntimeError(f"FLAC跳转采样不一致：{original.name}/{position}")
    return {"pcm_sha256": digest.hexdigest(), "full_pcm_equal": True,
            "native_decoder": type(cursor).__name__, "seek_positions": positions}


def prepare_assets(package, ffmpeg):
    root = package / "assets/game"
    removed = {}
    for name in PRUNED_ASSETS:
        path = root / name
        removed[name] = path.stat().st_size
        path.unlink()
    manifest = root / "audio/music-sources.json"
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    compressed = {}
    paths = []
    for name in metadata["runtime_files"]:
        original = root / "audio" / name
        target = original.with_suffix(".flac")
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(original),
                        "-c:a", "flac", "-compression_level", "12", str(target)], check=True)
        result = verify_audio(original, target)
        result.update(original_bytes=original.stat().st_size, compressed_bytes=target.stat().st_size,
                      source_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                      compressed_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        compressed[name] = result
        paths.append(target.relative_to(root / "audio").as_posix())
        original.unlink()
    metadata["runtime_files"] = paths
    metadata["distribution_encoding"] = "FLAC lossless; decoded PCM identical to original WAV"
    manifest.write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return {"removed_unused_assets": removed, "lossless_music": compressed}
