"""用指定的Filediver只读导出本机HD2岩壁，记录工具和原件身份。"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL = Path('D:/SteamLibrary/steamapps/common/Helldivers 2')
MEMBER = 'content/env_shared/assets/rocks/neutral/rock_cliff_face_01.unit'


def prepare(executable, output):
    if not output.absolute().is_relative_to(ROOT / 'logs'):
        raise ValueError('本机商业游戏衍生资源仅写入ignored logs')
    files = sorted(path for path in (INSTALL / 'data').iterdir() if path.is_file())
    before = {path.name: [path.stat().st_size, path.stat().st_mtime_ns] for path in files}
    output.mkdir(parents=True, exist_ok=False)
    command = [str(executable.resolve()), '--gamedir', str(INSTALL), '-i', MEMBER,
               '--model-format', 'glb', '--model-include-lods', '--unit-all-textures',
               '--planet-name', 'Turing', '--planet-sub-region', 'A', '-o', str(output)]
    with (output / 'extraction.log').open('w', encoding='utf-8') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    source = output / (MEMBER + '.glb')
    if not source.is_file():
        raise FileNotFoundError('工具退出后没有目标GLB，不能记为提取成功')
    after = {path.name: [path.stat().st_size, path.stat().st_mtime_ns] for path in files}
    if before != after:
        raise RuntimeError('导出前后原安装的大小/修改时间变化，需检查')
    report = {'scope': '用户授权的本机原岩壁样板；衍生仅ignored logs，不是可分发资源',
              'tool_source': 'https://github.com/xypwn/filediver/releases/tag/v0.7.63',
              'tool_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
              'command': command, 'source_member': MEMBER, 'planet': 'Turing', 'subregion': 'A',
              'output_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'installation_size_mtime_before': before, 'installation_size_mtime_after': after,
              'limits': '安装核对是size/mtime，未对24GB原包逐字节哈希；原材质语义仍需GPU实图核对'}
    (output / 'source-manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--filediver', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    prepare(arguments.filediver, arguments.output.absolute())
