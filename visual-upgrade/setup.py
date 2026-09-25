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
                "assets/game/**/*.png",
                "assets/game/**/*.ico",
                "assets/game/**/*.ttf",
                "assets/game/**/*.jpg",
                "assets/game/**/*.wav",
                "assets/game/**/*.json",
                "assets/game/**/License.txt",
                "assets/game/**/OFL.txt",
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
