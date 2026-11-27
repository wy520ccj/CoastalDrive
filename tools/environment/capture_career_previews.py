"""使用独立版 CoastalDrive 原生渲染器重拍全部 9 张生涯赛事与追逐预览图。"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from panda3d.core import Filename, Vec3
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from application import CoastalDrive
from race import GameMode

OUT_DIR = ROOT / "assets/game/ui/career"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    existing_size = (1280, 720)
    sample = OUT_DIR / "first-drive.png"
    if sample.is_file():
        with Image.open(sample) as im:
            existing_size = im.size

    tmp_out = ROOT / "logs/standalone-visual-check"
    tmp_out.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, output=tmp_out, render_size=existing_size)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.career_progress.records = {
        name: {"stars": 3, "seconds": 20.0}
        for name in ("first-drive", "parking", "slalom", "coast-sprint", "ridge-run", "coastal-cup")
    }
    app.aspect2d.hide()
    app.render2d.hide()

    # 统一使用 BRZ Varis（game-tuned）与原始 preview-manifest.json 保持一致
    app.career_action("select-car", "game-tuned")

    def capture(filename: str) -> dict:
        app.scene.sync_segments()
        state = app.session.current
        app.scene.apply(state)
        pos, look_at = app.chase_camera.update(state.player, 11.0, 0.0, snap=True)
        app.camera.setPos(pos)
        app.camera.lookAt(look_at)
        app.render.setShaderInput("camera_world_position", pos)
        app.scene.update_lighting(Vec3(*state.player.position))
        for _ in range(6):
            app.taskMgr.step()
        dest = OUT_DIR / filename
        app.win.saveScreenshot(Filename.fromOsSpecific(str(dest)))
        print(f"Captured {filename} ({existing_size[0]}x{existing_size[1]})")
        return {
            "image": filename,
            "sha256": sha256_file(dest),
            "design_id": "game-tuned",
            "visual": "sports",
        }

    cases = []
    try:
        for ev in ("first-drive", "parking", "slalom", "coast-sprint", "ridge-run", "coastal-cup"):
            app.career_action("start", ev)
            app.challenge_action("challenge-start")
            entry = capture(f"{ev}.png")
            entry["event"] = ev
            cases.append(entry)

        for mode, fname, ev_id in (
            (GameMode.VALLEY_PACE, "chase-valley.png", "chase-valley"),
            (GameMode.HILL_TRAFFIC, "hill-traffic.png", "hill-traffic"),
        ):
            app.career_action("start", mode)
            app.challenge_action("challenge-start")
            entry = capture(fname)
            entry["event"] = ev_id
            cases.append(entry)

        # chase-coastal：滨海环路计时追逐
        app.open_budget_challenge(GameMode.TIME_TRIAL, origin="chase")
        app.challenge_action("challenge-start")
        entry = capture("chase-coastal.png")
        entry["event"] = "chase-coastal"
        cases.append(entry)
    finally:
        app.close_game()

    manifest = {
        "source": "CoastalDrive standalone Panda3D renderer; open-license MIT/CC0 foliage, terrain, rocks, sky and roads",
        "process": "Live camera capture with synced road segments and sky dome; no UI and no pixel edits",
        "cases": cases,
    }
    (OUT_DIR / "preview-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("Updated", OUT_DIR / "preview-manifest.json")


if __name__ == "__main__":
    main()
