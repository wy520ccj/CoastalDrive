"""为隔离SDK复制渲染依赖，修正已声明的GPU float数组边界；共享包保持。"""

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT/"build/sim-double-runtime"


def configure():
    spec = importlib.util.find_spec("simplepbr")
    if spec is None:raise ModuleNotFoundError("现有环境缺少simplepbr")
    source = Path(spec.origin).parent
    target = BUILD/"panda-source/built-double/simplepbr"
    shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    file = target/"envmap.py"
    original_bytes = file.read_bytes()
    original = original_bytes.replace(b"\r\n",b"\n")
    old,new = b"p3d.LVecBase3(0, 0, 0)",b"p3d.LVecBase3f(0, 0, 0)"
    assert original.count(old)==1
    bam_old,bam_new = b"envmap.sh_coefficients[idx] = p3d.LVector3(",b"envmap.sh_coefficients[idx] = p3d.LVector3f("
    assert original.count(bam_old)==1
    adapted = original.replace(old,new).replace(bam_old,bam_new)
    # 从CPU投影返回的颜色向量也明确转成已声明的GPU数组类型。
    assignment = b"for idx, val in enumerate(shcoeffs):\n                self.sh_coefficients[idx] = val"
    assert adapted.count(assignment)==1
    adapted = adapted.replace(assignment,b"self._store_sh_coefficients(shcoeffs)")
    anchor = b"    @property\n    def hash"
    assert adapted.count(anchor)==1
    method = b"    def _store_sh_coefficients(self, values):\n        for idx, value in enumerate(values):\n            self.sh_coefficients[idx] = p3d.LVecBase3f(*value)\n\n"
    adapted = adapted.replace(anchor,method+anchor)
    file.write_bytes(adapted)
    cpu = target/"_ibl_funcs_cpu.py"
    cpu_original = cpu.read_bytes()
    (BUILD/"render-configuration.json").write_text(json.dumps({"package":"simplepbr 0.13.1",
        "source":str(source),"original":hashlib.sha256(original_bytes).hexdigest(),"adapted":hashlib.sha256(file.read_bytes()).hexdigest(),
        "cpu_original":hashlib.sha256(cpu_original).hexdigest(),"cpu_adapted":hashlib.sha256(cpu.read_bytes()).hexdigest(),
        "reason":"PTA_LVecBase3f spherical harmonic color array requires LVecBase3f; physical math stays double",
        "shared_package_changed":False},indent=2),encoding="utf-8")
    print("Isolated simplepbr GPU array adapter configured")


if __name__=="__main__":configure()
