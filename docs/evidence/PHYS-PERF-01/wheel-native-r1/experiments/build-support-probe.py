from pathlib import Path
from setuptools import Extension, setup

folder = Path(__file__).resolve().parent
setup(name='coastal-support-probe', version='0', packages=[], py_modules=[],
      ext_modules=[Extension('_support_probe', [str(folder / 'support-kernel.c')],
                             extra_compile_args=['/fp:strict', '/utf-8'])])
