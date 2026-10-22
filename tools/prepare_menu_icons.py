"""取得固定版本Tabler字体，只保留首页使用的五个开放图标。"""

import hashlib
import io
import json
import re
import tarfile
import urllib.request
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
VERSION = '3.49.0'
URL = f'https://registry.npmjs.org/@tabler/icons-webfont/-/icons-webfont-{VERSION}.tgz'
ICONS = ('trophy', 'car', 'beach', 'stopwatch', 'chart-dots')


def main():
    source = ROOT/'art/ui/menu-icons'
    source.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read()
    (source/'tabler-icons-webfont-3.49.0.tgz').write_bytes(data)
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        css = archive.extractfile('package/dist/tabler-icons.css').read().decode()
        font_bytes = archive.extractfile('package/dist/fonts/tabler-icons.ttf').read()
        license_text = archive.extractfile('package/LICENSE').read().decode()
    codes = {name: int(re.search(r'\.ti-'+name+r':before\s*\{\s*content: "\\([0-9a-f]+)"', css)[1], 16)
             for name in ICONS}
    font = TTFont(io.BytesIO(font_bytes), recalcTimestamp=False)
    subsetter = subset.Subsetter()
    subsetter.populate(unicodes=codes.values())
    subsetter.subset(font)
    target = ROOT/'assets/game/ui/fonts/Tabler-Menu.ttf'
    font.save(target)
    (target.parent/'License-Tabler-Menu.txt').write_text(license_text, encoding='utf-8')
    report = {'url': URL, 'version': VERSION, 'source_sha256': hashlib.sha256(data).hexdigest(),
              'font_sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'codepoints': codes,
              'process': 'Extract font data without running package code; fontTools subset retains five glyphs.'}
    (source/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
