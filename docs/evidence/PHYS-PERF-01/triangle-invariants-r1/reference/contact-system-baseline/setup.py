from setuptools import Extension, setup

setup(
    name="contact-system-baseline",
    ext_modules=[Extension(
        "_contact_system_old",
        ["baseline.c"],
        extra_compile_args=["/fp:strict", "/utf-8"],
    )],
)
