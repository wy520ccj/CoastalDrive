"""九份历史交通记录全旧字段比较；新增读数只分析原始拍，不重跑完整驾驶。"""

import argparse
import hashlib
import json
from pathlib import Path

from overtake_check import recheck, sources


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    start = sources()
    cases = []
    result = {'passed': False, 'source_start': start, 'cases': cases,
              'scope': '全部历史旧字段逐拍精确保持；新增观测来自历史真实拍，非新物理或Double执行'}
    try:
        for archive, names in (
            ('SAFE-OVERTAKE-01', ('normal-final', 'normal-unsafe', 'double-planned', 'double-unsafe')),
            ('HILL-TRAFFIC-01', ('normal-planned', 'normal-unsafe', 'double-planned', 'double-unsafe', 'normal-follow')),
        ):
            folder = root/'docs/evidence'/archive
            manifest = {name.replace('\\', '/'): value for name, value in
                        json.loads((folder/'archive-manifest.json').read_text(encoding='utf-8')).items()}
            for name in names:
                for filename in ('raw.json.gz', 'summary.json'):
                    relative = name+'/'+filename
                    assert hashlib.sha256((folder/relative).read_bytes()).hexdigest() == manifest[relative]['sha256']
                verified = recheck(folder/name)
                cases.append({'archive': archive, 'case': name, **verified,
                              'raw_sha256': manifest[name+'/raw.json.gz']['sha256']})
        result.update(passed=True, source_end=sources(), rows=sum(case['rows'] for case in cases))
        assert result['rows'] == 61697 and start == sources()
        assert {'front', 'parallel', 'clear'} <= {kind for case in cases for kind in case['reading_kinds']}
        for case in cases:
            if 'unsafe' in case['case']:
                assert case['incident'] is not None and case['incident']['side_m'] < 1. and case['incident']['end_m'] < 10.
        return {'passed': True, 'rows': result['rows'], 'cases': len(cases)}
    finally:
        (output/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve()), ensure_ascii=False))
