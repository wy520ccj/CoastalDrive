from setuptools import setup


setup(
    name="coastaldrive",
    version="0.6.2",
    options={
        "build_apps": {
            "gui_apps": {"coastaldrive": "src/main.py"},
            "platforms": ["win_amd64"],
            "log_filename": "$USER_APPDATA/CoastalDrive/coastaldrive.log",
            "log_append": False,
            "include_patterns": [
                "assets/game/**/*.glb",
                "assets/game/**/*.png",
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
