"""在本工作树隔离双精度SDK内运行脚本；子进程继承相同环境，不安装任何包。"""

import argparse
import json
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT/"build/sim-double-runtime/panda-source/built-double"


def activate():
    if not (RUNTIME/"panda3d").is_dir():raise FileNotFoundError("双精度SDK尚未构建")
    bootstrap = ROOT/"build/sim-double-runtime/bootstrap"
    bootstrap.mkdir(exist_ok=True)
    (bootstrap/"sitecustomize.py").write_text('''"""隔离子进程也必须加载同一双精度SDK。"""
import os
import sys
from pathlib import Path
runtime = Path(__file__).resolve().parent.parent/"panda-source/built-double"
sys.path.insert(0,str(runtime))
dll_directory = os.add_dll_directory(str(runtime/"bin"))
from panda3d.core import LPoint3,LPoint3d
if LPoint3 is not LPoint3d:raise SystemExit("隔离SDK不是双精度")
''',encoding="utf-8")
    existing = os.environ.get("PYTHONPATH","")
    os.environ["PYTHONPATH"] = os.pathsep.join((str(bootstrap),str(RUNTIME),existing))
    os.environ["PATH"] = str(RUNTIME/"bin")+os.pathsep+os.environ["PATH"]
    sys.path.insert(0,str(RUNTIME))
    handle = os.add_dll_directory(str(RUNTIME/"bin"))
    from panda3d import bullet, core
    if core.LPoint3 is not core.LPoint3d:raise RuntimeError("加载的运行时不是64位数学类型")
    return handle,{"panda":core.PandaSystem.getVersionString(),"bullet":bullet.getBulletVersion(),
                   "math_scalar_bits":64,"module":core.__file__,"shared_environment_modified":False}


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true")
    parser.add_argument("script",nargs="?")
    parser.add_argument("arguments",nargs=argparse.REMAINDER)
    args = parser.parse_args()
    dll_handle,metadata = activate()
    if args.check:print(json.dumps(metadata))
    elif args.script:
        target = (ROOT/args.script).resolve()
        sys.argv = [str(target),*args.arguments]
        sys.path.insert(0,str(target.parent))
        runpy.run_path(str(target),run_name="__main__")
    else:parser.error("指定待运行脚本或--check")
