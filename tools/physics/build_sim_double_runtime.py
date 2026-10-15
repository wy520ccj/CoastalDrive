"""串行重建隔离双精度运行时；可先下载准备，依赖和日志均限定本工作树。"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT/"build/sim-double-runtime"


def build(prepare, output):
    output.mkdir(parents=True,exist_ok=False)
    commands = []
    def run(name,args,cwd=ROOT):
        commands.append({"name":name,"args":args,"cwd":str(cwd)})
        (output/"commands.json").write_text(json.dumps(commands,indent=2),encoding="utf-8")
        print(name,flush=True)
        with (output/(name+".log")).open("wb") as stream:
            subprocess.run(args,cwd=cwd,stdout=stream,stderr=subprocess.STDOUT,check=True)
    if prepare:run("prepare",[sys.executable,str(ROOT/"tools/physics/prepare_sim_double_runtime.py")])
    if not (BUILD/"panda-source/makepanda/makepanda.py").is_file():raise FileNotFoundError("先使用--prepare准备官方依赖")
    cmake = shutil.which("cmake")
    if cmake is None:raise FileNotFoundError("未找到CMake")
    flags = ["USE_DOUBLE_PRECISION=ON","USE_MSVC_RUNTIME_LIBRARY_DLL=ON","USE_MSVC_FAST_FLOATINGPOINT=OFF",
        "USE_MSVC_SSE=OFF","BUILD_BULLET3=OFF","BUILD_BULLET2_DEMOS=OFF","BUILD_CPU_DEMOS=OFF",
        "BUILD_OPENGL3_DEMOS=OFF","BUILD_EXTRAS=OFF","BUILD_UNIT_TESTS=OFF","BUILD_PYBULLET=OFF","INSTALL_LIBS=ON",
        "CMAKE_POLICY_VERSION_MINIMUM=3.5","CMAKE_CXX_FLAGS=/fp:strict",f"CMAKE_INSTALL_PREFIX={(BUILD/'bullet-install').as_posix()}"]
    run("bullet-configure",[cmake,"-S",str(BUILD/"bullet-source"),"-B",str(BUILD/"bullet-build"),
        "-G","Visual Studio 17 2022","-A","x64",*("-D"+flag for flag in flags)])
    run("bullet-build",[cmake,"--build",str(BUILD/"bullet-build"),"--config","Release","--target","INSTALL","--parallel","4"])
    run("bridge",[sys.executable,str(ROOT/"tools/physics/configure_sim_double_panda.py")])
    features = ("python","direct","gl","bullet","zlib","png","jpeg","freetype","harfbuzz","egg","squish","openal","vorbis","opus")
    run("panda-build",[sys.executable,"makepanda/makepanda.py","--nothing",*("--use-"+name for name in features),
        "--no-copy-python","--no-eigen","--msvc-version=14.3","--windows-sdk=10","--override","STDFLOAT_DOUBLE=1",
        "--threads=4","--optimize=4","--outputdir=built-double"],BUILD/"panda-source")
    run("render-adapter",[sys.executable,str(ROOT/"tools/physics/configure_sim_double_rendering.py")])
    run("runtime-check",[sys.executable,str(ROOT/"tools/physics/run_sim_double.py"),"--check"])


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare",action="store_true")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    build(args.prepare,args.output.resolve())
