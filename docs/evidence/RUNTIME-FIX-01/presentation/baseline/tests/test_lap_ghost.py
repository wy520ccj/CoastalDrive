"""轻量记录、插值、版本与文件边界；规则夹具不冒充真实物理圈。"""

import hashlib
import zlib
from dataclasses import replace

import pytest

from lap_ghost import GhostRecorder, ghost_context, load_ghost, save_ghost
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
