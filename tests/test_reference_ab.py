"""配置变化必须改变真实加速、轮载转移和制动距离。"""

from dataclasses import replace

import pytest
from physics.reference_ab import run_trial

from driving_modes import REFERENCE_CAR


@pytest.mark.parametrize("case,changes", [
    ("B1-wheel-inertia", {"wheel_inertia": 3.6}),
    ("B2-cg-height", {"center_of_mass_height": .62}),
    ("B3-asphalt-mu", {"road_friction": .6}),
])
def test_reference_parameter_changes_have_the_expected_physical_direction(case, changes):
    baseline, _ = run_trial(case, REFERENCE_CAR)
    candidate, _ = run_trial(case, replace(REFERENCE_CAR, **changes))
    if case == "B1-wheel-inertia":
        assert candidate["final_speed_mps"] < baseline["final_speed_mps"]
        assert candidate["longitudinal_displacement_m"] < baseline["longitudinal_displacement_m"]
    elif case == "B2-cg-height":
        assert candidate["late_front_load_delta_from_static_n"] > 1.2 * baseline["late_front_load_delta_from_static_n"]
        assert candidate["late_front_load_fraction"] > baseline["late_front_load_fraction"]
        # 相同制动容量尚未摩擦饱和；改变CG使实际轴荷变化，平均减速度应保持。
        assert candidate["mean_longitudinal_deceleration_mps2"] == pytest.approx(
            baseline["mean_longitudinal_deceleration_mps2"], rel=.02)
    else:
        assert baseline["stopped"] and candidate["stopped"]
        assert candidate["time_to_stop_s"] > baseline["time_to_stop_s"]
        assert candidate["longitudinal_displacement_m"] > baseline["longitudinal_displacement_m"]
        assert candidate["mean_longitudinal_deceleration_mps2"] < baseline["mean_longitudinal_deceleration_mps2"]
