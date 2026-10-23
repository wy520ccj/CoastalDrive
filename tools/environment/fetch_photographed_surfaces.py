"""按固定来源和SHA取得实拍道路材质；已核对文件不重复下载。"""

import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]


def main():
    manifest = json.loads((ROOT/'art/expressway/sources/road-materials/manifest.json').read_text(encoding='utf-8'))
    for record in manifest['files'].values():
        path = ROOT/record['runtime']
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']:
            print('Verified', record['runtime'])
            continue
        request = Request(record['url'], headers={'User-Agent': 'CoastalDrive asset preparation'})
        with urlopen(request, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != record['sha256']:
            raise ValueError(f'素材SHA不符：{record["url"]}')
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix+'.tmp')
        temporary.write_bytes(data)
        temporary.replace(path)
        print('Fetched', record['runtime'])


if __name__ == '__main__':
    main()
