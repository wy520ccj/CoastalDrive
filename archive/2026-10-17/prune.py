"""仅筛选无回溯意义的缓存、编译中间产物及已校验压缩副本。"""
import gzip,hashlib,json,os,zipfile
from pathlib import Path
ARCHIVE=Path(__file__).resolve().parent

def sha(stream):return hashlib.file_digest(stream,'sha256').hexdigest()

def prepare():
    roots=[]
    cache_names={'__pycache__','.pytest_cache','.ruff_cache','__whl_cache__'}
    for base,dirs,names in os.walk(ARCHIVE,followlinks=False):
        for name in list(dirs):
            p=Path(base)/name
            if p.is_symlink() or p.is_junction():
                dirs.remove(name)
            elif name in cache_names:
                roots.append({'path':p.relative_to(ARCHIVE).as_posix(),'reason':'可重新生成/下载的Python、测试、Ruff或打包wheel缓存'})
                dirs.remove(name)
    for relative in ('build/lib.win-amd64-cpython-314','build/temp.win-amd64-cpython-314',
                     'builds/native-temp','builds/new-lab-merge-native','builds/susp-prep-01-native'):
        if (ARCHIVE/relative).exists():roots.append({'path':relative,'reason':'可由保留源码重新编译的中间产物，src当前原生模块未移动'})
    # 原始大日志存在gzip时，逐字节校验其解压SHA后只保留gzip。
    compressed=[]
    raw=ARCHIVE/'logs/game-drive-r5/render-pstats/raw.txt'
    packed=raw.with_suffix('.txt.gz')
    if raw.exists() and packed.exists():
        with raw.open('rb') as stream:original=sha(stream)
        with gzip.open(packed,'rb') as stream:restored=sha(stream)
        if original!=restored:raise ValueError('原始日志和gzip并不相同，禁止精简')
        roots.append({'path':raw.relative_to(ARCHIVE).as_posix(),'reason':'已验证gzip解压SHA与原始日志完全一致，仅保留gzip'})
        compressed.append({'original':raw.relative_to(ARCHIVE).as_posix(),'retained':packed.relative_to(ARCHIVE).as_posix(),'sha256':original})
    # 压缩包与展开副本所有文件一致时，保留压缩包及校验信息。
    for folder in (ARCHIVE/'builds').glob('lab-perf-*'):
        for packed in folder.glob('*.zip'):
            expanded=packed.with_suffix('')
            if not expanded.is_dir():continue
            actual={p.relative_to(expanded).as_posix():p for p in expanded.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
            with zipfile.ZipFile(packed) as z:
                members={i.filename:i for i in z.infolist() if not i.is_dir()}
                if actual.keys()!=members.keys():continue
                same=True
                for name,p in actual.items():
                    with p.open('rb') as stream:a=sha(stream)
                    with z.open(name) as stream:b=sha(stream)
                    if a!=b:same=False;break
                if same:
                    roots.append({'path':expanded.relative_to(ARCHIVE).as_posix(),'reason':'展开副本与相邻zip全量文件SHA一致，保留zip'})
                    compressed.append({'original':expanded.relative_to(ARCHIVE).as_posix(),'retained':packed.relative_to(ARCHIVE).as_posix(),'kind':'zip-directory'})
    # 去掉被更大精简根覆盖的重复条目。
    roots.sort(key=lambda row:(len(Path(row['path']).parts),row['path']))
    selected=[]
    for row in roots:
        if not any(Path(row['path']).is_relative_to(Path(x['path'])) for x in selected):selected.append(row)
    count=size=0
    removed=[]
    for row in selected:
        p=(ARCHIVE/row['path']).resolve()
        if not p.is_relative_to(ARCHIVE) or p==ARCHIVE:raise ValueError('精简路径越界')
        paths=[p] if p.is_file() else [x for x in p.rglob('*') if x.is_file()]
        for q in paths:
            removed.append(q.relative_to(ARCHIVE).as_posix())
            count+=1;size+=q.stat().st_size
    report={'roots':selected,'files':count,'bytes':size,'compressed_replacements':compressed}
    (ARCHIVE/'prune.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    with gzip.open(ARCHIVE/'pruned-files.jsonl.gz','wt',encoding='utf8') as stream:
        for p in removed:stream.write(json.dumps(p,ensure_ascii=False)+'\n')
    print(json.dumps({'roots':len(selected),'files':count,'gib':round(size/2**30,3),'compressed_replacements':len(compressed)},ensure_ascii=False),flush=True)

if __name__=='__main__':prepare()
