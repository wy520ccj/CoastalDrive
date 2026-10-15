"""核对实际双精度导向旧门槛、渲染颜色边界与真实跨运行时记录拒绝。"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from panda3d.bullet import BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, Texture, TransformState, Vec3
from simplepbr._ibl_funcs_cpu import get_sh_coeffs_from_cube_map
from simplepbr.envmap import EnvMap

from lab_records import changed_conditions, load_record, recalculate
from lab_runtime import runtime_fingerprint
from unsprung_body import NativeWheelGuides, SprungBodyFrame
from unsprung_dynamics import partition_vehicle
from vehicle_designs import REFERENCE_DESIGN


def check(output):
    output.mkdir(parents=True,exist_ok=False)
    (output/"executed-tool.py").write_bytes(Path(__file__).read_bytes())
    runtime = runtime_fingerprint()
    assert runtime["math_scalar_bits"]==64
    masses = (38.,41.,40.,39.)
    centers = ((-.84,1.1,-.1),(.84,1.1,-.1),(-.84,-1.1,-.1),(.84,-1.1,-.1))
    frame = SprungBodyFrame.from_partition(partition_vehicle(1200.,np.diag((1919.56,511.56,2290.)),masses,centers))
    world,body = BulletWorld(),BulletRigidBodyNode("unequal-freefall")
    world.setGravity(Vec3(0,0,-9.81));body.setDeactivationEnabled(False);body.setIntoCollideMask(BitMask32.bit(1))
    frame.install(body,REFERENCE_DESIGN,TransformState.makePos(Vec3(0,0,10)))
    world.attachRigidBody(body);guides=NativeWheelGuides(world,body,frame)
    try:
        for _ in range(24):world.doPhysics(1/240,0,1/240)
        _centers,speeds,_travel,_relative,transverse = guides.read()
        error = float(np.max(np.abs(speeds-np.array((0.,0.,-.981)))))
        assert error<5e-7
        fall = {"masses":masses,"initial_height":10.,"duration":.1,"threshold":5e-7,
                "maximum_velocity_error":error,"wheel_velocities":speeds.tolist(),"transverse":transverse.tolist()}
    finally:
        guides.close();world.removeRigidBody(body)
    texture = Texture("color-boundary")
    texture.setupCubeMap(2,Texture.T_unsigned_byte,Texture.F_rgb8)
    texture.setRamImage(bytes((255,255,255))*24)
    coefficients = get_sh_coeffs_from_cube_map(texture)
    environment = EnvMap(texture,skip_prepare=True)
    environment._store_sh_coefficients(coefficients)
    array = environment.sh_coefficients
    assert len(array)==9 and np.isfinite(np.asarray([tuple(v) for v in array])).all()
    single = load_record(ROOT/"logs/SIM-UNSPRUNG-01/sim-normal-record-r1/mass-40")
    double = load_record(ROOT/"logs/SIM-UNSPRUNG-01/sim-double-record-r1/mass-40")
    assert single.metadata["runtime_start"]["math_scalar_bits"]==32
    assert double.metadata["runtime_start"]["math_scalar_bits"]==64
    assert changed_conditions(single,double).keys()=={"runtime_version"}
    try:recalculate(single)
    except ValueError as error:
        assert "运行时" in str(error)
        rejection = str(error)
    else:raise AssertionError("真实跨精度记录未被拒绝")
    result = {"runtime":runtime,"freefall":fall,"gpu_color_array":True,"cross_runtime_rejection":rejection,
              "changed_conditions":["runtime_version"]}
    (output/"result.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    (output/"executed-tool.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps({"old_freefall_threshold_passed":True,"maximum_velocity_error":fall["maximum_velocity_error"],
                      "color_codec_passed":True,"real_cross_runtime_rejected":True}))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    check(parser.parse_args().output.resolve())
