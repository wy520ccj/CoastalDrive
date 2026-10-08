from setuptools import Extension,setup
setup(name="stable-map-probe",ext_modules=[Extension("_accurate_map",["stable.c"],extra_compile_args=["/fp:strict","/utf-8"])])
