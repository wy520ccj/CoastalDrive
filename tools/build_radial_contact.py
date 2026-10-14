"""只构建独立树的双精度接触查询模块，不安装依赖或重建游戏原生模块。"""

import os
from pathlib import Path

from setuptools import Extension, setup

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
setup(name="coastal-radial-contact",package_dir={"":"src"},ext_modules=[
    Extension("radial_contact_kernels",["src/radial_contact_kernels.cpp","src/radial_contact_vendor.cpp"],
              include_dirs=["vendor/bullet-2.84","vendor/bullet-2.84/BulletCollision/NarrowPhaseCollision"],
              depends=["src/radial_gjk_epa.cpp"],define_macros=[("BT_USE_DOUBLE_PRECISION","1")],language="c++",
              extra_compile_args=["/fp:strict","/utf-8"] if os.name=="nt" else ["-fno-fast-math","-ffp-contract=off"])
],options={"build_ext":{"build_temp":"build/radial-contact-double"}})
