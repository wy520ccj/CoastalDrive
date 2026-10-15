"""按归档SHA恢复本树隔离SDK；不安装或修改全局/共享Python环境。"""

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def restore():
    evidence = ROOT/"docs/evidence/SIM-UNSPRUNG-01/double-runtime"
    manifest = json.loads((evidence/"manifest.json").read_text(encoding="utf-8"))
    archive = evidence/"runtime.zip"
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=manifest["archives"]["runtime.zip"]:
        raise ValueError("隔离SDK归档内容不一致")
    output = (ROOT/manifest["runtime_target"]).resolve()
    if not output.is_relative_to(ROOT/"build"):raise ValueError("SDK恢复路径越界")
    members = json.loads((evidence/"runtime-members.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(archive) as package:
        for name in package.namelist():
            target = (output/name).resolve()
            if not target.is_relative_to(output):raise ValueError("SDK成员路径越界")
            blob = package.read(name)
            if name in members and hashlib.sha256(blob).hexdigest()!=members[name]:raise ValueError(f"SDK成员损坏：{name}")
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists() or hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(blob).digest():target.write_bytes(blob)
    print("Isolated SDK restored; use launchers/vehicle-lab-double-preview.cmd")


if __name__=="__main__":restore()
