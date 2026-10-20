"""原直线四份历史记录逐字段复算；不重跑物理或冒充新的Double驾驶。"""

import argparse
import hashlib
import json
from pathlib import Path

from overtake_check import recheck, sources


def check(output):
    if output.exists():
        raise FileExistsError('结果文件已存在，不能覆盖证据')
    root = Path(__file__).resolve().parents[1]
    archive = root/'docs/evidence/SAFE-OVERTAKE-01'
    manifest = {name.replace('\\', '/'): value for name, value in
                json.loads((archive/'archive-manifest.json').read_text(encoding='utf-8')).items()}
    start = sources()
    cases = []
    for name in ('normal-final', 'normal-unsafe', 'double-planned', 'double-unsafe'):
        for filename in ('summary.json', 'raw.json.gz'):
            relative = name+'/'+filename
            assert hashlib.sha256((archive/relative).read_bytes()).hexdigest() == manifest[relative]['sha256']
        result = recheck(archive/name)
        cases.append({'archive': name, **result, 'new_result_fields': ['route_id', 'traffic_reading', 'incident'],
                      'input_sha256': manifest[name+'/raw.json.gz']['sha256']})
    assert start == sources()
    result = {'passed': True, 'source_start': start, 'source_end': sources(), 'cases': cases,
              'rows': sum(case['rows'] for case in cases),
              'scope': '四份历史实际直线记录的全部原规则字段精确保持，只新增路线/近车/触发点观测；非新物理/SDK执行'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'passed': True, 'rows': result['rows']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve())))
