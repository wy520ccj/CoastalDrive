"""归档前后核对文件与当前运行依赖；只读检查，不移动文件。"""
import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ARCHIVE = Path(__file__).resolve().parent
ROOT = ARCHIVE.parents[1]

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def files(path):
    if path.is_file():
        yield path
    else:
        for base, dirs, names in os.walk(path, followlinks=False):
            dirs[:] = [name for name in dirs if not (Path(base)/name).is_symlink()
                       and not (Path(base)/name).is_junction()]
            for name in sorted(names):
                yield Path(base)/name

def prepare():
    if (ARCHIVE/'moves.json').exists():
        raise FileExistsError('本批清单已存在，不能覆盖归档前证据')
    candidates = []
    def add(path, reason):
        source = path.resolve()
        if not source.is_relative_to(ROOT) or source == ROOT or source.is_relative_to(ARCHIVE):
            raise ValueError(f'归档路径越界：{source}')
        relative = source.relative_to(ROOT).as_posix()
        candidates.append({'original': relative, 'archived': relative, 'reason': reason})
    for p in sorted((ROOT/'builds').iterdir()):
        add(p, '历史独立包、性能基线源码或可再生编译中间产物')
    for p in sorted((ROOT/'build').iterdir()):
        if p.name != 'sim-double-runtime':
            add(p, '旧原生扩展构建中间产物；当前运行从src加载')
    for p in sorted((ROOT/'launchers').iterdir()):
        if p.name == 'archive' or p.name.startswith('physics-'):
            add(p, '历史版本启动器及说明')
    add(ROOT/'legacy', '只读旧MFC工程，整目录保留内部字节')
    keep_logs = {'validation', 'manual-playtest', 'lab-parameter-05', 'project-archive-20261017', '.gitkeep'}
    for p in sorted((ROOT/'logs').iterdir()):
        if p.name not in keep_logs:
            add(p, '已结束阶段的日志、验证输出或诊断源码快照')
    for p in sorted((ROOT/'logs/validation').iterdir()):
        if not p.name.startswith('LAB-PARAMETER-05'):
            add(p, '已结束阶段验证日志；包含失败与中断原始记录')
    keep_manual = {'lab_parameters_fixed.py', 'parameters-fixed.stdout.log', 'parameters-fixed.stderr.log'}
    for p in sorted((ROOT/'logs/manual-playtest').iterdir()):
        if p.name not in keep_manual:
            add(p, '旧窗口启动器或已结束人工诊断日志')
    total_files = total_bytes = 0
    links = []
    with gzip.open(ARCHIVE/'files.jsonl.gz', 'wt', encoding='utf-8') as manifest:
        for i, item in enumerate(candidates):
            count = size = 0
            source = ROOT/item['original']
            if source.is_dir():
                for base, dirs, names in os.walk(source, followlinks=False):
                    for name in list(dirs):
                        p = Path(base)/name
                        if p.is_symlink() or p.is_junction():
                            links.append({'path': p.relative_to(ROOT).as_posix(), 'target': os.readlink(p)})
                            dirs.remove(name)
            for p in files(ROOT/item['original']):
                relative = p.relative_to(ROOT).as_posix()
                n = p.stat().st_size
                row = {'path': relative, 'bytes': n, 'sha256': digest(p)}
                manifest.write(json.dumps(row, ensure_ascii=False)+'\n')
                count += 1; size += n
            item.update(files=count, bytes=size)
            total_files += count; total_bytes += size
            if i%50 == 0:
                print(f'清单进度 {i+1}/{len(candidates)}，{total_files}文件', flush=True)
    # 当前运行树、开发入口和双精度SDK单独冻结指纹。
    protected = []
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf8').split('\0')
    prefixes = ('src/', 'assets/game/', 'art/', 'vendor/', 'tools/', 'tests/')
    names = {'setup.py', 'pyproject.toml', 'requirements.txt', 'requirements-dev.txt', 'requirements-lock.txt',
             '试玩.cmd', '试玩-物理开发.cmd'}
    paths = {ROOT/p for p in tracked if p and (p.startswith(prefixes) or p in names
             or (p.startswith('launchers/') and not (p.startswith('launchers/physics-') or p.startswith('launchers/archive/'))))}
    paths.update((ROOT/'src').glob('*.pyd'))
    paths.update(files(ROOT/'build/sim-double-runtime'))
    for p in sorted(paths):
        protected.append({'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest(p)})
    (ARCHIVE/'protected.json').write_text(json.dumps(protected, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    plan = {'schema': 'coastaldrive-archive-v1', 'baseline': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'root': str(ROOT), 'roots': candidates, 'files': total_files, 'bytes': total_bytes,
            'manifest_sha256': digest(ARCHIVE/'files.jsonl.gz'), 'protected_files': len(protected),
            'links': links,
            'protected_manifest_sha256': digest(ARCHIVE/'protected.json')}
    (ARCHIVE/'moves.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({k:v for k,v in plan.items() if k!='roots'}, ensure_ascii=False),flush=True)

def verify():
    plan=json.loads((ARCHIVE/'moves.json').read_text(encoding='utf8'))
    if digest(ARCHIVE/'files.jsonl.gz') != plan['manifest_sha256']:
        raise ValueError('归档文件清单SHA不符')
    count=size=0
    pruned_path=ARCHIVE/'pruned-files.jsonl.gz'
    pruned=set(json.loads(line) for line in gzip.open(pruned_path,'rt',encoding='utf8')) if pruned_path.exists() else set()
    removed_count=removed_bytes=0
    with gzip.open(ARCHIVE/'files.jsonl.gz','rt',encoding='utf8') as stream:
        for line in stream:
            row=json.loads(line)
            p=ARCHIVE/row['path']
            if row['path'] in pruned:
                if p.exists():raise ValueError(f'已精简文件仍存在：{p}')
                removed_count+=1;removed_bytes+=row['bytes']
                continue
            if p.stat().st_size != row['bytes'] or digest(p) != row['sha256']:
                raise ValueError(f'归档文件不一致：{p}')
            count+=1;size+=row['bytes']
            if count%20000==0: print(f'核验 {count}文件',flush=True)
    if (count+removed_count,size+removed_bytes)!=(plan['files'],plan['bytes']):raise ValueError('归档统计不符')
    protected=json.loads((ARCHIVE/'protected.json').read_text(encoding='utf8'))
    for link in plan['links']:
        p=ARCHIVE/link['path']
        if os.readlink(p)!=link['target']:raise ValueError(f'链接目标改变：{p}')
    if digest(ARCHIVE/'protected.json') != plan['protected_manifest_sha256']:
        raise ValueError('受保护清单SHA不符')
    edits_path=ARCHIVE/'metadata-edits.json'
    edits={row['path']:row for row in json.loads(edits_path.read_text(encoding='utf8'))} if edits_path.exists() else {}
    for row in protected:
        p=ROOT/row['path']
        if row['path'] in edits:
            edit=edits[row['path']]
            if row['sha256']!=edit['before_sha256'] or digest(p)!=edit['after_sha256']:
                raise ValueError(f'入口说明变更与登记不一致：{p}')
            continue
        if p.stat().st_size!=row['bytes'] or digest(p)!=row['sha256']:
            raise ValueError(f'当前文件被改变：{p}')
    for item in plan['roots']:
        if not (ARCHIVE/item['archived']).exists() and not any(Path(p).is_relative_to(item['archived']) for p in pruned):
            raise FileNotFoundError(item['archived'])
        if (ROOT/item['original']).exists():raise ValueError(f'旧位置仍存在：{item["original"]}')
    report={'passed':True,'files':count,'bytes':size,'roots':len(plan['roots']),
            'pruned_files':removed_count,'pruned_bytes':removed_bytes,
            'links_unchanged':len(plan['links']), 'protected_files_unchanged':len(protected)-len(edits),
            'intentional_metadata_edits':list(edits),
            'manifest_sha256':plan['manifest_sha256']}
    (ARCHIVE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':
    {'prepare':prepare,'verify':verify}[sys.argv[1]]()
