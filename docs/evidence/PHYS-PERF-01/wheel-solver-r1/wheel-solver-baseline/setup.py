from setuptools import Extension, setup
setup(name="wheel-solver-baseline",ext_modules=[Extension("_wheel_solver_old",["baseline.c"],extra_compile_args=["/fp:strict","/utf-8"])])
