"""按已冻结的来源与SHA下载源植物，已核对文件不重复下载。"""

import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]


def main():
    records = []
    for folder in ('vegetation', 'tree-small-02', 'grass-bermuda-01'):
        manifest = json.loads((ROOT/f'art/expressway/sources/{folder}/manifest.json').read_text(encoding='utf-8'))
        records.extend(manifest['files'])
    for record in records:
        path = ROOT/record['path']
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']:
            print('Verified', record['path'])
            continue
        request = Request(record['url'], headers={'User-Agent': 'CoastalDrive asset preparation; Powered by Poly Haven'})
        with urlopen(request, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != record['sha256']:
            raise ValueError(f'素材SHA不符：{record["url"]}')
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix+'.tmp')
        temporary.write_bytes(data)
        temporary.replace(path)
        print('Fetched', record['path'])


if __name__ == '__main__':
    main()
