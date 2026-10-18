from pathlib import Path
from setuptools import Extension,setup
root=Path.cwd()
setup(name="coastal-shared-rounding",ext_modules=[Extension("mechanical_kernels",[str(root/"src/mechanical_kernels.c")],include_dirs=[str(root/"src")],extra_compile_args=["/fp:strict","/utf-8"])])
