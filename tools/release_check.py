"""在源码或冻结包中复用真实窗口、独立物理进程和实验台往返检查。"""

import argparse
import hashlib
import json
import multiprocessing
import os
from dataclasses import replace
from math import isclose
from pathlib import Path

from workspace_transition_check import check, require


def challenge_preview(output):
    from application import CoastalDrive
    from career import EVENT_BY_ID
    from environment.career_coast import _data
    from race import GameMode
    from session_process import SessionProcess
    from streamed_road import ROAD_EDGE_ADJUSTMENT_AVAILABLE

    output.mkdir(parents=True, exist_ok=True)
    require(ROAD_EDGE_ADJUSTMENT_AVAILABLE, "冻结包没有赛道路面修正")
    for course in ("coast-club", "coast-final"):
        require(len(_data(course)["faces"]) > 0, f"生涯表现网格为空：{course}")
    app = CoastalDrive(smoke=True, output=output, independent_clock=True)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    try:
        require(isinstance(app.session, SessionProcess), "冻结包未创建独立物理进程")
        app.back_to_menu()
        app.start_sprint(GameMode.VALLEY_PACE)
        labels = [label.getText() for label in app.career_panel.labels]
        require(any("375米≥80" in text for text in labels), "山谷赛前显示旧规则")
        app.challenge_action("challenge-auto")
        app.session.pause()
        require(app.session.road_shape == "budget-valley" and app.budget_auto, "山谷试车未启动")
        valley = app.session.highway.snapshot.sprint
        if valley is None:
            # 计时前尚未创建赛事裁判，临时进入短计时会话核对权威门位。
            spec, build, *_ = app.career_panel.challenge_data
            app.session.start(mode=GameMode.VALLEY_PACE, track="endless", countdown=False,
                              challenge_spec=spec, build=build)
            app.session.pause()
            valley = app.session.highway.snapshot.sprint
        require(valley is not None and valley.rules_version == "budget-valley-braking-v1", "物理进程使用旧山谷规则")
        app.back_to_menu()
        app.start_sprint(GameMode.RIDGE_SPRINT)
        app.challenge_action("challenge-start")
        app.session.pause()
        ridge = app.session.road_shape
        require(ridge == "budget-ridge-long-waves", "物理进程退回旧山脊")
        app.back_to_menu()
        app.start_career_event("first-drive")
        require(app.career_panel.page == "challenge", "生涯未进入预算赛前页")
        app.challenge_action("challenge-auto")
        app.session.pause()
        require(app.session.mode == GameMode.CAREER and app.budget_auto, "生涯试车未启动")
        return {"passed": True, "independent_pid": app.session.process.pid,
                "valley": valley.rules_version, "ridge": ridge, "career": EVENT_BY_ID["first-drive"].id,
                "career_meshes": ["coast-club", "coast-final"]}
    finally:
        app.close_game()


def record_upgrade(output, previous, *, reuse_save=False):
    from application import CoastalDrive
    from challenge_build import BuildDraft
    from challenge_catalog import ROAD_CHALLENGES, course_gates
    from challenge_run import ChallengeStatus, EnergySplit
    from lap_ghost import ghost_context, packaged_source_paths, record_context, source_digest
    from race import GameMode

    mode = GameMode.VALLEY_PACE
    spec, gates = ROAD_CHALLENGES[mode], course_gates(mode)
    old_paths = packaged_source_paths(previous)
    require((previous / "coastaldrive.exe").is_file(), "上一版游戏程序不存在")
    app = CoastalDrive(smoke=True, output=output)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    try:
        app.back_to_menu()
        app.start_sprint(mode)
        app.challenge_action("challenge-start")
        actual = ghost_context(app.session.seed)
        for name, digest in actual["runtime_files"].items():
            library = previous / name.rsplit("/", 1)[-1]
            require(library.is_file() and hashlib.sha256(library.read_bytes()).hexdigest() == digest,
                    f"上一版运行库不同：{name}")
        previous_raw = {**actual, "source": source_digest(previous, old_paths),
                        "source_files": [str(path.relative_to(previous)) for path in sorted(old_paths)]}
        require(actual["source"] != previous_raw["source"], "诊断须使用两个不同的构建")
        old = record_context(previous_raw, mode, package_root=previous)
        require(record_context(actual, mode) == old, "新版未继承上一版成绩分组")
        # 用上一版真实包的分组构造隔离存档，检查新版正常入口是否能继续读档。
        result = spec.evaluate(BuildDraft(), 60., .2)
        splits = tuple(EnergySplit(gate, result.seconds*gate/spec.distance_m,
                                   result.litres*gate/spec.distance_m) for gate in gates)
        saved = app.session.challenge_scores(old)
        if reuse_save:
            require(saved.reference is not None and saved.reference['seconds'] == result.seconds,
                    "未找到上一版程序已保存的成绩夹具")
        else:
            require(bool(saved.record(result, splits=splits)), "旧版成绩夹具未保存")
        require(app.session.challenge_scores().reference == saved.reference, "个人最佳未读回")
        if not reuse_save:
            trial = replace(result, official=False, medal="", next_target=None)
            status = ChallengeStatus(spec.id, spec.name, spec.budget, result.cost, result.seconds, spec.distance_m,
                                     result.litres, result.consumption, splits, trial)
            group = (*app._automatic_trial_group()[:-1], old)
            require(app.auto_trials.save(group, spec, gates, status), "旧版试车夹具未保存")
        app.challenge_action("challenge-adjust")
        app.challenge_action("challenge-auto")
        reference = app.auto_trial_reference
        require(reference is not None and reference.result.seconds == result.seconds and reference.splits == splits,
                "自动试车未读回上一版对照")
        return {"passed": True, "reused_save": reuse_save, "previous": previous_raw["source"], "package": actual["source"],
                "previous_record_source": old["source"],
                "record_source": record_context(actual, mode)["source"], "best_seconds": result.seconds,
                "trial_seconds": reference.result.seconds}
    finally:
        app.close_game()


def season_replay(output, traces, cup_stage):
    """离屏重放实跑操控。主赛和每一站单独启动本工具，共用隔离存档。"""
    from panda3d.core import Filename

    from application import CoastalDrive
    from career import EVENTS
    from season_cup import CUP_LEGS
    from session import Phase
    from vehicle_state import Control

    output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, output=output)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    rows = []

    def drive(event_id):
        files = tuple(traces.glob(event_id+'-*.json'))
        require(len(files) == 1, f'{event_id}须有一份完整原始记录')
        document = json.loads(files[0].read_bytes())
        expected = document['result']
        require(expected['official'] and expected['medal'] and document['controller'] == 'keyboard',
                f'{event_id}须使用正常计分入口的完赛记录')
        for _ in range(360):
            app.session.tick()
        require(app.session.phase == Phase.DRIVING, f'{event_id}未正常发车')
        inputs = iter(Control(*sample[9:13]) for sample in document['samples'][1:])
        sample = app.session.keyboard.sample
        app.session.keyboard.sample = lambda state, dt: next(inputs)
        try:
            for _ in document['samples'][1:]:
                app.session.tick()
                if app.session.phase == Phase.RESULTS:
                    break
        finally:
            app.session.keyboard.sample = sample
        require(app.session.phase == Phase.RESULTS, f'{event_id}未进入结算')
        app._shown_phase = None
        app.refresh_panel()
        result = app.session.highway.snapshot.engineering.result
        require(result.official and result.medal == expected['medal'] and app.session.current.collisions == 0
                and isclose(result.seconds, expected['seconds'], rel_tol=0., abs_tol=1e-8)
                and isclose(result.litres, expected['litres'], rel_tol=0., abs_tol=1e-9),
                f'{event_id}包内结算与原始实跑不同：{result}')
        rows.append({'event': event_id, 'medal': result.medal, 'seconds': result.seconds,
                     'fuel_litres': result.litres, 'career_stars': app.career_progress.stars})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)

    try:
        if cup_stage == 0:
            require(app.career_progress.stars == 0, '生涯重放须从空档开始')
            app.open_career()
            for event in EVENTS:
                app.career_action('brief', event.id)
                app.career_panel.key('enter')
                drive(event.id)
                app.challenge_action('challenge-back')
            require(app.career_progress.stars == 15, '空档六场生涯结束后星级不对')
        else:
            mode = CUP_LEGS[cup_stage-1]
            if cup_stage == 1:
                app.career_action('cup-menu')
                app.career_action('cup-pick')
                app.career_action('cup-preview', 'coastal-hatch')
                app.career_panel.key('enter')
            else:
                app.continue_career()
            require(app.cup_store is not None and len(app.cup_store.current) == cup_stage-1
                    and app.cup_store.specs[mode].design_id == 'coastal-hatch', '综合杯未从本车磁盘档进入对应站')
            app.career_panel.key('enter')
            app.challenge_action('challenge-start')
            drive(mode.value)
            require(len(app.cup_store.current) == cup_stage, '综合杯本次成绩未保存')
            if cup_stage == len(CUP_LEGS):
                app.challenge_action('tour-next')
                require(app.career_panel.cup_page['recap'] and app.season_continuation()[0] == '第一季结算',
                        '完成综合杯后未进入赛季结算')
                for _ in range(6):
                    app.taskMgr.step()
                app.graphicsEngine.syncFrame()
                screenshot = Filename.fromOsSpecific(str(output/'season-recap.png'))
                require(app.win.getScreenshot().write(screenshot), '冻结包赛季结算截图未保存')
        return {'passed': True, 'cup_stage': cup_stage, 'process': os.getpid(), 'results': rows}
    finally:
        app.close_game()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    diagnostics = parser.add_mutually_exclusive_group()
    diagnostics.add_argument("--challenge-preview", action="store_true", help="离屏检查冻结版挑战入口")
    diagnostics.add_argument("--previous-preview", type=Path, help="离屏检查与上一版游戏目录的成绩衔接")
    diagnostics.add_argument("--season-replay", type=Path, help="用原始实跑输入重放第一季，参数为记录目录")
    parser.add_argument("--cup-stage", type=int, choices=(1, 2, 3), help="从磁盘档接续综合杯对应站")
    parser.add_argument("--reuse-preview-save", action="store_true", help="读取上一版诊断实际写入的隔离存档")
    args = parser.parse_args()
    if args.cup_stage is not None and args.season_replay is None:
        parser.error("--cup-stage 须与 --season-replay 一起使用")
    if args.reuse_preview_save and args.previous_preview is None:
        parser.error("--reuse-preview-save 须与 --previous-preview 一起使用")
    output = args.output.resolve()
    os.environ["LOCALAPPDATA"] = str(output / "user-data")
    if args.previous_preview is not None:
        result = record_upgrade(output, args.previous_preview.resolve(), reuse_save=args.reuse_preview_save)
        (output / "record-upgrade.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    elif args.challenge_preview:
        result = challenge_preview(output)
    elif args.season_replay is not None:
        stage = args.cup_stage or 0
        result = season_replay(output, args.season_replay.resolve(), stage)
        (output/f"season-replay-{stage}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                                        encoding="utf-8")
    else:
        result = check(output, onscreen=True, independent=True)
    print(json.dumps(result, ensure_ascii=False))
