"""同光照查看本机原树的完整轮廓；资源选型图，不是实际驾驶验收。"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from kcd_local_assets import load_local
from local_kcd_drive import SHADOW_MASK, LocalVegetation, soft_cutout, tree_shader
from panda3d.core import Filename, OrthographicLens, TextNode, Vec3, Vec4

from application import CoastalDrive
from race import GameMode
from scene import make_quad


def preview(output):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output / 'user')
    profile = LocalVegetation(output / 'assets', ROOT / 'logs/local-kcd-original-environment')
    profile.install()
    app = None
    try:
        app = CoastalDrive(smoke=True, output=output, render_size=(1600, 1200), threading_model='')
        app.taskMgr.remove('finish-smoke')
        app.taskMgr.remove('drive-update')
        app.start_game(mode=GameMode.FREE_DRIVE, track='endless')
        app.aspect2d.hide()
        for child in tuple(app.scene.render.getChildren()):
            child.hide()
        stage = app.scene.render.attachNewNode('source-oak-catalog')
        make_quad('catalog-floor', Vec3(0, 48, 0), 110, 150, Vec4(.13, .15, .16, 1), -.04).reparentTo(stage)
        trees, _grass, _ground = load_local(output / 'catalog-assets',
            tree_shader(app.scene.expressway_kit['foliage-shader']), tree_letters='abcdefghi')
        records = []
        for index, tree in enumerate(trees):
            letter = 'abcdefghi'[index]
            x, y = (index % 3 - 1) * 33, (index // 3) * 48
            source_height = float(tree.getTag('source-height'))
            tree.reparentTo(stage)
            tree.setPos(x, y, 0)
            tree.setScale(14 / source_height)
            tree.setH(25)
            soft_cutout(tree)
            text = TextNode('catalog-' + letter)
            text.setText(letter.upper() + '  ' + str(round(source_height, 1)) + 'm source')
            text.setAlign(TextNode.ACenter)
            label = stage.attachNewNode(text)
            label.setPos(x, y - 6, .3)
            label.setScale(1.1)
            label.setBillboardPointEye()
            label.setLightOff()
            label.setShaderOff(10)
            label.hide(SHADOW_MASK)
            records.append({'letter': letter, 'source_height_m': source_height, 'display_height_m': 14})
        lens = OrthographicLens()
        lens.setFilmSize(110, 82.5)
        lens.setNearFar(1, 350)
        app.cam.node().setLens(lens)
        app.camera.setPos(0, -80, 100)
        app.camera.lookAt(0, 48, 4)
        app.setBackgroundColor(.11, .13, .15)
        app.scene.update_lighting(Vec3(0, 48, 0))
        for _ in range(20):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / 'oak-catalog.png')))
        (output / 'catalog.json').write_text(json.dumps({
            'scope': '原件资源轮廓选型；同一高度14m与同一光照；非正常随车验收', 'trees': records},
            ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        if app is not None:
            app.close_game()
        profile.restore()


def preview_rocks(output):
    """五种原石按6m高度、两种朝向选轮廓；不把材质图集当原石实景。"""
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output / 'user')
    profile = LocalVegetation(output / 'assets', ROOT / 'logs/local-kcd-original-environment')
    profile.install()
    app = None
    try:
        app = CoastalDrive(smoke=True, output=output, render_size=(1600, 1000), threading_model='')
        app.taskMgr.remove('finish-smoke')
        app.taskMgr.remove('drive-update')
        app.start_game(mode=GameMode.FREE_DRIVE, track='endless')
        app.aspect2d.hide()
        for child in tuple(app.scene.render.getChildren()):
            child.hide()
        stage = app.scene.render.attachNewNode('original-stone-catalog')
        make_quad('catalog-floor', Vec3(0, 12, 0), 65, 60, Vec4(.13, .15, .16, 1), -.04).reparentTo(stage)
        records = []
        for column, (name, original) in enumerate(app.scene.expressway_kit['local-kcd-rocks'].items()):
            for row, heading in enumerate((0, 137)):
                node = original.copyTo(stage)
                node.node().forceSwitch(0)
                scale = 6 / float(node.getTag('source-height'))
                node.setScale(scale)
                x, y = (column - 2) * 12, row * 24
                node.setPos(x, y, -float(node.getTag('source-base')) * scale)
                node.setH(heading)
                text = TextNode('catalog-' + name)
                text.setText(name + '  ' + str(heading))
                text.setAlign(TextNode.ACenter)
                label = stage.attachNewNode(text)
                label.setPos(x, y - 7, .1)
                label.setScale(.7)
                label.setBillboardPointEye()
                label.setLightOff()
                label.setShaderOff(10)
                label.hide(SHADOW_MASK)
                low, high = node.getTightBounds(stage)
                records.append({'shape': name, 'heading': heading, 'display_height_m': 6.,
                                 'display_dimensions_m': list(high - low)})
        lens = OrthographicLens()
        lens.setFilmSize(66, 41.25)
        lens.setNearFar(1, 250)
        app.cam.node().setLens(lens)
        app.camera.setPos(0, -50, 43)
        app.camera.lookAt(0, 11, 2)
        app.scene.update_lighting(Vec3(0, 12, 0))
        for _ in range(24):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / 'stone-catalog.png')))
        (output / 'catalog.json').write_text(json.dumps({'scope': '原石实机资源选型，非正常随车验收',
                                                        'stones': records}, indent=2), encoding='utf-8')
    finally:
        if app is not None:
            app.close_game()
        profile.restore()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rocks', action='store_true')
    args = parser.parse_args()
    (preview_rocks if args.rocks else preview)(args.output.resolve())
