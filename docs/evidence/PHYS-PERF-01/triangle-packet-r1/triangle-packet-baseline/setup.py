from setuptools import Extension, setup
setup(name="triangle-packet-baseline",ext_modules=[Extension("_triangle_packet_old",["baseline.c"],extra_compile_args=["/fp:strict","/utf-8"])])
