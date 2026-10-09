import os

from setuptools import Extension, setup

compile_args = (["/fp:strict", "/utf-8"] if os.name == "nt"
                else ["-fno-fast-math", "-ffp-contract=off"])
convex_sources = [
    "BulletCollision/CollisionShapes/btSphereShape.cpp",
    "BulletCollision/CollisionShapes/btCollisionShape.cpp",
    "BulletCollision/CollisionShapes/btConvexShape.cpp",
    "BulletCollision/CollisionShapes/btConvexInternalShape.cpp",
    "BulletCollision/NarrowPhaseCollision/btContinuousConvexCollision.cpp",
    "BulletCollision/NarrowPhaseCollision/btConvexCast.cpp",
    "BulletCollision/NarrowPhaseCollision/btGjkPairDetector.cpp",
    "BulletCollision/NarrowPhaseCollision/btGjkEpa2.cpp",
    "BulletCollision/NarrowPhaseCollision/btGjkEpaPenetrationDepthSolver.cpp",
    "BulletCollision/NarrowPhaseCollision/btVoronoiSimplexSolver.cpp",
    "LinearMath/btAlignedAllocator.cpp",
    "LinearMath/btVector3.cpp",
]

setup(
    name="coastaldrive",
    version="0.8.3",
    package_dir={"": "src"},
    ext_modules=[
        Extension("mechanical_kernels", ["src/mechanical_kernels.c"], extra_compile_args=compile_args),
        Extension("wheel_contact_kernels", ["src/wheel_contact_kernels.c"],
                  depends=["src/wheel_convex_distance.h"], extra_compile_args=compile_args),
        Extension("convex_cast_kernels", ["src/convex_cast_kernels.cpp", *["vendor/bullet-2.84/"+name for name in convex_sources]],
                  include_dirs=["vendor/bullet-2.84"], extra_compile_args=compile_args, language="c++"),
    ],
    options={
        "build_apps": {
            "gui_apps": {"coastaldrive": "src/main.py"},
            "platforms": ["win_amd64"],
            "log_filename": "$USER_APPDATA/CoastalDrive/coastaldrive.log",
            "log_append": False,
            "include_patterns": [
                "assets/game/**/*.glb",
                "assets/game/**/*.bam",
                "assets/game/**/*.env",
                "assets/game/**/*.png",
                "assets/game/**/*.ico",
                "assets/game/**/*.ttf",
                "assets/game/**/*.otf",
                "assets/game/ui/fonts/*OFL.txt",
                "assets/game/ui/fonts/OFL-*.txt",
                "assets/game/**/*.jpg",
                "assets/game/**/*.wav",
                "assets/game/**/*.json",
                "assets/game/environment/shaders/*.vert",
                "assets/game/environment/shaders/*.frag",
                "assets/game/expressway/shaders/*.frag",
                "assets/game/expressway/shaders/*.vert",
                "assets/game/expressway/shaders/*.glsl",
                "assets/game/**/License.txt",
                "licenses/CPython-LICENSE.txt",
                "licenses/Bullet-LICENSE.txt",
            ],
            "plugins": ["pandagl", "p3openal_audio"],
            "include_modules": {"*": [
                "mechanical_kernels",
                "wheel_contact_kernels",
                "convex_cast_kernels",
                "multiprocessing.spawn",
                "multiprocessing.popen_spawn_win32",
                "multiprocessing.shared_memory",
                "multiprocessing.reduction",
                "multiprocessing.resource_tracker",
                "_multiprocessing",
                "_winapi",
                "numpy._core._exceptions",
                "direct.gui.DirectGui",
                "direct.gui.DirectGuiBase",
                "direct.showbase.ShowBase",
            ]},
        }
    },
)
