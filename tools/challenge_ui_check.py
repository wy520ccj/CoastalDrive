"""预算改装/联合结算/HUD的真实控件渲染；夹具只验排版，不冒充驾驶成绩。"""

import argparse
import json
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from panda3d.core import Filename, OrthographicLens, Point2, Vec3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from application import CoastalDrive
from challenge_build import BuildDraft
from challenge_catalog import CAREER_CHALLENGES, ROAD_CHALLENGES, SPRINT_CHALLENGES, course_gates
from challenge_rules import MedalTarget
from challenge_run import ChallengeStatus, EnergySplit
from driving_tour import LEGS
from highway_run import HighwayResult
from overtake_observations import TrafficReading
from player_road_ab import PlayerRoadAB
from race import GameMode
from session import Phase


def check(output, size, navigation=False, entries=False, ab_controls=False, circuit=False, tour=False, road_feedback=False,
          course_scenes=False, course_route='bend_sprint'):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True, output=output, render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    mode = GameMode(course_route) if course_scenes else GameMode.BEND_SPRINT
    reports = []
    try:
        app.start_sprint(mode)
        spec = SPRINT_CHALLENGES[mode]
        draft = BuildDraft(power=1.1, front_tire=1.15, rear_tire=1.15)
        baseline = asdict(app.session.current)

        def capture(name, labels):
            app.main_menu.resize(app.getAspectRatio())
            app.career_panel.resize(app.getAspectRatio())
            app.tour_panel.resize(app.getAspectRatio())
            app.taskMgr.step()
            for _ in range(6):
                app.graphicsEngine.renderFrame()
            path = output/(name+'.png')
            assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
            bounds = []
            aspect = app.getAspectRatio()
            for label in labels:
                if not label.getText():
                    continue
                lower, upper = label.getTightBounds(app.aspect2d)
                fits = lower.x >= -aspect-.001 and upper.x <= aspect+.001 and lower.z >= -1.001 and upper.z <= 1.001
                bounds.append({'text': label.getText(), 'fits': fits,
                               'lower': list(lower), 'upper': list(upper)})
            assert asdict(app.session.current) == baseline
            reports.append({'image': path.name, 'passed': all(row['fits'] for row in bounds), 'bounds': bounds})

        if course_scenes:
            from environment.expressway_route import anchor, segment_steps

            app.challenge_action('challenge-start')
            while app.session.phase == Phase.COUNTDOWN:
                app.session.countdown_step(360)
            baseline = asdict(app.session.current)
            app.aspect2d.hide()
            scene, simulation = app.scene, app.session.simulation
            for node in (scene.player, *scene.wheels, *scene.traffic, *scene.segment_nodes.values()):
                node.hide()
            curve = simulation.road.curve
            group = scene.render.attachNewNode('course-design-comparison')
            # 仅装配实际渲染分段，不移动车辆、不加载另一套物理世界。
            for index in range(-1, 11):
                node = group.attachNewNode('course-segment-'+str(index))
                for _ in segment_steps(node, index, simulation.seed, scene.expressway_kit, lambda _node: None, curve):
                    pass
                node.setPos(*anchor(curve, index))
            distances = {GameMode.RIDGE_SPRINT: (435., 590., 790.),
                         GameMode.VALLEY_PACE: (300., 520., 780.)}.get(mode, (350., 950.))
            for distance in distances:
                eye, target = curve.sample(distance-14.), curve.sample(distance+25.)
                position = Vec3(eye.x, eye.y, eye.z+3.2)
                app.camera.setPos(position)
                app.camera.lookAt(target.x, target.y, target.z+.5)
                app.camLens.setFov(68.)
                scene.sky.setPos(position)
                scene.update_lighting(position)
                scene.render.prepareScene(app.win.getGsg())
                capture(f'course-{int(distance)}m-static', ())
            xs, ys = [point.x for point in curve.points], [point.y for point in curve.points]
            center = Vec3((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, 0.)
            position = center+Vec3(0, 0, 100)
            lens = OrthographicLens()
            rotated = mode in (GameMode.RIDGE_SPRINT, GameMode.VALLEY_PACE)
            if rotated:
                film_width = max((max(ys)-min(ys))*1.2, (max(xs)-min(xs))*1.2*app.getAspectRatio())
            else:
                film_width = max((max(xs)-min(xs))*1.2, (max(ys)-min(ys))*1.2*app.getAspectRatio())
            lens.setFilmSize(film_width, film_width/app.getAspectRatio())
            lens.setNearFar(.1, 2000.)
            app.cam.node().setLens(lens)
            app.camera.setPos(position)
            if rotated:
                app.camera.lookAt(center, Vec3(-1, 0, 0))
            else:
                app.camera.lookAt(center)
            scene.sky.hide()
            group.setShaderOff(100)
            group.setLightOff(100)
            capture('course-overview-geometry', ())
            endpoints = []
            for distance in (0., curve.length):
                point = curve.sample(distance)
                projected = Point2()
                visible = lens.project(app.cam.getRelativePoint(scene.render, Vec3(point.x, point.y, point.z)), projected)
                endpoints.append({'distance_m': distance, 'projected': list(projected), 'visible': visible})
            (output/'overview-endpoints.json').write_text(json.dumps(endpoints, indent=2)+'\n', encoding='utf-8')
        elif road_feedback:
            for mode in (GameMode.HILL_TRAFFIC, GameMode.VALLEY_PACE):
                app.open_budget_challenge(mode)
                app.challenge_action('challenge-start')
                while app.session.phase == Phase.COUNTDOWN:
                    app.session.countdown_step(360)
                app.apply_scene(app.session.current, 0.)
                app._shown_phase = None
                app.refresh_panel()
                app.layout_driving_buttons()
                baseline = asdict(app.session.current)
                app.career_panel.hide()
                app.main_menu.root.hide()
                app.panel.hide()
                app.hud.root.show()
                road = app.session.highway.snapshot
                spec = ROAD_CHALLENGES[mode]
                status = ChallengeStatus(spec.id, spec.name, spec.budget, 0, 24., 420., .04, 9.5, (),
                                         distance_m=spec.distance_m)
                if mode == GameMode.HILL_TRAFFIC:
                    following = replace(road.overtake, passes=1, distance=420.,
                        traffic_reading=TrafficReading((0, 3), 'front', -2.1, 15., 18., 1., True))
                    returning = replace(following, passes=2, distance=440.,
                        traffic_reading=TrafficReading((0, 3), 'clear', 2., 6., 10., None, False))
                    qualified = replace(returning, passes=3, distance=1900., traffic_reading=None)
                    cases = tuple(
                        (f'hill-traffic-{phase}-feedback-fixture', replace(road, overtake=result,
                            engineering=replace(status, progress_m=result.distance, splits=tuple(
                                EnergySplit(distance, 24.*distance/result.distance, .04*distance/result.distance)
                                for distance in course_gates(mode) if distance <= result.distance))))
                        for phase, result in (
                            ('following', following), ('returning', returning), ('qualified', qualified)))
                else:
                    cases = tuple(
                        (f'valley-{phase}-feedback-fixture', replace(road,
                            sprint=replace(road.sprint, position=position, forward_kph=speed, gates=gates),
                            engineering=replace(status, progress_m=position, splits=tuple(
                                EnergySplit(distance, 24.*distance/position, .04*distance/position)
                                for distance in course_gates(mode)[:gates]))))
                        for phase, position, speed, gates in (
                            ('speed-gate', 218., 64., 0), ('approach', 350., 72., 1),
                            ('inside', 420., 44., 2), ('exit', 652., 45., 3)))
                for name, case in cases:
                    state = app.session.current
                    if case.sprint is not None:
                        state = replace(state, player=replace(state.player, speed=case.sprint.forward_kph/3.6))
                    app.hud.update(state, app.session.race.snapshot, case,
                                   track='endless', countdown='', notice='')
                    app.hud.resize(app.getAspectRatio())
                    view = app.hud.coastal
                    capture(name, (view.title, view.timer, view.checkpoints, view.sector,
                        view.cumulative, view.goal, view.notice, view.speed, view.gear, view.rpm))
                app.back_to_menu()
        elif tour:
            legacy = app.session.race.scores.path.with_name('driving-tour.json')
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_bytes((ROOT/'docs/evidence/COASTAL-TOUR-01/normal/driving-tour.json').read_bytes())
            before = legacy.read_bytes()
            app.open_driving_tour()
            view = app.tour_panel
            capture('tour-overview', tuple(view.labels))
            view.activate(5)
            view.activate(10)
            capture('tour-legacy-history', tuple(view.labels))
            view.activate(6)
            capture('tour-empty-history', tuple(view.labels))
            view.activate(0)
            for index, mode in enumerate(LEGS):
                spec = ROAD_CHALLENGES[mode]
                draft = (BuildDraft(power=1.1), BuildDraft(front_tire=1.15), BuildDraft())[index]
                measured = spec.evaluate(draft, (80., 100., 130.)[index], spec.distance_m*8/100_000)
                status = ChallengeStatus(spec.id, spec.name, spec.budget, draft.cost, measured.seconds,
                    spec.distance_m, measured.litres, measured.consumption, (), measured)
                stage = HighwayResult(finished=True, succeeded=True, engineering=status)
                app.tour_store.accept(mode, app.tour_store.variant, app.tour_physics(), stage)
                view.show(app.tour_store, view.legacy)
                capture(('tour-progress-fixture', 'tour-two-stages-fixture', 'tour-complete-fixture')[index], tuple(view.labels))
            view.activate(5)
            capture('tour-latest-fixture', tuple(view.labels))
            view.activate(7)
            capture('tour-no-official-record', tuple(view.labels))
            with patch.object(Path, 'replace', side_effect=OSError('排版夹具只读')):
                app.tour_store.save()
            view.activate(4)
            capture('tour-save-error-fixture', tuple(view.labels))
            assert legacy.read_bytes() == before
        elif circuit:
            app.back_to_menu()
            app.main_menu.resize(app.getAspectRatio())
            app._shown_phase = None
            app.refresh_panel()
            capture('coastal-menu', tuple(app.main_menu.widgets))
            app.main_menu.actions[0]()
            spec = ROAD_CHALLENGES[GameMode.TIME_TRIAL]
            app.challenge_action('challenge-value', ('power', '110'))
            capture('coastal-build', tuple(app.career_panel.labels))
            draft = app.budget_drafts[GameMode.TIME_TRIAL]
            app.challenge_action('challenge-start')
            app._shown_phase = None
            app.refresh_panel()
            baseline = asdict(app.session.current)
            app.session.pause()
            app._shown_phase = None
            app.refresh_panel()
            capture('coastal-pause', tuple(app.career_panel.labels))
            # 这里只检验五段布局、缺少标定及保存失败反馈，不能当真实一圈成绩。
            splits = tuple(EnergySplit(distance, 90*(index+1)/5, .18*(index+1)/5)
                           for index, distance in enumerate(course_gates(GameMode.TIME_TRIAL)))
            result = spec.evaluate(draft, 90., .18)
            status = ChallengeStatus(spec.id, spec.name, spec.budget, draft.cost, 90., spec.distance_m,
                .18, result.consumption, splits, result, '试跑记录未保存：排版测试夹具。',
                targets=spec.targets, distance_m=spec.distance_m, gate_count=5)
            app.career_panel.show_challenge_result(app.career_progress, spec, status)
            capture('coastal-result-fixture', tuple(app.career_panel.labels))
            app.career_panel.hide()
            app.main_menu.root.hide()
            app.hud.root.show()
            app.hud.resize(app.getAspectRatio())
            app.layout_driving_buttons()
            live = replace(status, seconds=42.7, progress_m=spec.distance_m*.45, litres=.08,
                consumption=100_000*.08/(spec.distance_m*.45), splits=splits[:2], result=None)
            road = replace(app.session.highway.snapshot, engineering=live)
            app.hud.update(app.session.current, app.session.race.snapshot, road,
                           track='coastal', countdown='', notice='')
            view = app.hud.coastal
            capture('coastal-hud-fixture', (view.title, view.timer, view.checkpoints, view.sector,
                                          view.cumulative, view.goal, view.notice))
        elif ab_controls:
            for title, brakes in (('gates', False), ('brakes', True)):
                source = ROOT/'docs/evidence'/('BRAKE-ROAD-AB-01/normal/player-braking-ab.json' if brakes else
                                              'PLAYER-ROAD-AB-01/normal/player-road-ab.json')
                path = output/(title+'-actual.json')
                path.write_bytes(source.read_bytes())
                store = PlayerRoadAB(path, brakes=brakes)
                before = path.read_bytes()
                if brakes:
                    app.player_brake_ab = store
                else:
                    app.player_road_ab = store
                app.open_player_road_ab('brakes' if brakes else 'tires')
                view = app.player_road_panel
                for index, suffix in enumerate(('graph', 'table', 'parameters')):
                    view.set_view(index)
                    capture(title+'-'+suffix, (view.status, view.delta, view.notice, *view.cards,
                            *(view.columns if index == 1 else view.parameters if index == 2 else (view.diagram.detail,))))
                assert path.read_bytes() == before
                view.hide()
            empty = PlayerRoadAB(output/'missing-record.json')
            app.player_road_ab = empty
            app.open_player_road_ab('tires')
            view = app.player_road_panel
            capture('empty', (view.status, view.delta, view.notice, *view.cards))
        elif entries:
            app.open_workshop_garage()
            capture('workshop-entry', ())
            app.workshop_garage.activate(0)
            capture('workshop-budget', tuple(app.career_panel.labels))
            app.challenge_action('challenge-back')
            app.open_career_collection()
            capture('collection-expert-link', tuple(app.career_panel.labels))
            app.back_to_menu()
            app.choose_slalom_lesson(GameMode.FAST_SLALOM)
            capture('slalom-entry', tuple(app.driving_cards.labels))
            source = ROOT/'docs/evidence/PLAYER-ROAD-AB-01/normal/player-road-ab.json'
            path = output/'historical-road-ab.json'
            path.write_bytes(source.read_bytes())
            app.player_road_ab = PlayerRoadAB(path)
            before = path.read_bytes()
            app.open_player_road_ab('tires')
            view = app.player_road_panel
            capture('historical-ab-graph', (view.status, view.delta, view.notice, view.diagram.detail))
            view.toggle_view()
            capture('historical-ab-table', (view.status, view.delta, view.notice, *view.columns))
            assert path.read_bytes() == before
            view.key('escape')
            app.choose_braking_lesson(GameMode.SHORT_BRAKING)
            capture('braking-entry', tuple(app.driving_cards.labels))
            app.back_to_menu()
            app.choose_sprint_routes()
            capture('road-entry', tuple(app.driving_cards.labels))
            app.choose_overtake()
            capture('traffic-entry', tuple(app.driving_cards.labels))
        elif navigation:
            app.open_budget_challenge(GameMode.FAST_SLALOM)
            capture('allowed-group', tuple(app.career_panel.labels))
            spec = SPRINT_CHALLENGES[mode]
            app.career_panel.show_challenge_pause(app.career_progress, spec, draft, None)
            capture('pause-fixture', tuple(app.career_panel.labels))
            spec = CAREER_CHALLENGES['parking']
            result = spec.evaluate(BuildDraft(), 20., .05, metric_value=3.)
            status = ChallengeStatus(spec.id, spec.name, spec.budget, 0, 20., 200., .05,
                result.consumption, (), result, '生涯进度未保存：测试文件访问失败。', assessment=spec.assessment)
            app.career_award = {'saved': False}
            app.career_panel.show_challenge_result(app.career_progress, spec, status)
            capture('save-error-fixture', tuple(app.career_panel.labels))
        else:
            for name, current, tab in (('build', draft, 0), ('wheels', draft, 1),
                                        ('free-setup', draft, 2), ('over-budget', BuildDraft(power=1.2), 0)):
                app.budget_drafts[mode] = current
                app.career_panel.show_challenge(app.career_progress, spec, current, tab)
                capture(name, tuple(app.career_panel.labels))
                if name == 'wheels':
                    app.career_panel.challenge_entries['front_tire']['focus'] = 1
                    capture('wheels-focus', tuple(app.career_panel.labels))
                    app.career_panel.challenge_entries['front_tire']['focus'] = 0
                assert app.budget_drafts[mode] == current
            fixture = replace(spec, targets=(MedalTarget('铜', 90., 10.), MedalTarget('银', 75., 8.2),
                                            MedalTarget('金', 65., 7.)))
            splits = tuple(EnergySplit(d, t, q) for d, t, q in
                           ((450., 14., .0324), (900., 29., .0657), (1350., 44., .10125), (1800., 60., .1332)))
            result = fixture.evaluate(draft, 60., .1332)
            status = ChallengeStatus(spec.id, spec.name, spec.budget, draft.cost, 60., 1800., .1332,
                                     result.consumption, splits, result,
                                     targets=fixture.targets, distance_m=1800.)
            app.career_panel.show_challenge_result(app.career_progress, fixture, status)
            capture('result-fixture', tuple(app.career_panel.labels))
            app.budget_drafts[mode] = draft
            app.challenge_action('challenge-start')
            app.apply_scene(app.session.current, 0.)
            app.hud.resize(app.getAspectRatio())
            app.layout_driving_buttons()
            baseline = asdict(app.session.current)
            app.career_panel.hide()
            app.main_menu.root.hide()
            app.panel.hide()
            app.hud.root.show()
            live = replace(status, seconds=42.73, progress_m=1200., litres=.0816, consumption=6.8,
                           splits=splits[:2], result=None)
            road = replace(app.session.highway.snapshot, engineering=live)
            app.hud.update(app.session.current, app.session.race.snapshot, road,
                           track='endless', countdown='', notice='')
            view = app.hud.coastal
            capture('hud-fixture', (view.title, view.timer, view.checkpoints, view.sector,
                                    view.cumulative, view.goal, view.speed, view.gear, view.rpm))
        report = {'passed': all(row['passed'] for row in reports), 'size': size, 'cases': reports,
                  'scope': '真实控件/展示车/道路Scene；结算与HUD为明示排版夹具，只初始化Scene，无新增正式驾驶，不证明数值平衡/驾驶FPS。'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'passed': report['passed'], 'cases': len(reports)}))
        return report['passed']
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--navigation', action='store_true', help='仅采集本轮暂停/保存失败/专项分类回归')
    parser.add_argument('--entries', action='store_true', help='仅核对统一入口/历史A/B可视化，不新增驾驶')
    parser.add_argument('--ab-controls', action='store_true', help='读取实际历史A/B，核对三视图与空记录')
    parser.add_argument('--circuit', action='store_true', help='滨海预算入口/暂停/五段结算与HUD排版夹具')
    parser.add_argument('--tour', action='store_true', help='预算巡回总览/历史/保存失败排版与真实旧轮次读取')
    parser.add_argument('--road-feedback', action='store_true', help='预算HUD的车流净距/限速带提示排版夹具')
    parser.add_argument('--course-scenes', action='store_true', help='新预算路线实际资源静态追车视角/总览，不移动物理车')
    parser.add_argument('--course-route', choices=('bend_sprint', 'ridge_sprint', 'valley_pace'), default='bend_sprint')
    parser.add_argument('--size', type=int, nargs=2, default=(1672, 941))
    args = parser.parse_args()
    raise SystemExit(0 if check(args.output.resolve(), tuple(args.size), args.navigation, args.entries,
                               args.ab_controls, args.circuit, args.tour, args.road_feedback, args.course_scenes,
                               args.course_route) else 1)
