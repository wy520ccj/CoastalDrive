"""只修改隔离构建树：换入双精度Bullet库/头，并为Panda桥接设置相同标量。"""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT/"build/sim-double-runtime"


def configure():
    sdk = BUILD/"panda-source/thirdparty/win-libs-vc14-x64/bullet"
    install = BUILD/"bullet-install"
    replacements = {}
    for name in ("BulletCollision.lib","BulletDynamics.lib","BulletSoftBody.lib","LinearMath.lib"):
        source,target = install/"lib"/name,sdk/"lib"/name
        assert source.is_file() and target.is_file()
        replacements[str(target.relative_to(BUILD))] = {"original":hashlib.sha256(target.read_bytes()).hexdigest(),
            "double":hashlib.sha256(source.read_bytes()).hexdigest()}
        shutil.copyfile(source,target)
    for source in (install/"include/bullet").rglob("*"):
        if not source.is_file():continue
        target = sdk/"include"/source.relative_to(install/"include/bullet")
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    script = BUILD/"panda-source/makepanda/makepanda.py"
    original = script.read_bytes()
    backup = BUILD/"makepanda-original.py"
    if not backup.exists():backup.write_bytes(original)
    anchor = b'DefSymbol("WITHINPANDA", "WITHIN_PANDA", "1")'
    addition = b'DefSymbol("ALWAYS", "BT_USE_DOUBLE_PRECISION", "1")'
    if addition not in original:
        assert original.count(anchor)==1
        script.write_bytes(original.replace(anchor,anchor+b'\n'+addition))
    record = {"libs":replacements,"makepanda_original":hashlib.sha256(backup.read_bytes()).hexdigest(),
        "makepanda_double":hashlib.sha256(script.read_bytes()).hexdigest(),"panda_override":"STDFLOAT_DOUBLE=1",
        "bullet_bridge_define":"BT_USE_DOUBLE_PRECISION=1","runtime_installed":False}
    (BUILD/"double-configuration.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
    print("Isolated double libraries and bridge configured; shared environment unchanged")


if __name__=="__main__":configure()
