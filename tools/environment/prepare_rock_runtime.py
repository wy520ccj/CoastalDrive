"""把已登记的原岩岸完整转换成Panda资源，避免每次进入道路重算glTF切线。"""

import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import gltf
from panda3d.core import Filename, NodePath, loadPrcFileData

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'assets/game/expressway/runtime-rocks'
SOURCES = (ROOT/'art/expressway/candidates/coastal-rocks/coastal-rocks.glb',
           ROOT/'art/expressway/candidates/driving-rocks/driving-rocks.glb')


def prepare():
    OUTPUT.mkdir(exist_ok=True)
    loadPrcFileData('rock-runtime-export', 'bam-texture-mode rawdata')
    entries = []
    for path in SOURCES:
        source = NodePath(gltf.load_model(Filename.fromOsSpecific(str(path))))
        target = OUTPUT/(path.stem+'.bam')
        temporary = target.with_suffix('.tmp.bam')
        if not source.writeBamFile(Filename.fromOsSpecific(str(temporary))):
            raise OSError('无法写入岩岸运行资源：'+str(temporary))
        temporary.replace(target)
        entries.append({'source': path.relative_to(ROOT).as_posix(),
                        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'output': target.relative_to(ROOT).as_posix(),
                        'output_sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        source.removeNode()
        print('PREPARED', target.name, target.stat().st_size, flush=True)
    document = {'schema': 'coastal-rock-runtime-v1',
                'converter': {'panda3d': version('panda3d'), 'panda3d-gltf': version('panda3d-gltf')},
                'changes': ['同一glTF转换结果完整序列化', '保留全部网格/切线/材质/内嵌贴图',
                            '原GLB、LOD命名和运行时岩岸着色器不改'], 'assets': entries}
    temporary = OUTPUT/'manifest.tmp.json'
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(OUTPUT/'manifest.json')


if __name__ == '__main__':
    prepare()
