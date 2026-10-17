"""外部旧副本/工作树迁移清单与字节核验；不跟随共享环境链接。"""
import gzip, hashlib, json, os, subprocess, sys
from pathlib import Path
ARCHIVE=Path(__file__).resolve().parent
ROOT=ARCHIVE.parents[1]

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def prepare():
    if (ARCHIVE/'external.json').exists():raise FileExistsError('外部清单已存在')
    entries=[
        ('visual-identity-v1', ROOT.parent/'CoastalDrive-VI-v1','worktrees/visual-identity-v1',True),
        ('before-AUDIO-01', ROOT.parent/'backups/CoastalDrive-before-AUDIO-01-20260930','backups/CoastalDrive-before-AUDIO-01-20260930',False),
        ('gr86-physics',Path('C:/Users/15120/.codex/worktrees/gr86-physics/CoastalDrive'),'worktrees/gr86-physics',True),
        ('simulation-fidelity',Path('C:/Users/15120/.codex/worktrees/simulation-fidelity/CoastalDrive'),'worktrees/simulation-fidelity',True)]
    rows=[]
    with gzip.open(ARCHIVE/'external-files.jsonl.gz','wt',encoding='utf8') as manifest:
        for label,source,destination,git in entries:
            source=source.resolve()
            if not source.is_dir():raise FileNotFoundError(source)
            if (ARCHIVE/destination).exists():raise FileExistsError(destination)
            entry={'label':label,'original':str(source),'archived':destination,'git':git,'links':[],'files':0,'bytes':0}
            if git:
                status=subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=source,text=True)
                if status:raise ValueError(f'工作树不是干净状态：{source}\n{status}')
                entry['head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
                entry['branch']=subprocess.check_output(['git','branch','--show-current'],cwd=source,text=True).strip()
                entry['unmerged_commits']=int(subprocess.check_output(['git','rev-list','--count','main..HEAD'],cwd=source,text=True))
            for base,dirs,names in os.walk(source,followlinks=False):
                for name in list(dirs):
                    p=Path(base)/name
                    if p.is_symlink() or p.is_junction():
                        entry['links'].append({'path':p.relative_to(source).as_posix(),'target':os.readlink(p)})
                        dirs.remove(name)
                for name in sorted(names):
                    p=Path(base)/name
                    n=p.stat().st_size
                    manifest.write(json.dumps({'root':label,'path':p.relative_to(source).as_posix(),'bytes':n,'sha256':sha(p)},ensure_ascii=False)+'\n')
                    entry['files']+=1;entry['bytes']+=n
                    if entry['files']%20000==0:print(label,entry['files'],'files',flush=True)
            rows.append(entry)
            print(label,entry['files'],round(entry['bytes']/2**30,3),'GiB',flush=True)
    report={'baseline':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'roots':rows,
            'files':sum(x['files'] for x in rows),'bytes':sum(x['bytes'] for x in rows),
            'manifest_sha256':sha(ARCHIVE/'external-files.jsonl.gz')}
    (ARCHIVE/'external.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('外部归档清单完成',report['files'],report['bytes'],flush=True)

def verify(copy=False, reuse_copy_hashes=False):
    plan=json.loads((ARCHIVE/'external.json').read_text(encoding='utf8'))
    if sha(ARCHIVE/'external-files.jsonl.gz')!=plan['manifest_sha256']:raise ValueError('外部清单SHA不符')
    if reuse_copy_hashes:
        proof=json.loads((ARCHIVE/'external-copy-verification.json').read_text(encoding='utf8'))
        if not proof['passed'] or proof['manifest_sha256']!=plan['manifest_sha256'] or proof['pruned_files']:
            raise ValueError('不能复用外部迁移前完整校验')
    roots={row['label']:row for row in plan['roots']}
    count=size=0
    pruned_path=ARCHIVE/'pruned-files.jsonl.gz'
    pruned=set(json.loads(line) for line in gzip.open(pruned_path,'rt',encoding='utf8')) if pruned_path.exists() else set()
    removed_count=removed_bytes=0
    with gzip.open(ARCHIVE/'external-files.jsonl.gz','rt',encoding='utf8') as manifest:
        for line in manifest:
            row=json.loads(line)
            p=ARCHIVE/roots[row['root']]['archived']/row['path']
            if p.relative_to(ARCHIVE).as_posix() in pruned:
                if p.exists():raise ValueError(f'已精简文件仍存在：{p}')
                removed_count+=1;removed_bytes+=row['bytes'];continue
            if p.stat().st_size!=row['bytes'] or (not reuse_copy_hashes and sha(p)!=row['sha256']):
                raise ValueError(f'归档不一致：{p}')
            count+=1;size+=row['bytes']
            if count%25000==0:print('外部核验',count,flush=True)
    if (count+removed_count,size+removed_bytes)!=(plan['files'],plan['bytes']):raise ValueError('外部统计不符')
    for row in plan['roots']:
        path=ARCHIVE/row['archived']
        if not copy and Path(row['original']).exists():raise ValueError(f'旧目录仍存在：{row["original"]}')
        for link in row['links']:
            if os.readlink(path/link['path'])!=link['target']:raise ValueError(f'链接不符：{link}')
        if row['git']:
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=path,text=True).strip()
            status=subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=path,text=True)
            if head!=row['head'] or status:raise ValueError(f'工作树状态不符：{path}')
    result={'passed':True,'files':count,'bytes':size,'roots':len(roots),'git_worktrees_preserved':3,
            'pruned_files':removed_count,'pruned_bytes':removed_bytes,'manifest_sha256':plan['manifest_sha256']}
    result['full_hash_evidence']='external-copy-verification.json' if reuse_copy_hashes else 'this_run'
    (ARCHIVE/('external-copy-verification.json' if copy else 'external-verification.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result),flush=True)

if __name__=='__main__':{'prepare':prepare,'verify':verify,'verify-copy':lambda:verify(copy=True),
                       'verify-retained':lambda:verify(reuse_copy_hashes=True)}[sys.argv[1]]()
