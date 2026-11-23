"""轻量记录、插值、版本与文件边界；规则夹具不冒充真实物理圈。"""

import hashlib
import json
import zlib
from dataclasses import replace

import pytest

from challenge_build import BuildDraft
from challenge_catalog import ROAD_CHALLENGES
from challenge_run import EnergySplit
from challenge_scores import ChallengeScores
from lap_ghost import GhostRecorder, ghost_context, load_ghost, record_context, save_ghost
from race import BestTimes, GameMode, RaceSnapshot
from simulation import Snapshot
from vehicle_state import FIXED_DT, CarState, WheelState


def sample(index):
    wheels = tuple(WheelState((side, index*.5, -.1), (1. if index%2 == 0 else -1., 0., 0., 0.))
                   for side in (-1., 1., -1., 1.))
    car = CarState((0., index*.5, .42), heading=179. if index == 0 else -179., wheels=wheels)
    return Snapshot(100+index, (100+index)*FIXED_DT, car, ())


def recorded_lap(seconds=.025):
    recorder = GhostRecorder(sample(0), {"seed": 0, "bits": 32, "source": "fixture"})
    for index in range(1, 4):
        recorder.append(sample(index))
    race = RaceSnapshot(mode=GameMode.TIME_TRIAL, finished=True, new_best=True,
                        last_lap=seconds, splits=(seconds/2, seconds))
    return recorder.finish("fixture-course", race)


def store(tmp_path, lap):
    scores = BestTimes(tmp_path/"scores.json")
    scores.record(GameMode.TIME_TRIAL, lap.seconds, lap.score_id, splits=lap.splits)
    path = save_ghost(lap, scores, GameMode.TIME_TRIAL)
    return scores, path


def test_roundtrip_keeps_every_pose_and_shortest_angle_interpolation(tmp_path):
    lap = recorded_lap()
    scores, path = store(tmp_path, lap)
    loaded = load_ghost(BestTimes(scores.path), GameMode.TIME_TRIAL, lap.score_id,
                        lap.context, lap.seconds, lap.splits)
    assert loaded == lap and loaded.frames == 4 and path.exists()
    pose = loaded.pose_at(FIXED_DT/2)
    assert pose.position == pytest.approx((0., .25, .42))
    assert pose.hpr[0] == 180.
    assert pose.wheels[0].orientation == (1., 0., 0., 0.)
    assert loaded.pose_at(loaded.seconds).position == sample(3).player.position
    assert loaded.pose_at(-.001) is None and loaded.pose_at(.026) is None


def test_missing_or_corrupt_file_and_incompatible_context_do_not_relabel_ghost(tmp_path):
    lap = recorded_lap()
    scores, path = store(tmp_path, lap)
    with pytest.raises(ValueError, match="条件"):
        load_ghost(scores, GameMode.TIME_TRIAL, lap.score_id, {**lap.context, "bits": 64}, lap.seconds, lap.splits)
    with pytest.raises(ValueError, match="成绩"):
        load_ghost(scores, GameMode.TIME_TRIAL, lap.score_id, lap.context, lap.seconds+.001, lap.splits)
    original = path.read_bytes()
    path.write_bytes(original[:-1])
    with pytest.raises(ValueError, match="损坏"):
        load_ghost(scores, GameMode.TIME_TRIAL, lap.score_id, lap.context, lap.seconds, lap.splits)
    path.unlink()
    with pytest.raises(FileNotFoundError):
        load_ghost(scores, GameMode.TIME_TRIAL, lap.score_id, lap.context, lap.seconds, lap.splits)
    assert scores.get(GameMode.TIME_TRIAL, lap.score_id) == lap.seconds


def test_new_best_unlinks_old_ghost_even_when_new_ghost_save_fails(tmp_path, monkeypatch):
    old = recorded_lap()
    scores, old_path = store(tmp_path, old)
    new = recorded_lap(.022)
    scores.record(GameMode.TIME_TRIAL, new.seconds, new.score_id, splits=new.splits)
    assert BestTimes(scores.path).ghost_digest(GameMode.TIME_TRIAL, new.score_id) is None
    monkeypatch.setattr(scores, "attach_ghost", lambda *args: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        save_ghost(new, scores, GameMode.TIME_TRIAL)
    assert load_ghost(BestTimes(scores.path), GameMode.TIME_TRIAL, new.score_id,
                       new.context, new.seconds, new.splits) is None
    assert old_path.exists()


def test_ghost_cannot_attach_to_another_lap_and_slower_lap_keeps_link(tmp_path):
    lap = recorded_lap()
    scores, _ = store(tmp_path, lap)
    digest = scores.ghost_digest(GameMode.TIME_TRIAL, lap.score_id)
    scores.record(GameMode.TIME_TRIAL, .03, lap.score_id, splits=(.01, .03))
    assert scores.ghost_digest(GameMode.TIME_TRIAL, lap.score_id) == digest
    with pytest.raises(ValueError, match="改变"):
        scores.attach_ghost(GameMode.TIME_TRIAL, lap.score_id, .03, (.01, .03), digest)


def test_budget_ghost_follows_fastest_complete_run_across_builds(tmp_path):
    mode = GameMode.TIME_TRIAL
    spec = ROAD_CHALLENGES[mode]
    lap = recorded_lap()
    scores = ChallengeScores(tmp_path/'challenge-best.json', spec, 'keyboard', lap.context)
    splits = (EnergySplit(spec.distance_m/2, lap.splits[0], .03),
              EnergySplit(spec.distance_m, lap.seconds, .06))
    assert scores.record(spec.evaluate(BuildDraft(), lap.seconds, .06), splits=splits)
    best = scores.completed['fastest']
    lap = replace(lap, score_id=best['run_id'])
    save_ghost(lap, scores, mode)
    scores.record(spec.evaluate(BuildDraft(mass=.96), .03, .05))
    restored = ChallengeScores(scores.path, spec, 'keyboard', lap.context)
    assert restored.completed['economy']['build']['mass'] == .96
    assert load_ghost(restored, mode, lap.score_id, lap.context, lap.seconds, lap.splits) == lap
    other_input = ChallengeScores(scores.path, spec, 'gamepad', lap.context)
    assert load_ghost(other_input, mode, lap.score_id, lap.context, lap.seconds, lap.splits) is None
    restored.record(spec.evaluate(BuildDraft(front_tire=1.3), .022, .07))
    assert not restored.ghost_digest(mode, restored.completed['fastest']['run_id'])
    assert not restored.ghost_digest(mode, lap.score_id)
    before = restored.path.read_bytes()
    with pytest.raises(ValueError, match='最快完赛已改变'):
        restored.attach_ghost(mode, lap.score_id, lap.seconds, lap.splits, 'f'*64)
    assert restored.path.read_bytes() == before


def test_sampling_requires_consecutive_authority_ticks_and_full_valid_finish(monkeypatch):
    recorder = GhostRecorder(sample(0), {})
    with pytest.raises(ValueError, match="连续"):
        recorder.append(sample(2))
    recorder.append(sample(1))
    invalid = RaceSnapshot(finished=True, new_best=False, last_lap=FIXED_DT, splits=(FIXED_DT,))
    with pytest.raises(ValueError):
        recorder.finish("test", invalid)
    with pytest.raises(ValueError):
        recorder.finish("test", replace(invalid, new_best=True, invalidated=True))
    monkeypatch.setattr("lap_ghost.MAX_TICKS", 1)
    recorder.append(sample(2))
    assert recorder.notice and recorder.frames == 0


def test_invalid_compression_and_record_size_are_checked(tmp_path, monkeypatch):
    lap = recorded_lap()
    scores, _ = store(tmp_path, lap)
    blob = b"CDG1invalid compression"
    digest = hashlib.sha256(blob).hexdigest()
    (tmp_path/"ghosts"/(digest+".cdg")).write_bytes(blob)
    scores.attach_ghost(GameMode.TIME_TRIAL, lap.score_id, lap.seconds, lap.splits, digest)
    with pytest.raises(ValueError, match="压缩"):
        load_ghost(scores, GameMode.TIME_TRIAL, lap.score_id, lap.context, lap.seconds, lap.splits)
    monkeypatch.setattr("lap_ghost.MAX_BYTES", 10)
    with pytest.raises(ValueError, match="过大"):
        load_ghost(scores, GameMode.TIME_TRIAL, lap.score_id, lap.context, lap.seconds, lap.splits)


def test_decompression_limit_rejects_expanding_content(tmp_path, monkeypatch):
    lap = recorded_lap()
    scores, _ = store(tmp_path, lap)
    blob = b"CDG1"+zlib.compress(b"a"*1000)
    digest = hashlib.sha256(blob).hexdigest()
    (tmp_path/"ghosts"/(digest+".cdg")).write_bytes(blob)
    scores.attach_ghost(GameMode.TIME_TRIAL, lap.score_id, lap.seconds, lap.splits, digest)
    monkeypatch.setattr("lap_ghost.MAX_BYTES", 200)
    with pytest.raises(ValueError, match="超限"):
        load_ghost(scores, GameMode.TIME_TRIAL, lap.score_id, lap.context, lap.seconds, lap.splits)


def test_compatibility_tracks_model_dependencies_but_not_presentation(tmp_path, monkeypatch):
    source = tmp_path/"src"
    source.mkdir()
    for name in ("simulation", "driving_modes", "controls", "race"):
        (source/(name+".py")).write_text("import model\n", encoding="utf-8")
    (source/"model.py").write_text("stiffness = 1\n", encoding="utf-8")
    (source/"scene.py").write_text("color = 1\n", encoding="utf-8")
    monkeypatch.setattr("lap_ghost.resource_root", lambda: tmp_path)
    original = ghost_context(0)
    (source/"scene.py").write_text("color = 2\n", encoding="utf-8")
    assert ghost_context(0) == original
    (source/"model.py").write_text("stiffness = 2\n", encoding="utf-8")
    assert ghost_context(0) != original
    (source/"model.py").write_text("import extra\nstiffness = 2\n", encoding="utf-8")
    (source/"extra.py").write_text("ratio = 1\n", encoding="utf-8")
    expanded = ghost_context(0)
    assert str((source/'extra.py').relative_to(tmp_path)) in expanded['source_files']
    (source/"extra.py").write_text("ratio = 2\n", encoding="utf-8")
    assert ghost_context(0) != expanded
    package = source/'package'
    package.mkdir()
    (package/'__init__.py').write_text('from . import part\n', encoding='utf-8')
    (package/'part.py').write_text('ratio = 1\n', encoding='utf-8')
    (source/'model.py').write_text('import package\n', encoding='utf-8')
    packaged = ghost_context(0)
    assert str((package/'part.py').relative_to(tmp_path)) in packaged['source_files']
    (package/'part.py').write_text('ratio = 2\n', encoding='utf-8')
    assert ghost_context(0) != packaged


def test_record_context_only_reuses_the_verified_source_for_each_rule(tmp_path, monkeypatch):
    monkeypatch.setattr("lap_ghost.resource_root", lambda: tmp_path)
    folder = tmp_path/"assets"/"game"/"rules"
    folder.mkdir(parents=True)
    (folder/"record-context-aliases.json").write_text(
        json.dumps({"a"*64: {"default": "b"*64, GameMode.DISTANCE_CHALLENGE.value: "c"*64}}),
        encoding="utf-8",
    )
    source = {"source": "a"*64, "seed": 17, "bits": 64, "runtime_files": {"library": "d"*64}}
    assert record_context(source, GameMode.TIME_TRIAL) == {**source, "source": "b"*64}
    assert record_context(source, GameMode.DISTANCE_CHALLENGE) == {**source, "source": "c"*64}
    assert source["source"] == "a"*64
    different = {**source, "source": "e"*64}
    assert record_context(different, GameMode.TIME_TRIAL) == different


def test_packaged_record_context_reuses_group_only_for_matching_program(tmp_path, monkeypatch):
    monkeypatch.setattr("lap_ghost.resource_root", lambda: tmp_path)
    monkeypatch.setattr("lap_ghost.sys.frozen", True, raising=False)
    game = tmp_path/"coastaldrive.exe"
    game.write_bytes(b"first package")
    first = ghost_context(0)
    (tmp_path/"coastaldrive-check.exe").write_bytes(b"diagnostic")
    assert ghost_context(0) == first
    (tmp_path/"release.json").write_text(json.dumps({
        "record_source": {"package": first["source"], "gameplay": "a"*64},
    }), encoding="utf-8")
    assert record_context(first, GameMode.TIME_TRIAL) == {**first, "source": "a"*64}

    game.write_bytes(b"different package")
    different = ghost_context(0)
    assert different["source"] != first["source"]
    assert record_context(different, GameMode.TIME_TRIAL) == different
