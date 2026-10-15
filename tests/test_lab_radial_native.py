"""真实查询旧公式与批量路径逐位对照，包含旋转、边缘和腾空。"""

from dataclasses import fields
from itertools import product
from types import SimpleNamespace

import numpy as np
import pytest
from lab_radial_reference import roads_reference, surface_reference
from panda3d.bullet import (
    BulletConvexHullShape,
    BulletPlaneShape,
    BulletRigidBodyNode,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
    BulletWorld,
)
from panda3d.core import BitMask32, TransformState, Vec3
from wheel_contact_kernels import radial_contact_frames, radial_plane_values

from radial_geometry import RadialRoads, RadialSurface
from triangle_support import TriangleSupport
from unsprung_motion import rotation_increment
from vehicle_designs import REFERENCE_DESIGN


def assert_geometry(actual, expected):
    assert actual.hits == expected.hits
    for field in fields(actual)[1:]:
        a,b = getattr(actual,field.name),getattr(expected,field.name)
        assert a.dtype == b.dtype
        assert a.shape == b.shape
        assert a.tobytes() == b.tobytes(), field.name


@pytest.mark.parametrize("layout", ["C","F"])
@pytest.mark.parametrize("scale", [0.,1e-11,1.,100.])
def test_plane_and_contact_frames_keep_original_matrix_and_scalar_rounding(layout, scale):
    rng = np.random.default_rng(17)
    for _ in range(100):
        frame = np.array(rotation_increment(rng.normal(size=3)*.2),order=layout)
        translation = rng.normal(size=3)*scale
        normal = rng.normal(size=3)
        normal /= np.linalg.norm(normal)
        surface = RadialSurface("plane",frame,translation,(),(tuple(normal),float(rng.normal())),None,0.)
        centers = rng.normal(size=(4,6))[:,::2]*scale
        axes = rng.normal(size=(4,6))[:,::2]
        actual = surface.query_plane(centers,axes,REFERENCE_DESIGN)
        for center,axis,a in zip(centers,axes,actual):
            b, = surface_reference(surface,center,axis,REFERENCE_DESIGN)
            assert a[0].hex() == b[0].hex()
            assert a[1].tobytes() == b[1].tobytes()
            assert a[2].tobytes() == b[2].tobytes()
            assert a[3] == b[3]
        roads = SimpleNamespace(config=REFERENCE_DESIGN,surfaces=(surface,))
        up = np.array((0.,0.,1.))
        assert_geometry(RadialRoads.query(roads,centers,up,axes),roads_reference(roads,centers,up,axes))


@pytest.mark.parametrize("altitude", [-1e-11,-0.,0.,1e-11,.01,.4,1.])
def test_mixed_finite_box_and_plane_select_same_surface_and_real_edge(altitude):
    config = REFERENCE_DESIGN
    plane = RadialSurface("plane",np.eye(3),np.zeros(3),(),((0.,0.,1.),0.),None,0.)
    half = (.24,.45,.005)
    box = RadialSurface("box",np.eye(3),np.array((0.,-.45,-.005)),
                        tuple(product(*((-h,h) for h in half))),None,None,0.,half)
    roads = SimpleNamespace(config=config,surfaces=(plane,box))
    axes = np.tile((1.,0.,0.),(4,1))
    for y in np.linspace(-.14,.14,25):
        centers = np.array(((0.,y,.315+altitude),(0.,y+.02,.315+altitude),
                            (0.,y,.4+altitude),(0.,y+2.,2.+altitude)))
        assert_geometry(RadialRoads.query(roads,centers,np.array((0.,0.,1.)),axes),
                        roads_reference(roads,centers,np.array((0.,0.,1.)),axes))


@pytest.mark.parametrize("kernel", [radial_plane_values,radial_contact_frames])
def test_native_geometry_rejects_invalid_array_counts(kernel):
    with pytest.raises(ValueError):
        kernel((),(),4,.33,.11,.01,.003,0.)


@pytest.mark.parametrize("kind", ["hull","triangles"])
def test_actual_world_convex_and_mesh_keep_results_and_solver_failures_after_movement(kind):
    world,body = BulletWorld(),BulletRigidBodyNode("query")
    ground,obstacle = BulletRigidBodyNode("ground"),BulletRigidBodyNode(kind)
    ground.addShape(BulletPlaneShape(Vec3(0.,0.,1.),-1.))
    if kind == "hull":
        shape = BulletConvexHullShape()
        vertices = tuple(tuple(Vec3(*p)) for p in product((-.4,.4),(-.5,.5),(-.02,0.)))
        for point in vertices:
            shape.addPoint(Vec3(*point))
    else:
        triangles = (((-.4,-.5,0.),(.4,-.5,0.),(.4,.5,0.)),
                     ((-.4,-.5,0.),(.4,.5,0.),(-.4,.5,0.)))
        mesh = BulletTriangleMesh()
        for triangle in triangles:
            mesh.addTriangle(*(Vec3(*p) for p in triangle))
        shape = BulletTriangleMeshShape(mesh,dynamic=False)
        obstacle.setPythonTag("suspension_mesh",TriangleSupport.build(triangles))
    shape.setMargin(.01)
    obstacle.addShape(shape)
    if kind == "hull":
        obstacle.setPythonTag("suspension_hull_shapes",tuple(obstacle.getShapes()))
        obstacle.setPythonTag("suspension_hull_vertices",(vertices,))
    for node in (ground,obstacle):
        node.setIntoCollideMask(BitMask32.bit(0))
        world.attachRigidBody(node)
    try:
        seen = set()
        for z in (0.,.08):
            obstacle.setTransform(TransformState.makePosHpr(Vec3(0.,0.,z),Vec3(3.,2.,1.)))
            roads = RadialRoads(world,body,REFERENCE_DESIGN)
            for y in (0.,.48,.55,1.2):
                centers = np.array(((0.,y,.32),(.3,y,.32),(-.5,y,.32),(0.,y,2.)))
                up,axes = np.array((0.,0.,1.)),np.tile((1.,0.,0.),(4,1))
                # 旧一般凸体EPA也可能拒绝边缘；须保留同一失败，不能放宽门槛。
                try:
                    expected = roads_reference(roads,centers,up,axes)
                except ArithmeticError as old_error:
                    with pytest.raises(ArithmeticError) as new_error:
                        roads.query(centers,up,axes)
                    assert str(new_error.value) == str(old_error)
                    continue
                actual = roads.query(centers,up,axes)
                assert_geometry(actual,expected)
                seen.update(hit.node for hit in actual.hits if hit is not None)
        assert obstacle in seen
        world.removeRigidBody(obstacle)
        roads = RadialRoads(world,body,REFERENCE_DESIGN)
        assert all(surface.body != obstacle for surface in roads.surfaces)
    finally:
        for node in tuple(world.getRigidBodies()):
            world.removeRigidBody(node)
