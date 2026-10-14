"""试验场坐标与游戏场地隔离，重开保留实验初值约定。"""

from simulation import Simulation
from test_track import SPAWN
from vehicle_designs import REFERENCE_DESIGN


def test_lab_uses_local_origin_while_test_track_keeps_its_spawn():
    lab = Simulation(track="lab",config=REFERENCE_DESIGN)
    test = Simulation(track="test",config=REFERENCE_DESIGN)
    try:
        assert lab.spawn[:2]==(0.,0.)
        assert tuple(lab.player.reference_pose().getPos())[:2]==(0.,0.)
        assert test.spawn[:2]==SPAWN[:2]
        lab.reset(17)
        assert lab.spawn[:2]==(0.,0.)
        assert tuple(lab.player.reference_pose().getPos())[:2]==(0.,0.)
    finally:
        lab.close();test.close()
