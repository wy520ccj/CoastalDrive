"""PERF-02固定12车短测；可从Git载入优化前美术用于同机A/B。"""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/"src"),str(ROOT/"tools/environment")]
from check_expressway import drive

from application import CoastalDrive

parser = argparse.ArgumentParser()
parser.add_argument("--output",type=Path,required=True)
parser.add_argument("--baseline",action="store_true")
args = parser.parse_args()
args.output.mkdir(parents=True,exist_ok=False)
os.environ["LOCALAPPDATA"] = str(args.output.resolve()/"user-data")
if args.baseline:
    for name in ("expressway_route","expressway_mountains"):
        module = ModuleType("environment."+name)
        source = subprocess.check_output(["git","show",f"f9431dd:src/environment/{name}.py"],cwd=ROOT).decode("utf-8")
        exec(compile(source,name,"exec"),module.__dict__)  # noqa: S102 - 固定本仓库提交的离线A/B
        sys.modules[module.__name__] = module
app = CoastalDrive(smoke=True,onscreen=True,track="endless",road_shape="hills",seed=23,output=args.output,render_size=(1920,1080))
app.taskMgr.remove("finish-smoke")
try:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32",use_last_error=True)
    user32.ShowWindow.argtypes = [wintypes.HWND,ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    window = app.win.getWindowHandle().getIntHandle()
    user32.ShowWindow(window,9)
    user32.SetForegroundWindow(window)
    passed = drive(app,args.output,45,True)
finally:
    app.close_game()
raise SystemExit(0 if passed else 1)
