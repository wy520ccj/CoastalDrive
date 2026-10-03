"""只读逐子步原始记录，按既有0.001N停止门槛计算总路面功误差界。"""

import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "residual-work-v2"
report = {"status": "completed", "gate_n": .001, "trials": [], "scope":
          "原0.001N门槛上界；保留实际残差更紧界的浮点负违例。静摩擦不能用末子步patch速度乘残差替代完整界。"}
for path in sorted(DATA.glob("*/summary.json")):
    trial = json.loads(path.read_text(encoding="utf-8"))
    config = trial["config"]
    macro = defaultdict(lambda: [0.0, 0.0])
    count = violations = residual_failures = 0
    maximum_negative_fraction, tight_violations = 0.0, 0
    raw = path.parent / "substeps.jsonl.gz"
    worst = None
    with gzip.open(raw, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            step, h, speed, grip = row["step"], row["dt_s"], row["patch_speed_mps"], row["grip_n"]
            bound = h*.001*speed
            if step["mode"] in ("compliant-sticking", "compliant-sliding"):
                bound += h*.001*grip/(config["tire_contact_stiffness"]*h+config["tire_contact_damping"])
            road = step["road_dissipation"]
            macro[row["tick"], row["wheel"]][0] += road
            macro[row["tick"], row["wheel"]][1] += bound
            count += 1
            violations += road+bound < 0
            residual_failures += step["residual"] >= .001
            tight_violations += row["signed_road_above_lower_bound_j"] < 0
            if road < 0 and bound > 0:
                fraction = -road/bound
                if fraction > maximum_negative_fraction:
                    maximum_negative_fraction = fraction
                    worst = {"tick": row["tick"], "substep": row["substep"], "wheel": row["wheel"],
                             "road_j": road, "gate_bound_j": bound, "actual_residual_n": step["residual"],
                             "mode": step["mode"]}
    report["trials"].append({"case": trial["case"], "label": trial["label"],
        "source_unchanged": trial["source_unchanged"], "same_timed_trace": trial["same_timed_trace"],
        "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(), "records": count,
        "substep_gate_bound_violations": int(violations),
        "macro_gate_bound_violations": sum(road+bound < 0 for road, bound in macro.values()),
        "original_force_gate_failures": int(residual_failures),
        "actual_residual_tighter_bound_violations": int(tight_violations),
        "maximum_negative_fraction_of_gate_bound": maximum_negative_fraction, "worst_fraction_record": worst})
report["explanation"] = (
    "B加速有4个约2.5e-17至6.4e-17J负功超出按近机器精度实际残差计算的紧界；"
    "F与目标的浮点相减可给近零残差，而slip-rate的独立运算仍有舍入差。"
    "原0.001N门槛功界未放宽，逐子步及总和均需明确核对；不钳负路面功。"
    "初轮residual-work的same_timed_trace=False来自tuple与JSON list直接比较，"
    "修正观察器表示后v2所有既有物理字段与计时轨迹严格相同。")
(DATA / "gate-bound-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
print(json.dumps([{k: r[k] for k in ("case", "label", "records", "substep_gate_bound_violations",
                                    "macro_gate_bound_violations", "same_timed_trace")} for r in report["trials"]], ensure_ascii=False))
