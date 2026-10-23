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
    coast, ridge, final = (CareerCourse(key) for key in COURSES)
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
