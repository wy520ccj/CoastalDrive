from setuptools import Extension, setup
setup(name="shared-load-old",ext_modules=[Extension("_shared_load_old",["baseline.c"],extra_compile_args=["/fp:strict","/utf-8"])])
