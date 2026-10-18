"""初章由真实试验/独立方案及同车成绩派生，不新造完成标记。"""

from dataclasses import replace

import pytest

import workshop
import workshop_cornering as cornering
from braking_lesson import BrakingScores
from lab_experiment import LabExperiment
from lab_records import LabRecord
from vehicle_designs import REFERENCE_DESIGN
from vehicle_schemes import load_scheme, save_scheme, sync_road_progress
from vehicle_workspace import WorkspaceVehicle
from workshop_journey import read_journey


@pytest.fixture(scope="module")
def trials():
    results = []
    for rule, config in ((workshop, workshop.BASE_CONFIG), (workshop, workshop.build_config(2, False)),
                         (cornering, cornering.BASE_CONFIG), (cornering, cornering.build_config(2, False, False))):
        run = LabExperiment(rule.OPTIONS, config=config)
        try:
            while not run.done:
                run.step()
            results.append(LabRecord.from_run(run))
        finally:
            run.close()
    return results


def schemes(root, trials):
    a, b, c, d = trials
    return (save_scheme(root, "制动70%", b, a, workshop.evaluate(a, b, 2, False)),
            save_scheme(root, "循迹50k", d, c, cornering.evaluate(c, d, 2, False, False)))


def scores(tmp_path, key="car-A"):
    return BrakingScores(tmp_path/"braking-best.json", key)


def test_new_player_has_actionable_five_step_route_without_writing_progress(tmp_path):
    vehicle = WorkspaceVehicle("reference-rwd", REFERENCE_DESIGN)
    data = read_journey(tmp_path/"schemes", vehicle, scores(tmp_path))
    assert data["steps"] == 0 and data["next_index"] == 0 and not data["errors"]
    assert [item["steps"] for item in data["projects"]] == [0, 0, 0]
    assert "A/B" in data["projects"][0]["next"]
    assert not list(tmp_path.iterdir())


def test_real_awards_road_steps_current_car_scores_and_restart(tmp_path, trials):
    brake, corner = schemes(tmp_path/"schemes", trials)
    data = read_journey(tmp_path/"schemes", brake.vehicle, scores(tmp_path))
    assert data["steps"] == 2 and data["next_index"] == 0
    assert data["projects"][0]["scheme_id"] == brake.id
    assert all(item["medal"] == "金" for item in data["projects"][:2])
    for item in (brake, corner):
        sync_road_progress(tmp_path/"schemes", replace(item.vehicle,
            workshop_result={**item.vehicle.workshop_result, "road_validated": True}))
    current_scores = scores(tmp_path)
    current_scores.record(1.8)
    restarted = read_journey(tmp_path/"schemes", load_scheme(tmp_path/"schemes", corner.id).vehicle,
                             scores(tmp_path))
    assert restarted["steps"] == 5 and restarted["next_index"] is None
    assert restarted["projects"][2]["medal"] == "金"
    other_car = read_journey(tmp_path/"schemes", brake.vehicle, scores(tmp_path, "other-hardware"))
    assert other_car["steps"] == 4 and other_car["next_index"] == 2
    assert other_car["projects"][2]["best_error"] is None


def test_legacy_current_vehicle_counts_without_duplicate_and_missing_original_does_not(tmp_path, trials):
    brake, _ = schemes(tmp_path/"schemes", trials)
    legacy = replace(brake.vehicle, scheme_id=None)
    data = read_journey(tmp_path/"empty-library", legacy, scores(tmp_path))
    assert data["steps"] == 1 and data["projects"][0]["vehicle"] == legacy
    bad = replace(legacy, report_path=str(tmp_path/"gone"/"report.html"))
    data = read_journey(tmp_path/"empty-library", bad, scores(tmp_path))
    assert data["steps"] == 0 and data["errors"]
    # 当前车辆已完成而方案回写失败，也不能丢掉已保存的这次完成。
    completed = replace(brake.vehicle, workshop_result={**brake.vehicle.workshop_result, "road_validated": True})
    data = read_journey(tmp_path/"schemes", completed, scores(tmp_path))
    assert data["projects"][0]["steps"] == 2


def test_corrupt_best_scheme_falls_back_to_complete_other_original(tmp_path, trials):
    first, corner = schemes(tmp_path/"schemes", trials)
    alternate = save_scheme(tmp_path/"schemes", "另一个制动版本", trials[1], trials[0], first.challenge)
    sync_road_progress(tmp_path/"schemes", replace(first.vehicle,
        workshop_result={**first.vehicle.workshop_result, "road_validated": True}))
    (first.folder/"trial"/"snapshots.bin").write_bytes(b"broken")
    data = read_journey(tmp_path/"schemes", corner.vehicle, scores(tmp_path))
    assert data["steps"] == 2 and data["errors"]
    assert data["projects"][0]["scheme_id"] == alternate.id
    assert data["projects"][0]["steps"] == 1


def test_bad_score_file_reports_problem_and_keeps_engineering_awards(tmp_path, trials):
    brake, _ = schemes(tmp_path/"schemes", trials)
    (tmp_path/"braking-best.json").write_text("broken", encoding="utf-8")
    data = read_journey(tmp_path/"schemes", brake.vehicle, scores(tmp_path))
    assert data["steps"] == 2 and data["errors"]
    assert data["projects"][2]["steps"] == 0
