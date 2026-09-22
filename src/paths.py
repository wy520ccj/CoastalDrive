import os
import sys
from pathlib import Path


def resource_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data():
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    target = root / "CoastalDrive"
    target.mkdir(parents=True, exist_ok=True)
    return target
