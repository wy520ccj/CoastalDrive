"""准备隔离仿真运行时的官方源/工具依赖；不安装、不修改现有Python环境。"""

import hashlib
import json
import time
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT/"build/sim-double-runtime"
PACKAGES = (
    ("panda-source","https://codeload.github.com/panda3d/panda3d/zip/refs/tags/v1.10.16","panda-source",True),
    ("panda-tools","https://www.panda3d.org/download/panda3d-1.10.16/panda3d-1.10.16-tools-win64.zip","panda-source",True),
    ("bullet-source","https://codeload.github.com/bulletphysics/bullet3/zip/refs/tags/2.84","bullet-source",True),
)


def prepare():
    BUILD.mkdir(parents=True,exist_ok=True)
    ledger = {}
    for key,url,destination,strip_root in PACKAGES:
        archive = BUILD/(key+".zip")
        if not archive.exists():
            partial = archive.with_suffix(".part")
            count,last = 0,time.monotonic()
            with urllib.request.urlopen(url,timeout=60) as response,partial.open("wb") as stream:
                while blob:=response.read(1024*1024):
                    stream.write(blob);count+=len(blob)
                    if time.monotonic()-last>5:
                        print(f"{key}: {count//(1024*1024)} MiB received",flush=True);last=time.monotonic()
            partial.replace(archive)
        output = (BUILD/destination).resolve()
        if not output.is_relative_to(BUILD.resolve()):raise ValueError("依赖输出路径越界")
        output.mkdir(parents=True,exist_ok=True)
        digests = {}
        links = {}
        with zipfile.ZipFile(archive) as package:
            for item in package.infolist():
                if item.is_dir():continue
                parts = Path(item.filename).parts
                relative = Path(*(parts[1:] if strip_root else parts))
                target = (output/relative).resolve()
                if not target.is_relative_to(output):raise ValueError("上游归档路径越界")
                target.parent.mkdir(parents=True,exist_ok=True)
                blob = package.read(item)
                if (item.external_attr>>16)&0o170000==0o120000:
                    link = PurePosixPath(blob.decode("utf-8"))
                    if link.is_absolute() or ".." in link.parts:raise ValueError("上游链接目标越界")
                    member = str(PurePosixPath(item.filename).parent/link)
                    linked = package.getinfo(member)
                    if (linked.external_attr>>16)&0o170000==0o120000:raise ValueError("依赖不接受链接链")
                    links[str(relative)] = member
                    blob = package.read(linked)
                target.write_bytes(blob)
                digests[str(relative)] = hashlib.sha256(blob).hexdigest()
        ledger[key] = {"url":url,"sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
                       "bytes":archive.stat().st_size,"destination":str(output),"files":digests,"materialized_links":links}
        (BUILD/"prepared.json").write_text(json.dumps(ledger,indent=2),encoding="utf-8")
        print(f"{key}: extracted {len(digests)} files",flush=True)
    assert (BUILD/"panda-source/makepanda/makepanda.py").is_file()
    assert (BUILD/"panda-source/thirdparty/win-libs-vc14-x64").is_dir()
    assert (BUILD/"bullet-source/src/BulletSoftBody").is_dir()
    print("Official sources and dependencies prepared; runtime not built or installed",flush=True)


if __name__=="__main__":prepare()
