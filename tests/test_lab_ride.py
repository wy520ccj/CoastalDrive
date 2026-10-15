"""惯性坐标/质心分工、解析统计与工况完整性，不复制物理求解器。"""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from lab_experiment import LabOptions
from lab_metrics import ride_analysis
from lab_signals import body_components
from parameter_formulas import formula_key
from parameter_help import METRIC_INFO, explanation


def test_inertial_vector_projection_and_numeric_wire_types_are_consistent():
    # 车身旋转90°后，固定世界加速度(3,4,0)为右4/前-3；没有坐标旋转伪加速度。
    q = (np.sqrt(.5), 0., 0., np.sqrt(.5))
    projected = body_components((3.,4.,0.), q)
    assert projected == pytest.approx((4.,-3.))
    assert body_components(np.array((3.,4.,0.)),np.array(q)) == projected


def analytic_rows():
    rows = []
    for index, az in enumerate((None,4.,-4.)):
        row = {"time":index/120, "sprung_az":az}
        for wheel in ("fl","fr","rl","rr"):
            row.update({f"hub_az_{wheel}":None if index==0 else 10.,
                        f"travel_{wheel}":.08,
                        f"load_{wheel}":400. if index!=2 or wheel!="fl" else 0.})
        rows.append(row)
    contacts = tuple(SimpleNamespace(in_contact=True,contact_point=(0.,0.,.01)) for _ in range(4))
    snapshots = [SimpleNamespace(player=SimpleNamespace(unsprung_state=True,wheel_contacts=contacts))]*3
    return rows, snapshots


def test_ride_statistics_use_completed_samples_and_initial_load_without_iso_grade():
    rows, snapshots = analytic_rows()
    metrics = ride_analysis(rows,snapshots,{"maneuver":"ride_bump"},"time_limit")["metrics"]
    values = {m["key"]:m["value"] for m in metrics}
    assert values["ride.body_rms"]==4. and values["ride.hub_peak"]==10.
    assert values["ride.max_travel"]==.08 and values["ride.min_load_fl"]==0.
    assert values["ride.unload_fraction"]==1/8
    assert values["ride.load_cv_fl"]==pytest.approx(np.sqrt(.5))
    for item in metrics:
        key = "metric."+item["key"]
        assert key in METRIC_INFO and formula_key(key) is not None
        assert explanation(key).unit==item["unit"]
    assert "未加权" in metrics[0]["note"]


@pytest.mark.parametrize("reason",["failed","collision","reset"])
def test_abnormal_trial_cannot_publish_valid_ride_metrics(reason):
    rows,snapshots = analytic_rows()
    assert all(m["value"] is None for m in ride_analysis(rows,snapshots,{"maneuver":"ride_bump"},reason)["metrics"])


def test_ride_metrics_require_rear_stimulus_and_actual_wheel_degrees_of_freedom():
    rows,snapshots = analytic_rows()
    contacts = list(snapshots[0].player.wheel_contacts)
    contacts[2] = SimpleNamespace(in_contact=True,contact_point=(0.,0.,0.))
    incomplete = [SimpleNamespace(player=SimpleNamespace(unsprung_state=True,wheel_contacts=contacts))]*3
    result = ride_analysis(rows,incomplete,{"maneuver":"ride_bump"},"time_limit")["metrics"]
    assert all(m["value"] is None and "左后" in m["note"] for m in result)
    legacy = [SimpleNamespace(player=SimpleNamespace(unsprung_state=None))]*3
    assert all(m["value"] is None for m in ride_analysis(rows,legacy,{"maneuver":"ride_bump"},"time_limit")["metrics"])
    assert all(m["value"] is None for m in ride_analysis(rows,snapshots,{"maneuver":"braking"},"stopped")["metrics"])


@pytest.mark.parametrize("change",[{"bump_height_m":0.},{"bump_length_m":float("nan")},{"bump_distance_m":1.}])
def test_bump_geometry_boundary_rejects_invalid_physical_inputs(change):
    with pytest.raises(ValueError,match="凸起"):
        replace(LabOptions(),**change)
