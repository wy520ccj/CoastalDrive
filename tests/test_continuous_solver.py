"""连续内核实际执行、工作区重置及有限几何的小型SVD独立核对。"""

import math
import pickle
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from threading import Barrier, get_ident

import numpy as np
import pytest
from wheel_contact_kernels import _joint_contact_state, _joint_coordinates, convex_distance

import physics_workers
import tire_drivetrain
from physics_wire import from_bytes, result_bytes
from suspension import SuspensionState
from suspension_kinematics import finite_contact_system
from vehicle_suspension import Suspension
from vehicle_tire_step import TireBodyInput, TireWheelInput, tire_hardware

FIXTURE = Path(__file__).resolve().parents[1]/'docs/evidence/PHYS-PERF-01/structural-20261009/native-input-fixture'


def test_complete_world_candidates_cover_crossings_and_preserve_finite_geometry():
    hardware = pickle.loads((FIXTURE/'hardware.pickle').read_bytes())
    payload = (FIXTURE/'geometry.pickle').read_bytes()
    memory = SharedMemory(create=True, size=len(payload))
    memory.buf[:] = payload
    reference = physics_workers.GeometryRef(memory.name, len(payload), 1701)
    try:
        physics_workers._load_geometry(reference)
        request = from_bytes((FIXTURE/'input-6240.bin').read_bytes())
        body = TireBodyInput(request.body.pose, request.body.velocity, request.body.angular,
                             request.body.inverse_inertia, request.body.angular_damping)
        adapter = Suspension.__new__(Suspension)
        adapter.config = hardware
        adapter.hubs, _rear = tire_hardware(hardware)
        adapter.envelope = None
        adapter.compression = request.compression
        adapter.state = SuspensionState(force_tick=request.previous_force_tick,
                                         normal_force=request.previous_normal_force)
        adapter._support_shapes = None
        adapter._candidate_cache = {}
        system = adapter.prepare(physics_workers.StaticQueryBoundary(), body,
            tuple(TireWheelInput(*wheel) for wheel in request.wheel_inputs), physics_workers._worker_geometry)
        geometry = tire_drivetrain.native_contact_geometry(system)
        assert geometry is not None
        vx, vy, vz = request.body.velocity
        queries = (((vx, vy, vz), request.body.angular),
                   ((vx+100, vy+100, vz), (.2, -.3, .1)),
                   ((vx-180, vy-80, vz-4), (-.1, .4, -.2)),
                   ((vx+100.01, vy+100.01, vz), (.2001, -.3001, .1001)),
                   ((vx, vy, vz), request.body.angular))
        filtered = []
        for velocity, angular in queries:
            gradients, alignment, touching, counts = _joint_contact_state(geometry, velocity, angular, request.dt)
            expected = finite_contact_system(system, velocity, angular, request.dt)
            np.testing.assert_allclose(gradients, expected.gradients, rtol=2e-13, atol=2e-13)
            assert touching == expected.touching
            for actual, target in zip(alignment, expected.alignment):
                assert actual == pytest.approx(target, rel=2e-13, abs=2e-13) if target is not None else actual is None
            filtered.extend((kept, full) for kept, full in counts if kept >= 0)
        assert filtered and all(0 <= kept <= full for kept, full in filtered)
        assert any(kept < full for kept, full in filtered)
    finally:
        physics_workers._worker_geometry = None
        physics_workers._worker_candidates.clear()
        physics_workers._worker_meshes.clear()
        physics_workers._worker_version = None
        if physics_workers._worker_memory is not None:
            physics_workers._worker_memory.close()
            physics_workers._worker_memory = None
        memory.close()
        memory.unlink()


def test_real_complete_inputs_use_native_iteration_and_reset_workspace(monkeypatch):
    hardware = pickle.loads((FIXTURE/'hardware.pickle').read_bytes())
    payload = (FIXTURE/'geometry.pickle').read_bytes()
    memory = SharedMemory(create=True, size=len(payload))
    memory.buf[:] = payload
    reference = physics_workers.GeometryRef(memory.name, len(payload), 1)
    original = tire_drivetrain.joint_solve
    original_prepare = tire_drivetrain.joint_mechanical_prepare
    native_calls = []
    prepare_calls = []

    def native(*args):
        native_calls.append(args[0])
        return original(*args)

    def python_iteration(*args, **kwargs):
        raise AssertionError('真实输入不允许回到旧Python共同迭代或有限接触回调')

    def prepare(*args):
        prepare_calls.append(args[0])
        return original_prepare(*args)

    monkeypatch.setattr(tire_drivetrain, 'joint_solve', native)
    monkeypatch.setattr(tire_drivetrain, 'joint_mechanical_prepare', prepare)
    for name in ('shared_load_solution', 'loaded_wheel_force_solution', 'finite_contact_system',
                 'wheel_residuals', 'suspension_residuals', 'differential_branches', 'shaft_brake_plans',
                 'shared_map_coefficients', 'wheel_map_coefficients', 'load_coefficients', 'suspension_projection'):
        monkeypatch.setattr(tire_drivetrain, name, python_iteration)
    identifiers = sorted(int(path.stem.split('-')[1]) for path in FIXTURE.glob('input-*.bin'))
    try:
        # 同一工作区交错处理真实两子步/各车输入；改变次序不能带入上一车暖模式。
        for index, identifier in enumerate((*identifiers, *reversed(identifiers))):
            if index == len(identifiers):
                previous_geometry = physics_workers._worker_geometry
                reference = replace(reference, version=2)
            request = replace(from_bytes((FIXTURE/f'input-{identifier}.bin').read_bytes()), config=hardware)
            result = physics_workers._solve_vehicle(request, reference)
            assert result is not None
            assert result_bytes(result) == (FIXTURE/f'result-{identifier}.bin').read_bytes()
            if index == len(identifiers):
                assert physics_workers._worker_geometry is not previous_geometry
                assert physics_workers._worker_geometry.joint_surfaces is not previous_geometry.joint_surfaces
        assert len(native_calls) == 2*len(identifiers) == 52
        assert all(workspace is native_calls[0] for workspace in native_calls)
        assert len(prepare_calls) == 52
        assert all(workspace is prepare_calls[0] for workspace in prepare_calls)
    finally:
        physics_workers._worker_geometry = None
        physics_workers._worker_candidates.clear()
        physics_workers._worker_meshes.clear()
        physics_workers._worker_version = None
        if physics_workers._worker_memory is not None:
            physics_workers._worker_memory.close()
            physics_workers._worker_memory = None
        memory.close()
        memory.unlink()


def test_mutable_numeric_workspaces_are_owned_by_each_thread():
    hardware = pickle.loads((FIXTURE/'hardware.pickle').read_bytes())
    barrier = Barrier(2)

    def workspace():
        owner = get_ident()
        joint = tire_drivetrain.native_joint_workspace(hardware, owner)
        mechanical = tire_drivetrain.native_mechanical_workspace(hardware, owner)
        barrier.wait(timeout=5)
        return owner, joint, mechanical

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = (result.result() for result in (pool.submit(workspace), pool.submit(workspace)))
    assert first[0] != second[0]
    assert first[1] is not second[1]
    assert first[2] is not second[2]


def test_native_parallel_complete_results_and_error_recovery(monkeypatch):
    hardware = pickle.loads((FIXTURE/'hardware.pickle').read_bytes())
    payload = (FIXTURE/'geometry.pickle').read_bytes()
    memory = SharedMemory(create=True, size=len(payload))
    memory.buf[:] = payload
    reference = physics_workers.GeometryRef(memory.name, len(payload), 1)
    identifier = min(int(path.stem.split('-')[1]) for path in FIXTURE.glob('input-*.bin'))
    request = replace(from_bytes((FIXTURE/f'input-{identifier}.bin').read_bytes()), config=hardware)
    expected = (FIXTURE/f'result-{identifier}.bin').read_bytes()
    native = tire_drivetrain.joint_solve
    captured = []

    def capture(*args):
        captured.append(args)
        return native(*args)

    try:
        monkeypatch.setattr(tire_drivetrain, 'joint_solve', capture)
        assert result_bytes(physics_workers._solve_vehicle(request, reference)) == expected
        monkeypatch.setattr(tire_drivetrain, 'joint_solve', native)
        args = captured[-1]
        original = native(*args)
        # 纯数值区的错误须在恢复线程状态后传回，下一次合法求解仍可复用工作区。
        for invalid in (math.nan, math.inf):
            data = list(args[-1])
            state = list(data[0])
            state[3] = invalid
            data[0] = tuple(state)
            with pytest.raises(OverflowError, match='有限机械矩阵求和溢出'):
                native(*args[:-1], tuple(data))
            assert native(*args) == original
        barrier = Barrier(3)
        geometry = physics_workers._worker_geometry

        def solve():
            owner = get_ident()
            candidates = {}
            barrier.wait(timeout=5)
            for _ in range(8):
                result = request.solve(static_geometry=geometry,
                    surface_material=physics_workers.material_query, surface_candidates=candidates)
                assert result_bytes(result) == expected
            return owner

        with ThreadPoolExecutor(max_workers=3) as executor:
            owners = [future.result() for future in [executor.submit(solve) for _ in range(3)]]
        assert len(set(owners)) == 3
    finally:
        physics_workers._worker_geometry = None
        physics_workers._worker_candidates.clear()
        physics_workers._worker_meshes.clear()
        physics_workers._worker_version = None
        if physics_workers._worker_memory is not None:
            physics_workers._worker_memory.close()
            physics_workers._worker_memory = None
        memory.close()
        memory.unlink()


@pytest.mark.parametrize('columns', (1, 2, 3))
@pytest.mark.parametrize('condition', (1., 1e4, 1e8))
def test_native_simplex_svd_rank_and_independent_backward_error(columns, condition):
    rng = np.random.default_rng(23)
    for _ in range(12):
        left, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        right, _ = np.linalg.qr(rng.normal(size=(columns, columns)))
        singular = np.geomspace(1., 1/condition, columns)
        matrix = left[:, :columns] @ np.diag(singular) @ right.T
        rhs = rng.normal(size=3)
        actual, rank = _joint_coordinates(tuple(map(tuple, matrix.T)), tuple(rhs))
        expected, _, expected_rank, _ = np.linalg.lstsq(matrix, rhs, rcond=None)
        actual = np.asarray(actual)
        assert rank == expected_rank
        assert np.isfinite(actual).all()
        # 允许SVD末位差异；按矩阵/解规模独立检查后向误差，而非改物理残差门槛。
        scale = np.linalg.norm(matrix)*max(np.linalg.norm(actual), np.linalg.norm(expected)) + np.linalg.norm(rhs)
        bound = 32*np.finfo(float).eps*scale
        assert np.linalg.norm(matrix @ (actual-expected)) <= bound
        assert np.linalg.norm(matrix.T @ (matrix @ actual-rhs)) <= bound*np.linalg.norm(matrix)


def test_native_simplex_rank_deficiency_preserves_minimum_norm():
    columns = ((1., 2., 3.), (2., 4., 6.), (0., 0., 0.))
    rhs = (3., -1., 2.)
    actual, rank = _joint_coordinates(columns, rhs)
    expected, _, expected_rank, _ = np.linalg.lstsq(np.asarray(columns).T, rhs, rcond=None)
    assert rank == expected_rank == 1
    assert actual == pytest.approx(expected, abs=2e-15)
    assert math.isclose(actual[1], 2*actual[0], rel_tol=0., abs_tol=2e-15)


@pytest.mark.parametrize('center', ((1.3, .4, .8), (1.2, 1.5, 1.4), (.7, .2, 1.1), (-1.4, -1.2, 1.7)))
def test_native_finite_box_edges_match_independent_cylinder_product(center):
    half, radius, half_width, shoulder = (1., 1., .05), .33, .1025, .01
    axial = max(abs(center[0])-half[0]-half_width+shoulder, 0.)
    dy, dz = max(abs(center[1])-half[1], 0.), max(abs(center[2])-half[2], 0.)
    radial = max(math.hypot(dy, dz)-radius+shoulder, 0.)
    expected = math.hypot(axial, radial)
    # None明确选择连续内核的小型原生SVD，不能回调NumPy。
    distance, normal, point = convex_distance(center, (1., 0., 0.), half,
        radius, half_width, shoulder, 0., None, 1)
    assert distance == pytest.approx(expected, abs=2e-10)
    assert sum(value*value for value in normal) == pytest.approx(1., abs=2e-12)
    assert all(abs(value) <= extent+1e-12 for value, extent in zip(point, half))


def test_native_rotated_crown_cap_preserves_actual_axial_extent():
    axis = (.9398454188243761, -.34157626571707533, .004030311850328373)
    center = (99.08800894185853, 14.050510012143128, .047717814869382646)
    corner = (99.3, 14.120750419027639, -.046897439629641796)
    unit = tuple(value/math.sqrt(math.fsum(x*x for x in axis)) for value in axis)
    relative = tuple(point-origin for point, origin in zip(corner, center))
    axial = math.fsum(value*direction for value, direction in zip(relative, unit))
    radial = math.sqrt(math.fsum((relative[i]-axial*unit[i])**2 for i in range(3)))
    assert radial < .32-.003
    distance, normal, point = convex_distance(tuple(-value for value in relative), axis,
        (0., 0., 0.), .33, .1025, .01, .003, None, 1)
    assert distance == pytest.approx(axial-.0925, rel=0., abs=2e-15)
    assert normal == pytest.approx(tuple(-value for value in unit), rel=0., abs=2e-15)
    assert point == (0., 0., 0.)
