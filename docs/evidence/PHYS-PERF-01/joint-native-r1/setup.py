from setuptools import Extension, setup
setup(name="joint-native-old",ext_modules=[Extension("_joint_native_old",["baseline.c"],extra_compile_args=["/fp:strict","/utf-8"])])
