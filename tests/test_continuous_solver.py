"""连续内核实际执行、工作区重置及有限几何的小型SVD独立核对。"""

import math
import pickle
from dataclasses import replace
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path

import numpy as np
import pytest
from wheel_contact_kernels import _joint_coordinates, convex_distance

import physics_workers
import tire_drivetrain
from physics_wire import from_bytes, result_bytes

FIXTURE = Path(__file__).resolve().parents[1]/'docs/evidence/PHYS-PERF-01/structural-20261009/native-input-fixture'


def test_real_complete_inputs_use_native_iteration_and_reset_workspace(monkeypatch):
    hardware = pickle.loads((FIXTURE/'hardware.pickle').read_bytes())
    payload = (FIXTURE/'geometry.pickle').read_bytes()
    memory = SharedMemory(create=True, size=len(payload))
    memory.buf[:] = payload
    reference = physics_workers.GeometryRef(memory.name, len(payload), 1)
    original = tire_drivetrain.joint_solve
    native_calls = []

    def native(*args):
        native_calls.append(args[0])
        return original(*args)

    def python_iteration(*args, **kwargs):
        raise AssertionError('真实输入不允许回到旧Python共同迭代或有限接触回调')

    monkeypatch.setattr(tire_drivetrain, 'joint_solve', native)
    for name in ('shared_load_solution', 'loaded_wheel_force_solution', 'finite_contact_system',
                 'wheel_residuals', 'suspension_residuals'):
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
