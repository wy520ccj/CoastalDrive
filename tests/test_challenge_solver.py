"""挑战及完整回归的真实失败子步，使用原精度验证两条求根路径。"""

import gzip
import hashlib
import json
import pickle
from pathlib import Path

import pytest

import physics_workers
import tire_drivetrain
from physics_workers import StaticSource
from suspension_contacts import StaticSupportShapes


@pytest.mark.parametrize(('case', 'native'), (
    ('challenge-handling-shared', True), ('challenge-handling-shared', False),
    ('core-rolling-root', True), ('core-rolling-root', False),
    ('challenge-ridge-face-tie', True),
))
def test_captured_mechanical_step_converges_with_existing_precision(case, native, monkeypatch):
    fixture = Path(__file__).parent/'data'/case
    payload = gzip.decompress((fixture/'input.pkl.gz').read_bytes())
    source = json.loads((fixture/'source.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(payload).hexdigest() == source['sha256']
    # 仅读取本项目捕获并随仓库保存的可信夹具，不读取外部用户pickle。
    inputs, groups, kwargs = pickle.loads(payload)
    geometry = StaticSupportShapes(tuple((StaticSource(index), supported, parts)
                                         for index, supported, parts in groups))
    monkeypatch.setattr(physics_workers, '_worker_geometry', geometry)
    for plane in inputs.parameters['suspension'].kinematics:
        if plane is not None:
            # 原捕获器没有候选盒；用同批完整几何查询，不伪造空向量。
            plane.surface.candidates.clear()
    if not native:
        monkeypatch.setattr(tire_drivetrain, 'native_contact_geometry', lambda system: None)
    observed = []
    for _ in range(3):
        result = inputs.solve(**kwargs)
        assert result.normal_residual < 1e-10
        assert max(wheel.residual for wheel in result.wheels) < 1e-4
        assert abs(result.suspension.energy_residual) < 1e-8
        observed.append((result.velocity, result.angular, result.engine_omega, result.shaft_omega,
                         tuple((wheel.fx, wheel.fy, wheel.omega, wheel.brake_torque) for wheel in result.wheels),
                         result.suspension))
    assert observed[0] == observed[1] == observed[2]
