"""方案库静态实际界面；只读恢复既有真实方案，不重复物理或道路驾驶。"""

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import Filename

from lab_application import VehicleLab
from vehicle_schemes import compare_schemes


def check(output, size, before):
    output.mkdir(parents=True)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    source = ROOT/'docs/evidence/DESIGN-SCHEMES-01/normal/schemes'
    hashes = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in source.rglob('*') if p.is_file()}
    app = VehicleLab(offscreen=True, output=output/'reports', scheme_root=output/'schemes', render_size=tuple(size))
    app.engine.taskMgr.remove('lab-update')
    panel = app.schemes
    try:
        def capture(name):
            app.resize()
            for _ in range(4):
                app.engine.taskMgr.step()
            app.engine.graphicsEngine.syncFrame()
            assert app.engine.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))

        panel.show()
        capture('empty')
        shutil.copytree(source, app.scheme_root, dirs_exist_ok=True)
        for archive in app.scheme_root.rglob('*.gz'):
            archive.with_suffix('').write_bytes(gzip.decompress(archive.read_bytes()))
        panel.refresh()
        panel.move(1, 1)
        comparison = compare_schemes(panel.selected(0), panel.selected(1))
        assert comparison['comparable'] and len(comparison['rows']) == 5
        original = app.active_record(), app.baseline, app.workspace_vehicle
        identities = panel.selected(0).id, panel.selected(1).id
        capture('comparable')
        # 只注入可比判定的UI数据，原真实记录/元数据不改；不伪称新的跨工况物理。
        with patch('ui.lab_schemes.compare_schemes', return_value={**comparison,
                'comparable': False, 'mismatches': ['试验工况/车型/路面']}):
            panel.present()
            capture('conditions-differ')
            assert panel.curves_button['state'] == (DGG.NORMAL if before else DGG.DISABLED)
            assert panel.load_button['state'] == panel.drive_button['state'] == DGG.NORMAL
        panel.present()
        assert panel.curves_button['state'] == DGG.NORMAL
        panel.menus[1].showPopupMenu()
        panel.menus[1].hidePopupMenu()
        panel.hide()
        panel.show()
        assert (panel.selected(0).id, panel.selected(1).id) == identities
        assert (app.active_record(), app.baseline, app.workspace_vehicle) == original
        assert all(hashlib.sha256((source/name).read_bytes()).hexdigest() == digest for name, digest in hashes.items())
        assert all(hashlib.sha256((app.scheme_root/name).read_bytes()).hexdigest() == digest for name, digest in hashes.items())
        result = {'passed': True, 'size': size, 'before': before, 'source': str(source.relative_to(ROOT)),
                  'original_record_sha256': hashes, 'identities': identities, 'metrics': comparison['rows'],
                  'records_and_workspace_unchanged': True, 'mismatch_uses_explicit_ui_fixture': True,
                  'scope': '历史两真实方案静态复载，不新跑物理；条件不一致仅UI数据注入'}
        (output/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'passed': True, 'images': 3}
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    parser.add_argument('--before', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.before)))
