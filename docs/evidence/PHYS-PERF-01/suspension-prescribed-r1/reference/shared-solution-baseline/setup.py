from setuptools import Extension, setup

setup(
    name="shared-solution-baseline",
    ext_modules=[Extension(
        "_shared_solution_old",
        ["baseline.c"],
        extra_compile_args=["/fp:strict", "/utf-8"],
    )],
)
