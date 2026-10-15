"""显式开发预览入口：导入已有完整轮心工程配置，不改变常规实验室默认车型。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from lab_application import VehicleLab

if __name__=="__main__":
    app = VehicleLab()
    try:
        app.import_engineering(ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json")
        app.run()
    finally:
        app.close_game()
