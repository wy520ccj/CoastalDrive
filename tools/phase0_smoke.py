"""Small, repeatable checks for the phase 0 runtime setup."""

from __future__ import annotations

import json
import math
import struct
import sys
import tempfile
import wave
from pathlib import Path

from panda3d.core import Filename, loadPrcFileData

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "logs" / "phase0-smoke.json"
MODEL_PATH = PROJECT_ROOT / "assets" / "game" / "player-car.glb"
ROUNDTRIP_MODEL_PATH = PROJECT_ROOT / "builds" / "phase0-blender-roundtrip.glb"


def make_test_tone(path: Path) -> None:
    sample_rate = 22050
    frames = []
    for i in range(sample_rate // 10):
        sample = int(0.15 * 32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
        frames.append(struct.pack("<h", sample))
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"".join(frames))


def run() -> int:
    loadPrcFileData("phase0", "window-type offscreen")
    loadPrcFileData("phase0", "audio-library-name null")

    report: dict[str, object] = {
        "python": sys.version,
        "executable": sys.executable,
        "checks": {},
    }

    from direct.showbase.ShowBase import ShowBase
    from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode, BulletWorld
    from panda3d.core import AmbientLight, NodePath, Vec3

    try:
        import importlib

        importlib.import_module("simplepbr")
        report["checks"]["simplepbr_import"] = True
    except (ImportError, OSError, RuntimeError) as exc:  # pragma: no cover - diagnostic boundary
        report["checks"]["simplepbr_import"] = f"FAIL: {exc}"

    app = ShowBase()
    app.disableMouse()
    app.setBackgroundColor(0.08, 0.12, 0.18)

    light = AmbientLight("phase0-ambient")
    light.setColor((0.8, 0.8, 0.8, 1))
    app.render.setLight(app.render.attachNewNode(light))

    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    body = BulletRigidBodyNode("phase0-body")
    body.setMass(1.0)
    body.addShape(BulletBoxShape(Vec3(0.5, 0.5, 0.5)))
    body_path = app.render.attachNewNode(body)
    body_path.setPos(0, 0, 3)
    world.attachRigidBody(body)
    world.doPhysics(1 / 60, 4, 1 / 60)
    report["checks"]["bullet_step"] = body.getLinearVelocity().getZ() < 0

    try:
        import gltf

        model = gltf.load_model(Filename.fromOsSpecific(str(MODEL_PATH)))
        model_path = NodePath(model)
        model_path.reparentTo(app.render)
        model_path.setScale(1.0)
        report["checks"]["glb_load"] = MODEL_PATH.exists() and not model_path.isEmpty()
    except (ImportError, OSError, RuntimeError, ValueError) as exc:  # pragma: no cover - diagnostic boundary
        report["checks"]["glb_load"] = f"FAIL: {exc}"

    try:
        if ROUNDTRIP_MODEL_PATH.exists():
            roundtrip_model = gltf.load_model(Filename.fromOsSpecific(str(ROUNDTRIP_MODEL_PATH)))
            roundtrip_path = NodePath(roundtrip_model)
            roundtrip_path.reparentTo(app.render)
            report["checks"]["blender_roundtrip_load"] = not roundtrip_path.isEmpty()
        else:
            report["checks"]["blender_roundtrip_load"] = "SKIP: no Blender roundtrip asset"
    except (ImportError, OSError, RuntimeError, ValueError) as exc:  # pragma: no cover - diagnostic boundary
        report["checks"]["blender_roundtrip_load"] = f"FAIL: {exc}"

    try:
        from panda3d.core import TextNode

        text_node = TextNode("phase0-text")
        text_node.setText("滨海驾驶")
        report["checks"]["chinese_text"] = text_node.getText() == "滨海驾驶"
    except (ImportError, OSError, RuntimeError, ValueError) as exc:  # pragma: no cover - diagnostic boundary
        report["checks"]["chinese_text"] = f"FAIL: {exc}"

    with tempfile.TemporaryDirectory(prefix="coastaldrive-phase0-") as temp_dir:
        tone_path = Path(temp_dir) / "tone.wav"
        make_test_tone(tone_path)
        try:
            sound = app.loader.loadSfx(Filename.fromOsSpecific(str(tone_path)))
            report["checks"]["wav_load"] = sound is not None
        except (OSError, RuntimeError, ValueError) as exc:  # pragma: no cover - diagnostic boundary
            report["checks"]["wav_load"] = f"FAIL: {exc}"

    report["renderer"] = app.pipe.getInterfaceName() if app.pipe else "none"
    report["checks"]["offscreen_window"] = app.win is not None

    required = {
        "simplepbr_import",
        "bullet_step",
        "glb_load",
        "chinese_text",
        "wav_load",
        "offscreen_window",
    }
    if ROUNDTRIP_MODEL_PATH.exists():
        required.add("blender_roundtrip_load")
    passed = all(report["checks"].get(name) is True for name in required)
    report["passed"] = passed
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    app.destroy()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(run())
