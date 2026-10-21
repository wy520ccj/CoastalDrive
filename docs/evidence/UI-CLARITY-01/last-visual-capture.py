"""末次颜色和状态前缀采集；其余已通过实图复用。"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]
from panda3d.core import Filename
from road_review_check import archived_records
from lab_application import VehicleLab
from road_comparison import RoadResults

width, height = map(int, sys.argv[1:])
tag = '720' if width == 1280 else '4x3'
output = Path(__file__).parent/tag
output.mkdir(exist_ok=False)
os.environ['LOCALAPPDATA'] = str(output/'user-data')
app = VehicleLab(offscreen=True, render_size=(width, height), output=output/'reports',
    scheme_root=ROOT/'logs/validation'/('UI-CLARITY-01-copy-'+tag)/'schemes')
app.engine.taskMgr.remove('lab-update')

def capture(name):
    app.resize()
    for _ in range(5):
        app.engine.taskMgr.step()
    app.engine.graphicsEngine.syncFrame()
    assert app.engine.win.getScreenshot().write(Filename.fromOsSpecific(str(output/name)))
    assert app.run_state is None

try:
    app.schemes.show()
    app.schemes.move(1, 1)
    panel = app.schemes.virtual_driver
    panel.show()
    panel.comparison = RoadResults(archived_records('normal'), 'complete')
    panel.present()
    capture('10-road-result.png')
    app.schemes.hide()
    app.workshop.show()
    capture('02-brake-ready.png')
    (output/'summary.json').write_text(json.dumps({'passed': True, 'size': [width, height],
        'new_physics_ticks': 0, 'images': ['10-road-result.png', '02-brake-ready.png']}), encoding='utf-8')
finally:
    app.close_game()
