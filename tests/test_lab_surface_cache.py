"""同子步几何复用对原完整查询逐位核对，并检查布局、失效范围和保存边界。"""

import json
import pickle
import weakref
from dataclasses import fields
from itertools import product
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from lab_surface_cache_reference import query_reference
from panda3d.bullet import BulletRigidBodyNode
from panda3d.core import TransformState, Vec3
from physics.unsprung_step_checkpoint import load_step, save_step
from test_finite_radial_contact import contact_case
from test_lab_crossover_diagnostics import DIAGNOSTIC
from test_lab_radial_native import (
    test_actual_world_convex_and_mesh_keep_results_and_solver_failures_after_movement as world_case,
)

from lab_experiment import LabExperiment, LabOptions
from radial_geometry import RadialRoads, RadialSurface
from unsprung_contact_geometry import FiniteRadialContact
from unsprung_motion import rotation_increment
from vehicle_designs import REFERENCE_DESIGN, vehicle_design
from vehicle_parameters import config_from_document
from vehicle_unsprung import UnsprungAdvanceInput


class TraceSurface:
    def __init__(self,surface):
        self.surface,self.body,self.plane = surface,surface.body,surface.plane
        self.rows = 0

    def query_plane(self,centers,axes,config):
        self.rows += len(centers)
        return self.surface.query_plane(centers,axes,config)

    def query(self,center,axis,config):
        self.rows += 1
        return self.surface.query(center,axis,config)


def assert_geometry(actual,expected):
    assert actual.hits == expected.hits
    for field in fields(actual)[1:]:
        a,b = getattr(actual,field.name),getattr(expected,field.name)
        assert a.dtype == b.dtype and a.shape == b.shape
        assert a.tobytes() == b.tobytes(),field.name


def layout(values,kind):
    if kind in ('C','F'):return np.array(values,order=kind)
    if kind=='reverse':return np.array(values[:,::-1])[:,::-1]
    storage = np.empty((len(values),6))
    storage[:,::2] = values
    return storage[:,::2]


def surfaces(frame_layout,kind):
    frame = np.array(rotation_increment(np.array((.01,-.02,.03))),order=frame_layout)
    plane = RadialSurface('plane',frame,np.zeros(3),(),((0.,0.,1.),0.),None,0.)
    half = (.24,.45,.005)
    box = RadialSurface('box',frame,np.array((0.,-.45,-.005)),tuple(product(*((-h,h) for h in half))),
                        None,None,0.,half)
    return {'plane':(plane,),'box':(box,),'mixed':(plane,box)}[kind]


@pytest.mark.parametrize('frame_layout',['C','F'])
@pytest.mark.parametrize('input_layout',['C','F','strided','reverse'])
@pytest.mark.parametrize('kind',['plane','box','mixed'])
def test_partial_and_full_hits_match_original_bits_and_never_alias_output(frame_layout,input_layout,kind):
    raw = surfaces(frame_layout,kind)
    traced = tuple(TraceSurface(s) for s in raw)
    roads = SimpleNamespace(config=REFERENCE_DESIGN,surfaces=traced)
    reference = SimpleNamespace(config=REFERENCE_DESIGN,surfaces=raw)
    cache = [{} for _ in raw]
    centers = layout(np.array(((0.,-.09,.315),(.04,-.07,.315),(-.04,-.02,.4),(0.,2.,2.))),input_layout)
    axes = layout(np.tile((1.,0.,0.),(4,1)),input_layout)
    up = np.array((0.,0.,1.))
    for step in range(6):
        if step==2:centers[1,2] += 1e-5
        if step==4:up = np.array((0.,.1,np.sqrt(.99)))
        actual = RadialRoads.query(roads,centers,up,axes,surface_cache=cache)
        assert_geometry(actual,query_reference(reference,centers,up,axes))
        assert all(surface.rows==(4 if step<2 else 5) for surface in traced)
        # 调用者可以改自己的输出，下一次命中不能读回这些改动。
        for field in fields(actual)[1:]:getattr(actual,field.name)[:] = 71.


@pytest.mark.parametrize('kind',['plane','box'])
def test_key_distinguishes_signed_zero_neighbor_ulp_and_vector_layout(kind):
    raw = surfaces('C',kind)
    traced = TraceSurface(raw[0])
    roads = SimpleNamespace(config=REFERENCE_DESIGN,surfaces=(traced,))
    reference = SimpleNamespace(config=REFERENCE_DESIGN,surfaces=raw)
    cache = [{}]
    centers = np.array(((0.,-.09,.315),(.04,-.07,.315),(-.04,-.02,.4),(0.,2.,2.)))
    axes,up = np.tile((1.,0.,0.),(4,1)),np.array((0.,0.,1.))
    expected_rows = (4,5,6,7,11,15)
    for step in range(6):
        if step==1:centers[0,0] = -0.
        if step==2:centers[0,0] = np.nextafter(0.,1.)
        if step==3:axes[0,1] = -0.
        if step==4:centers,axes = layout(centers,'F'),layout(axes,'F')
        if step==5:centers,axes = layout(centers,'reverse'),layout(axes,'reverse')
        assert_geometry(RadialRoads.query(roads,centers,up,axes,surface_cache=cache),
                        query_reference(reference,centers,up,axes))
        assert traced.rows==expected_rows[step]


def test_dtype_boundary_keeps_native_error_and_separates_later_valid_input():
    raw = surfaces('C','plane')
    traced = TraceSurface(raw[0])
    roads = SimpleNamespace(config=REFERENCE_DESIGN,surfaces=(traced,))
    cache = [{}]
    centers,axes = np.zeros((4,3)),np.tile((1.,0.,0.),(4,1))
    with pytest.raises(ValueError):
        RadialRoads.query(roads,centers.astype(np.float32),np.array((0.,0.,1.)),axes,surface_cache=cache)
    actual = RadialRoads.query(roads,centers,np.array((0.,0.,1.)),axes,surface_cache=cache)
    assert_geometry(actual,query_reference(SimpleNamespace(config=REFERENCE_DESIGN,surfaces=raw),
                                          centers,np.array((0.,0.,1.)),axes))
    assert traced.rows==8


@pytest.mark.parametrize('failure',[False,True])
def test_empty_candidates_are_cached_but_partial_failures_are_not(failure):
    class Surface:
        plane,body = None,'surface'
        calls = 0

        def query(self,center,axis,config):
            self.calls += 1
            if failure:
                yield 0.,np.array((0.,0.,1.)),center,None
                raise ArithmeticError('原候选未能完成')

    surface = Surface()
    roads = SimpleNamespace(config=REFERENCE_DESIGN,surfaces=(surface,))
    centers,axes = np.arange(12,dtype=float).reshape(4,3),np.tile((1.,0.,0.),(4,1))
    cache = [{}]
    for _ in range(2):
        if failure:
            with pytest.raises(ArithmeticError,match='原候选未能完成'):
                RadialRoads.query(roads,centers,np.array((0.,0.,1.)),axes,surface_cache=cache)
            assert not cache[0]
        else:
            up = np.array((0.,.1,np.sqrt(.99)))
            assert_geometry(RadialRoads.query(roads,centers,up,axes,surface_cache=cache),query_reference(roads,centers,up,axes))
    # 参考路径另有八次空查询；错误路径从未成功缓存第一行。
    assert surface.calls==(2 if failure else 12)


def test_new_physics_read_uses_new_static_descriptor_and_new_cache():
    world,ground,bump,old = contact_case()
    try:
        velocity = np.zeros(16);velocity[1] = 5.
        before = old.evaluate(velocity)
        bump.setTransform(TransformState.makePos(Vec3(-.84,.45,.025)))
        roads = RadialRoads(world,BulletRigidBodyNode('new-query'),old.config)
        current = FiniteRadialContact(roads,old.hardware,old.centers,old.rotation,old.hardware.axes,old.deformation,
                                     old.steering,old.trails,old.dt,old.config,old.on_asphalt)
        after = current.evaluate(velocity)
        assert current.query_cache is not old.query_cache
        assert not np.array_equal(before.geometry.deflection,after.geometry.deflection)
        assert old.evaluate(velocity) is before
    finally:
        world.removeRigidBody(bump);world.removeRigidBody(ground)


@pytest.mark.parametrize('kind',['hull','triangles'])
def test_actual_convex_mesh_success_and_epa_failures_repeat_with_cache(monkeypatch,kind):
    original = RadialRoads.query
    caches = weakref.WeakKeyDictionary()
    failures = []

    def query(self,centers,up,axes):
        cache = caches.setdefault(self,[{} for _ in self.surfaces])
        try:
            result = original(self,centers,up,axes,surface_cache=cache)
        except ArithmeticError as error:
            failures.append(str(error))
            with pytest.raises(ArithmeticError) as again:
                original(self,centers,up,axes,surface_cache=cache)
            assert str(again.value)==str(error)
            raise
        assert_geometry(original(self,centers,up,axes,surface_cache=cache),result)
        return result

    monkeypatch.setattr(RadialRoads,'query',query)
    world_case(kind)
    if kind=='triangles':assert failures


def test_actual_checkpoint_omits_only_derived_cache_and_replays_identical_numeric_fields(tmp_path,monkeypatch):
    root = Path(__file__).resolve().parents[1]
    document = json.loads((root/'docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json').read_text(encoding='utf-8'))
    config = config_from_document(document,vehicle_design('reference-rwd').config)
    run = LabExperiment(LabOptions(maneuver='ride_bump',duration=1/120,bump_distance_m=2.),
                        config=config,parameter_metadata=document['metadata'])
    original = UnsprungAdvanceInput.solve
    captured = []

    def solve(source,**kwargs):
        result = original(source,**kwargs)
        if not captured:
            counts = [len(cache) for cache in source.finite_contact.query_cache]
            assert sum(counts)>0
            path = tmp_path/'step.pkl'
            save_step(source,path)
            assert counts==[len(cache) for cache in source.finite_contact.query_cache]
            saved = pickle.loads(path.read_bytes())
            assert all(not cache for cache in saved.finite_contact.query_cache)
            captured.append((path,DIAGNOSTIC.digest(result)))
        return result

    monkeypatch.setattr(UnsprungAdvanceInput,'solve',solve)
    try:run.step()
    finally:run.close()
    path,expected = captured[0]
    assert DIAGNOSTIC.digest(load_step(path).solve())==expected
