"""原生单刚体恒力解析对照；区分连续力批量提交与提前冲量的舍入，不改生产状态。"""

import argparse
import json
from pathlib import Path

from panda3d.bullet import BulletRigidBodyNode, BulletWorld
from panda3d.core import Vec3


def check(output):
    output.mkdir(parents=True,exist_ok=False)
    rows = []
    for total in (-.02,-20.,-300.):
        for substeps in (2,4,8):
            for mode in ("impulse_then_force","all_force"):
                world,body = BulletWorld(),BulletRigidBodyNode("constant-force")
                world.setGravity(Vec3(0))
                body.setMass(1040.)
                body.setLinearVelocity(Vec3(0,5.,0))
                body.setDeactivationEnabled(False)
                world.attachRigidBody(body)
                h,steps = 1/120/substeps,120*substeps
                try:
                    for _ in range(steps):
                        if mode=="impulse_then_force":
                            body.applyCentralImpulse(Vec3(0,.625*total*h,0))
                            body.applyCentralForce(Vec3(0,.375*total,0))
                        else:
                            body.applyCentralForce(Vec3(0,total,0))
                        world.doPhysics(h,0,h)
                    actual,expected = body.getLinearVelocity().y,5.+total/1040.
                    rows.append({"force_N":total,"substeps":substeps,"mode":mode,
                        "velocity_mps":actual,"analytic_mps":expected,"velocity_error":actual-expected,
                        "kinetic_defect_J":.5*1040*(actual-expected)*(actual+expected)})
                finally:
                    world.removeRigidBody(body)
    (output/"result.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
    (output/"executed-tool.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps(rows,indent=2))


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    check(parser.parse_args().output.resolve())
