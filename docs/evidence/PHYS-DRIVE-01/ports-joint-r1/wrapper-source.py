"""把正式端口函数放入冻结四轮联合台架；不冒充原生驾驶接入。"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from transmission_ports import clutch_brake_plans, clutch_brake_state, transmission_state


def main():
    output = ROOT / "docs/evidence/PHYS-DRIVE-01/ports-joint-r1"
    output.parent.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).with_name("drive-contact-joint-r2-probe.py")
    scope = {"__file__": str(source), "__name__": "frozen_joint"}
    exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), scope)

    def two_ports(delta, speed, dcc, dcl, dll, dt, capacity, efficiency):
        value, speeds = transmission_state((delta, speed), ((dcc, dcl), (dcl, dll)), dt, capacity, efficiency)
        return value + speeds, 1

    scope["TWO"] = two_ports
    scope["port_plans"] = lambda response, dt, capacity, brake, efficiency: clutch_brake_plans(
        response, capacity, brake, efficiency)
    scope["port_state"] = clutch_brake_state
    scope["OUT"] = output
    scope["main"]()
    (output / "live-port-source.py").write_bytes((ROOT / "src/transmission_ports.py").read_bytes())
    (output / "frozen-joint-source.py").write_bytes(source.read_bytes())
    (output / "wrapper-source.py").write_bytes(Path(__file__).read_bytes())
    current = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    old = json.loads(Path(__file__).with_name("drive-contact-joint-r1").joinpath("summary.json").read_text(encoding="utf-8"))
    difference = max(abs(a - b) for new, previous in zip(current["trials"], old["trials"])
                     for name in ("qend", "velocity_end") for a, b in zip(new[name], previous[name]))
    assert difference < 1e-10
    result = {"cases": len(current["trials"]), "maximum_state_difference": difference,
              "maximum_energy_error_j": current["maximum_energy_error_j"],
              "maximum_momentum_error_nms": current["maximum_momentum_error_nms"],
              "production_port_sha256": hashlib.sha256((ROOT / "src/transmission_ports.py").read_bytes()).hexdigest(),
              "claim": "live production port functions inside frozen compliant joint bench; native driving not connected"}
    (output / "comparison.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
