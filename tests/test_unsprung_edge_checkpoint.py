"""真实失败子步的数值回归，保留既有共同求解门槛。"""

import pickle
from pathlib import Path


def test_certified_edge_normal_resolves_recorded_joint_line_search_failure():
    # 仅载入仓库中由本项目生成的可信数值夹具，不接收外部用户pickle。
    path = Path(__file__).resolve().parents[1]/"docs/evidence/SIM-UNSPRUNG-01/local-origin/failed-step.pkl"
    source = pickle.loads(path.read_bytes())
    source.finite_contact.on_asphalt = lambda x,y:True
    step = source.solve()
    assert step.momentum_error<1e-9
    assert step.force_error<1e-5
    assert step.port_error<1e-9
    assert abs(step.energy_error)<1e-8
