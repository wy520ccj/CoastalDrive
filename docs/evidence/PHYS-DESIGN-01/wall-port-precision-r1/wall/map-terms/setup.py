from setuptools import Extension,setup
setup(name="map-terms",ext_modules=[Extension("_map_terms",["terms.c"],extra_compile_args=["/fp:strict","/utf-8"])])
