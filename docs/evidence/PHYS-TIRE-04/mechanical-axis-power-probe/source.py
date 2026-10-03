"""轮轴与接触平面分离的虚功核对；不修改射线支撑或驾驶源码。"""

import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from tire_coupling import cross, dot

OUT = Path(__file__).with_name("mechanical-axis-power-probe")


def normalized(vector):
    length = math.sqrt(dot(vector, vector))
    return tuple(v / length for v in vector)


def trial(bank, steer, omega):
    bank, steer = math.radians(bank), math.radians(steer)
    axis = (math.cos(steer), -math.sin(steer), 0.)
    normal = (math.sin(bank), 0., math.cos(bank))
    tangent = normalized(cross(normal, axis))
    lateral = cross(tangent, normal)
    radius, inertia = .33, 1.8
    contact_point = (.84, 1.1, -.42)
    # 保留现有射线支撑的point-to-hub偏移；不冒充薄圆盘与路面的几何求交。
    offset = tuple(-radius * n for n in normal)
    lever = dot(cross(offset, tangent), axis)
    angular, velocity = (.2, -.1, .3), (.4, 12., -.2)
    force_x, force_y, drive, brake = 1734., -421., 130., 20.
    force = tuple(force_x * tangent[a] + force_y * lateral[a] for a in range(3))
    surface = tuple(velocity[a] + cross(angular, contact_point)[a]
                    + (-omega - dot(angular, axis)) * cross(axis, offset)[a] for a in range(3))
    moment_x = tuple(cross(contact_point, tangent)[a] - lever * axis[a] for a in range(3))
    vx = dot(velocity, tangent) + dot(angular, moment_x)
    vy = dot(velocity, lateral) + dot(angular, cross(contact_point, lateral))
    assert abs(lever - radius * math.sqrt(1 - dot(axis, normal) ** 2)) < 1e-15
    assert abs(dot(surface, tangent) - (vx - lever * omega)) < 1e-14
    assert abs(dot(surface, lateral) - vy) < 1e-14
    spin_torque = drive - brake - lever * force_x
    body_torque = tuple(cross(contact_point, force)[a] + spin_torque * axis[a] for a in range(3))
    mechanical_power = dot(velocity, force) + dot(angular, body_torque) + omega * spin_torque
    contact_power = dot(surface, force)
    actuator_power = (drive - brake) * (omega + dot(angular, axis))
    assert abs(mechanical_power - contact_power - actuator_power) < 1e-10
    old_tangent = normalized(tuple((math.sin(steer), math.cos(steer), 0.)[a]
                                   - normal[a] * dot((math.sin(steer), math.cos(steer), 0.), normal)
                                   for a in range(3)))
    old_axle = cross(old_tangent, normal)
    old_spin_vector = tuple(-inertia * omega * old_axle[a] for a in range(3))
    true_spin_vector = tuple(-inertia * omega * axis[a] for a in range(3))
    return {"bank_deg": math.degrees(bank), "steer_deg": math.degrees(steer), "omega_radps": omega,
            "mechanical_axis": axis, "road_normal": normal, "tangent": tangent, "lateral": lateral,
            "contact_point": contact_point, "point_to_hub_offset": tuple(-v for v in offset),
            "effective_rolling_radius_m": lever, "body_angular_radps": angular,
            "velocity_mps": velocity, "force_n": force, "drive_nm": drive, "brake_nm": brake,
            "surface_speed_mps": surface, "spin_torque_nm": spin_torque, "body_torque_nm": body_torque,
            "mechanical_power_w": mechanical_power, "contact_power_w": contact_power,
            "actuator_power_w": actuator_power, "power_error_w": mechanical_power-contact_power-actuator_power,
            "old_contact_axle": old_axle, "old_vs_mechanical_spin_vector_difference_nms": tuple(
                old_spin_vector[a] - true_spin_vector[a] for a in range(3))}


if __name__ == "__main__":
    OUT.mkdir(exist_ok=False)
    (OUT / "source.py").write_bytes(Path(__file__).read_bytes())
    trials = [trial(bank, steer, omega) for bank in (-20., -5., 0., 5., 20.)
              for steer in (-30., 0., 30.) for omega in (-60., 0., 60.)]
    report = {"claim": "independent mechanical/contact virtual-power derivation, no source integration",
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "trials": trials}
    (OUT / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"trials": len(trials), "maximum_power_error_w": max(abs(t["power_error_w"]) for t in trials),
                      "maximum_false_spin_vector_nms": max(math.sqrt(dot(
                          t["old_vs_mechanical_spin_vector_difference_nms"],
                          t["old_vs_mechanical_spin_vector_difference_nms"])) for t in trials)}))
