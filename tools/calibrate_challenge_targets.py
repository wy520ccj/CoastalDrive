"""用指定来源的重复逐拍记录生成候选；代理基准须显式选择，不自动改写关卡。"""

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from challenge_calibration import candidate_targets
from challenge_catalog import ROAD_CHALLENGES, distance_challenge_spec
from highway_run import TRAFFIC_DENSITIES
from lap_ghost import ghost_context
from race import GameMode


def sample_spec(challenge, document):
    if challenge != GameMode.DISTANCE_CHALLENGE.value:
        return next(spec for spec in ROAD_CHALLENGES.values() if spec.id == challenge)
    for shape in ('straight', 'hills'):
        for key, density in TRAFFIC_DENSITIES.items():
            suffix = f':road-{shape}:traffic-{density.cars}-{density.spawn_span:g}'
            if document['input_group'].endswith(suffix):
                return distance_challenge_spec(shape, key, document['source_start']['seed'])
    raise ValueError('五公里样本缺少有效道路和车流分组')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--challenge', choices=sorted(spec.id for spec in ROAD_CHALLENGES.values()
                                                     if spec.assessment == 'road'), required=True)
    parser.add_argument('--samples', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--agent-baseline', action='store_true', help='使用自动驾驶逐拍记录生成候选')
    args = parser.parse_args()
    try:
        documents = [json.loads(path.read_text(encoding='utf-8')) for path in args.samples]
        spec = sample_spec(args.challenge, documents[0])
        source = ghost_context(documents[0]['source_start']['seed'])
        targets = candidate_targets(spec, documents, source=source, agent=args.agent_baseline)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, '未生成候选标准：'+str(error)+'\n')
    result = {'challenge': spec.id, 'rules_version': spec.version,
              'source': source,
              'targets': [asdict(target) for target in targets],
              'samples': [{'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                          for path in args.samples],
              'status': 'agent-candidate' if args.agent_baseline else 'candidate',
              'scope': ('自动驾驶重复实跑复算候选，待核对关卡难度后采用。' if args.agent_baseline else
                        '真人重复样本复算候选；尚需实际难度与多方案平衡复核。')}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        parser.exit(1, '输出文件已存在，请使用新的候选编号。\n')
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(str(args.output.resolve()))
