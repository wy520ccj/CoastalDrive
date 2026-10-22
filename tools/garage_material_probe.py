"""隔离车库反射诊断；候选只在当前进程中显示，不写车型和物理。"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename, Material, MaterialAttrib

from application import CoastalDrive


def capture(output, design):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True, output=output)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')

    def shot(name):
        for _ in range(8):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))

    try:
        app.open_career_collection()
        app.career_action('garage-car', design)
        view = app.workshop_vehicle
        shot('01-baseline')
        report = []
        for node in view.car_root.findAllMatches('**/paint'):
            for geom in node.node().getGeoms():
                report.append({'name': node.getName(), 'vertex_format': str(geom.getVertexData().getFormat()),
                               'net_state': str(node.getNetState()), 'geom_state': str(node.node().getGeomState(0))})
        (output/'states.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        for node in view.car_root.findAllMatches('**/paint'):
            material = Material(node.getNetState().getAttrib(MaterialAttrib).getMaterial())
            material.setMetallic(1.)
            material.setRoughness(.06)
            node.setMaterial(material, 2)
        shot('02-mirror')
        view.pipeline.max_lights = 4
        shot('03-lights')
        for roughness, metallic in ((.10, .45), (.12, .65), (.15, .8)):
            for node in view.car_root.findAllMatches('**/paint'):
                material = Material(node.getNetState().getAttrib(MaterialAttrib).getMaterial())
                material.setMetallic(metallic)
                material.setRoughness(roughness)
                node.setMaterial(material, 2)
            shot(f'04-gloss-{roughness}-{metallic}')
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--car', default='club-coupe')
    args = parser.parse_args()
    capture(args.output.resolve(), args.car)
