"""记录音频修复前后源码差异，不把旧物理证据称为全仓最终版本。"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def main():
    baseline = json.loads((HERE / "vehicle-ab/summary.json").read_text(encoding="utf-8"))
    before = baseline["source_sha256_before"]
    after = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in before}
    changed = {name: {"before": before[name], "after": after[name]}
               for name in before if before[name] != after[name]}
    report = {
        "scope": "vehicle-ab production and probe Python after audio-only regression repair",
        "source_count": len(before),
        "production_source_count": sum(name.startswith("src/") for name in before),
        "tool_source_count": sum(name.startswith("tools/") for name in before),
        "source_sha256_after": after,
        "changed": changed,
        "only_audio_impact_changed": set(changed) == {"src/audio/impact.py"},
        "physics_source_unchanged": all(name.startswith("src/audio/") for name in changed),
        "old_evidence": "A/B, strict rigid and substep trajectories describe unchanged physics; "
                        "audio T1 and final T2 validate the repaired presentation behavior",
    }
    (HERE / "audio-source-transition.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print({"sources": len(before), "changed": list(changed),
           "only_audio_impact_changed": report["only_audio_impact_changed"]})
    return 0 if report["only_audio_impact_changed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
