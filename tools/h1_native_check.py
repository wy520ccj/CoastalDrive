"""Record a manual/native-keyboard run without supplying any driving inputs."""

import json
import sys
from dataclasses import asdict
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from direct.showbase.DirectObject import DirectObject

    from application import CoastalDrive

    output = root / "logs/h1-native"
    output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive()
    listener = DirectObject()
    events = []
    samples = []

    def record(key):
        events.append(
            {"key": key, "tick": app.session.current.tick, "phase": app.session.phase.value}
        )

    for key in ("enter", "escape", "w", "a", "s", "d", "r", "c", "arrow_up", "raw-w"):
        listener.accept(key, record, [key])
        listener.accept(f"{key}-up", record, [f"{key}-up"])

    def sample(task):
        state = app.session.current
        samples.append(
            {
                "phase": app.session.phase.value,
                "tick": state.tick,
                "position": state.player.position,
                "speed": state.player.speed,
                "control": asdict(app.session.keyboard.sample(state, 1 / 120)),
            }
        )
        return task.again

    app.taskMgr.doMethodLater(0.05, sample, "native-input-observer")
    try:
        app.run()
    finally:
        listener.ignoreAll()
        app.taskMgr.remove("native-input-observer")
        (output / "input-record.json").write_text(
            json.dumps(
                {
                    "input_source": "native window, no injected controller",
                    "events": events,
                    "samples": samples,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        app.close_game()


if __name__ == "__main__":
    main()
