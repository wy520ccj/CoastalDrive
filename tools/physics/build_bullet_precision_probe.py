"""从官方标签构建独立精度诊断模块；输出仅在build，不安装共享环境。"""

import hashlib
import io
import json
import os
import urllib.request
import zipfile
from pathlib import Path

from setuptools import Extension, setup

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT/"build/bullet-precision-proof"
SOURCE = BUILD/"source"
URL = "https://codeload.github.com/bulletphysics/bullet3/zip/refs/tags/2.84"


def sources():
    SOURCE.mkdir(parents=True,exist_ok=True)
    manifest = BUILD/"upstream.json"
    if not manifest.exists():
        data = urllib.request.urlopen(URL,timeout=60).read()
        digests = {}
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            for name in package.namelist():
                relative = Path(*Path(name).parts[1:])
                if name.endswith("/") or not (relative.as_posix()=="LICENSE.txt" or
                    len(relative.parts)>1 and relative.parts[0]=="src" and relative.parts[1] in
                    ("LinearMath","BulletCollision","BulletDynamics","Bullet3Common") or relative.as_posix()=="src/btBulletDynamicsCommon.h"
                    or relative.as_posix()=="src/btBulletCollisionCommon.h"):
                    continue
                target = (SOURCE/relative).resolve()
                if not target.is_relative_to(SOURCE.resolve()):raise ValueError("上游归档路径越界")
                target.parent.mkdir(parents=True,exist_ok=True)
                blob = package.read(name);target.write_bytes(blob)
                digests[str(relative)] = hashlib.sha256(blob).hexdigest()
        manifest.write_text(json.dumps({"url":URL,"archive_sha256":hashlib.sha256(data).hexdigest(),"files":digests},indent=2),encoding="utf-8")
    saved = json.loads(manifest.read_text(encoding="utf-8"))
    for relative,digest in saved["files"].items():
        if hashlib.sha256((SOURCE/relative).read_bytes()).hexdigest()!=digest:raise ValueError(f"上游源内容改变：{relative}")
    return [str(p.relative_to(BUILD)) for folder in ("LinearMath","BulletCollision","BulletDynamics")
            for p in (SOURCE/"src"/folder).rglob("*.cpp")]+["source/src/Bullet3Common/b3Logging.cpp"]


if __name__=="__main__":
    source_files = ["probe.cpp",*sources()]
    (BUILD/"probe.cpp").write_bytes((ROOT/"tools/physics/bullet_precision_probe.cpp").read_bytes())
    os.chdir(BUILD)
    extensions = [Extension("bullet_precision_"+kind,source_files,include_dirs=[str(SOURCE/"src")],
        define_macros=[("BT_USE_DOUBLE_PRECISION","1")] if kind=="double" else [],language="c++",
        extra_compile_args=["/O2","/fp:strict","/utf-8"] if os.name=="nt" else ["-O2","-fno-fast-math","-ffp-contract=off"])
        for kind in ("float","double")]
    setup(name="bullet-precision-proof",ext_modules=extensions,
          options={"build_ext":{"build_temp":"objects","build_lib":"modules"}})
