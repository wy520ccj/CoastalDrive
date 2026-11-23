"""独立赛道路形、弧长、投影和真实碰撞网格。"""

import math

import pytest

import curve_mesh
from career import EVENTS
from career_courses import COURSES, CareerCourse
from traffic import Road


@pytest.mark.parametrize('course_id', COURSES)
def test_course_projection_and_joined_arc_geometry(course_id):
    course = CareerCourse(course_id)
    for distance in range(-50, course.length+51, 7):
        for lateral in (-6.74, 0., 6.74):
            p = course.sample(distance+.25, lateral)
            measured, offset = course.project((p.x, p.y, p.z))
            assert measured == pytest.approx(distance+.25, abs=.08)
            assert offset == pytest.approx(lateral, abs=.01)
            assert course.on_asphalt(p.x, p.y)
    for boundary in (0, course.length):
        a, b = course.sample(boundary-.001), course.sample(boundary+.001)
        assert math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)) < .00201
        assert abs(a.heading-b.heading) < .001


def test_three_course_layouts_are_distinct_and_free_highway_is_preserved():
    coast, ridge, final = (CareerCourse(key) for key in ('coast-club', 'ridge-club', 'coast-final'))
    assert (coast.length, ridge.length, final.length) == (900, 1000, 1800)
    assert max(p.z for p in coast.points)-min(p.z for p in coast.points) == 0
    assert max(p.z for p in ridge.points)-min(p.z for p in ridge.points) >= 25
    assert max(p.heading for p in ridge.points)-min(p.heading for p in ridge.points) >= 140
    assert max(p.heading for p in final.points) >= 140
    for event in EVENTS[3:]:
        road = Road('endless', shape=event.shape)
        assert road.curve.length == event.distance
        vertices, _triangles = curve_mesh.surfaces(road.curve, 2)['road']
        anchor = curve_mesh.anchor(road.curve, 2)
        p = road.curve.sample(400, -6.75)
        assert vertices[0] == pytest.approx((p.x-anchor[0], p.y-anchor[1], p.z-anchor[2]))
    assert Road('endless', shape='hills').curve.sample(500).heading == pytest.approx(0.)
    assert Road('endless', shape='straight').curve is None


def test_hairpin_ground_triangles_have_one_global_owner_and_no_empty_stream_shapes():
    from career_terrain import terrain

    course = CareerCourse('ridge-club')
    meshes = terrain(course.course_id)
    triangles = []
    for vertices, faces in meshes.values():
        for face in faces:
            triangle = tuple(vertices[index] for index in face)
            assert len({(p[0], p[1]) for p in triangle}) == 3
            triangles.append(tuple(sorted(triangle)))
    assert len(triangles) == len(set(triangles))
    for index in range(-6, 12):
        vertices, faces = curve_mesh.surfaces(course, index)['ground']
        assert vertices and faces


def test_budget_bend_matches_design_profile_and_has_real_technical_corners():
    import json
    from pathlib import Path

    profile = json.loads(Path('docs/design/challenge-courses-v2/bend-profile.json').read_text(encoding='utf-8-sig'))
    assert COURSES['budget-bend'] == tuple(tuple(row) for row in profile['sections'])
    course = CareerCourse('budget-bend')
    assert course.length == profile['distance_m'] == 1800
    assert max(point.z for point in course.points) == 0.
    assert max(abs(course.sample(s+1).heading-course.sample(s).heading) for s in range(1800)) > 1.7
    for s in range(1340, 1800):
        assert course.sample(s).heading == -80.


def test_budget_ridge_has_designed_climb_undulations_and_downhill():
    import json
    from pathlib import Path

    profile = json.loads(Path('docs/design/challenge-courses-v2/ridge-profile.json').read_text(encoding='utf-8'))
    assert COURSES['budget-ridge'] == tuple(tuple(row) for row in profile['sections'])
    course = CareerCourse('budget-ridge')
    assert course.length == profile['distance_m'] == 1400
    for distance, height in ((0, 16), (380, 30), (470, 35), (530, 35), (550, 35.3),
                             (570, 35), (590, 35.3), (610, 35), (630, 35.3), (650, 35),
                             (710, 35), (860, 20), (1040, 18), (1140, 20), (1400, 24)):
        point = course.sample(distance)
        assert point.z == pytest.approx(height)
        assert point.grade == pytest.approx(0.)
    assert min(p.grade for p in course.points[710:861]) < -8.5
    assert max(p.grade for p in course.points[180:381]) > 6.
    assert max(abs(course.sample(s+1).heading-course.sample(s).heading) for s in range(1400)) > 1.4


def test_budget_rough_ridge_preserves_dimensions_and_combines_waves_with_turning():
    import json
    from pathlib import Path

    profile = json.loads(Path('docs/design/challenge-courses-v2/ridge-rough-final-profile.json').read_text(encoding='utf-8'))
    assert COURSES['budget-ridge-rough'] == tuple(tuple(row) for row in profile['sections'])
    course = CareerCourse('budget-ridge-rough')
    assert course.length == 1400
    for group in range(10):
        start = 530+12*group
        assert course.sample(start).z == pytest.approx(35.)
        assert course.sample(start+6).z == pytest.approx(35.06)
        assert course.sample(start+12).z == pytest.approx(35.)
    assert course.sample(650).heading-course.sample(530).heading == pytest.approx(30.)
    assert course.sample(1400).z == pytest.approx(24.)
    # 实际显示/碰撞网格保留短波高差，不能被旧5米弦面抹平。
    vertices, _ = curve_mesh.surfaces(course, 2)['road']
    anchor_z = curve_mesh.anchor(course, 2)[2]
    assert vertices[(536-400)*2][2]+anchor_z == pytest.approx(35.06)
    assert vertices[(542-400)*2][2]+anchor_z == pytest.approx(35.)


def test_budget_valley_keeps_speed_rules_and_has_real_downhill_and_climb():
    import json
    from pathlib import Path

    from race import GameMode
    from sprint_routes import SPRINT_ROUTES

    profile = json.loads(Path('docs/design/challenge-courses-v2/valley-profile.json').read_text(encoding='utf-8'))
    assert COURSES['budget-valley'] == tuple(tuple(row) for row in profile['sections'])
    course = CareerCourse('budget-valley')
    assert course.length == profile['distance_m'] == 1000
    for distance, height in ((0, 30), (100, 30), (250, 22), (350, 12),
                             (400, 12), (650, 12), (750, 20), (850, 30), (1000, 30)):
        point = course.sample(distance)
        assert point.z == pytest.approx(height)
        assert point.grade == pytest.approx(0.)
    assert min(p.grade for p in course.points[250:351]) < -8.5
    assert max(p.grade for p in course.points[750:851]) > 8.5
    assert min(p.z for p in course.points) == 12.
    route = SPRINT_ROUTES[GameMode.VALLEY_PACE]
    assert route.entry_kph == profile['entry_kph'] == 60.
    assert (route.speed_zone.start, route.speed_zone.end, route.speed_zone.minimum_kph,
            route.speed_zone.maximum_kph) == tuple(profile['speed_zone'])
    assert route.gates == tuple(profile['splits_m'])


@pytest.mark.parametrize('name, course_id, turn, rise', (
    ('ridge-suspension-profile.json', 'budget-ridge-suspension', 60., .06),
    ('ridge-suspension-30-012-profile.json', 'budget-ridge-long-waves', 30., .12),
))
def test_continuous_rough_bend_matches_design_and_real_collision_surface(name, course_id, turn, rise):
    import json
    from pathlib import Path

    profile = json.loads((Path('docs/design/challenge-courses-v2') / name).read_text(encoding='utf-8'))
    course = CareerCourse(course_id)
    assert COURSES[course_id] == tuple(tuple(row) for row in profile['sections'])
    assert course.length == profile['distance_m'] == 1400
    assert course.sample(770).heading-course.sample(530).heading == pytest.approx(turn)
    for group in profile['rough_groups']:
        for start in range(group['start_m'], group['end_m'], group['period_m']):
            assert course.sample(start).z == pytest.approx(35.)
            assert course.sample(start+group['period_m']/2).z == pytest.approx(35.+rise)
            assert course.sample(start+group['period_m']).z == pytest.approx(35.)
    for distance, height in ((830, 35), (980, 20), (1160, 18), (1260, 20), (1400, 24)):
        assert course.sample(distance).z == pytest.approx(height)
    # 第二种周期跨越分段边界，实际共用网格也须保留峰值与段端连续性。
    vertices, _ = curve_mesh.surfaces(course, 3)['road']
    anchor_z = curve_mesh.anchor(course, 3)[2]
    assert vertices[(606-600)*2][2]+anchor_z == pytest.approx(35.+rise)
    previous, _ = curve_mesh.surfaces(course, 2)['road']
    a = curve_mesh.anchor(course, 2)
    b = curve_mesh.anchor(course, 3)
    assert tuple(previous[-2][i]+a[i] for i in range(3)) == pytest.approx(
        tuple(vertices[0][i]+b[i] for i in range(3)))
