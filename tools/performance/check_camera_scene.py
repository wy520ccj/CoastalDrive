"""固定真实随车画面比较原相机输入与分帧存储，不改变几何、材质或镜位。"""

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from panda3d.core import Filename
from simplepbr import Pipeline

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/environment'))
sys.path.insert(0, str(ROOT / 'src'))

from check_driving_composition import check

import application
from rendering import ScenePipeline


def compare(app, output):
    app.taskMgr.remove('simplepbr update')
    images = []
    task = SimpleNamespace(DS_cont=1)
    labels = ('original', 'buffered', 'original-repeat', 'buffered-repeat',
              'ordered-original', 'ordered-buffered')
    for label in labels:
        if label == 'ordered-original':
            # 诊断固定叶片交叠次序，区分排序差异和相机uniform数值差异；不接入游戏。
            for number, node in enumerate(app.scene.render.findAllMatches('**/+GeomNode')):
                node.setBin('fixed', number, 100)
        update = Pipeline._update if 'original' in label else ScenePipeline._update
        update(app.pipeline, task)
        for _ in range(12):
            app.graphicsEngine.renderFrame()
        app.graphicsEngine.syncFrame()
        picture = app.win.getScreenshot()
        picture.write(Filename.fromOsSpecific(str(output/(label+'.png'))))
        images.append(np.frombuffer(picture.getRamImageAs('RGB'), dtype=np.uint8).copy())
    rows = []
    for first, second in ((0, 1), (0, 2), (1, 3), (4, 5)):
        error = np.abs(images[first].astype(np.int16)-images[second])
        rows.append({'pair': [labels[first], labels[second]], 'max_rgb8': int(error.max()),
                     'changed_channels': int(np.count_nonzero(error))})
    report = {'scope': '沿海120m原随车完整场景，同一位置/时间/几何/着色器，直接比较相机输入存储',
              'differences': rows, 'natural_order_identical': rows[0]['max_rgb8'] == 0,
              'passed': all(row['max_rgb8'] == 0 for row in rows[1:]),
              'limits': '原排序差异完整保留；固定顺序仅检查uniform数值等价，不能冒称自然排序全帧零差'}
    (output/'camera-scene.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    assert report['passed'], report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original = application.ScenePipeline
    application.ScenePipeline = ScenePipeline
    try:
        check(args.output.resolve(), False, (1280, 720), end_distance=120, inspect_at_120=compare)
    finally:
        application.ScenePipeline = original
