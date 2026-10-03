"""保留原门槛验证共面中心Box分区原型；不改生产源码。"""

import gzip
import io
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools"), str(HERE)]

from centered_box_partition import install
from panda3d.core import Vec3
from physics import esc_probe
from physics.collision_support_probe import source_hashes

import vehicle
from simulation import Control, Simulation
from vehicle_config import CAR
from vehicle_state import VehicleCommand


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    before = source_hashes()
    original = vehicle.install_chassis_shape
    vehicle.install_chassis_shape = install
    report = {"status": "running", "source_before": before, "trials": [],
              "scope": "prototype sharp nominal box union, zero child margin, original inertia; rounded GJK volume deliberately differs near historical external edges, all original safety gates retained"}
    try:
        for steps in (2, 4, 8, 16):
            cfg = replace(esc_probe.trial_config("airborne-recontact", True), tire_substeps=steps)
            summary, rows = esc_probe.run_trial("airborne-recontact", True, 6, "simulation", vehicle_config=cfg)
            esc_probe.write_csv(output / f"airborne-{steps}.csv.gz", rows)
            report["trials"].append({"case": "airborne-recontact", "steps": steps, **summary})
            print("airborne", steps, summary["peak_abs_unwrapped_heading_deg"], summary["path_distance_m"], flush=True)
        sim = Simulation(track="highway")
        try:
            target = sim._traffic_bodies[0]
            pos = target.getTransform().getPos()
            sim.reset_player((pos.x, pos.y-12, .55))
            for _ in range(60):
                sim.step(Control())
            sim._chassis.setLinearVelocity(Vec3(0, 30, 0))
            sim.player.tires.initialize_rolling(30)
            peak, first_gap = 0.0, None
            with gzip.open(output / "rear.jsonl.gz", "wt", encoding="utf-8") as stream:
                for _ in range(480):
                    sim.step(Control(throttle=1))
                    peak = max(peak, abs(sim.snapshot().player.roll))
                    if first_gap is None and sim._world.contactTestPair(sim._chassis, target).getNumContacts():
                        first_gap = target.getTransform().getPos().y-sim._chassis.getTransform().getPos().y
                    stream.write(json.dumps(asdict(sim.snapshot()), allow_nan=False)+"\n")
            report["rear"] = {"peak_abs_roll_deg": peak, "first_gap_m": first_gap,
                              "final_speed_mps": sim.snapshot().player.speed}
            print("rear", report["rear"], flush=True)
        finally:
            sim.close()
        for sustained in (False, True):
            sim = Simulation(track="highway", traffic_count=0)
            try:
                diagnostic = io.StringIO()
                sim.set_impact_diagnostic(diagnostic, scenario="center-box")
                sim.reset_player((6.9 if sustained else 5.8, 30, .55))
                sim._chassis.setLinearVelocity(Vec3(.5, 8, 0) if sustained else Vec3(8, 12, 0))
                sim.player.tires.initialize_rolling(8 if sustained else 12)
                run = longest = 0
                impacts = []
                with gzip.open(output / f"rail-{sustained}.jsonl.gz", "wt", encoding="utf-8") as stream:
                    for _ in range(840 if sustained else 30):
                        sim.step(VehicleCommand(throttle=.5, steering=2, direction=1) if sustained else Control())
                        state = sim.snapshot()
                        touching = any(c.material == "metal_barrier" for c in state.contacts)
                        run = run+1 if touching else 0
                        longest = max(longest, run)
                        impacts.extend(state.impacts)
                        stream.write(json.dumps(asdict(state), allow_nan=False)+"\n")
                (output / f"rail-{sustained}-diagnostic.jsonl").write_text(diagnostic.getvalue(), encoding="utf-8")
                report[f"rail_{sustained}"] = {"longest_contact_ticks": longest, "impacts": [asdict(i) for i in impacts]}
                print("rail", sustained, longest, len(impacts), flush=True)
            finally:
                sim.close()
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        vehicle.install_chassis_shape = original
        report["source_after"] = source_hashes()
        report["source_unchanged"] = before == report["source_after"]
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


if __name__ == "__main__":
    run(HERE / "centered-box-prototype")
