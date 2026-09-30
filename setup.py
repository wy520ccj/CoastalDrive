from setuptools import setup


setup(
    name="coastaldrive",
    version="0.8.3",
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
            ],
            "plugins": ["pandagl", "p3openal_audio"],
            "include_modules": [
                "direct.gui.DirectGui",
                "direct.gui.DirectGuiBase",
                "direct.showbase.ShowBase",
            ],
        }
    },
)
