"""实验实际运行时的精度/内容摘要；只读已加载库，不创建物理世界。"""

import hashlib
from functools import cache
from pathlib import Path

from panda3d import bullet, core


@cache
def library_hashes():
    directory = Path(core.__file__).parent
    files = [Path(core.__file__),Path(bullet.__file__),*directory.glob("*.dll"),*(directory.parent/"bin").glob("*.dll")]
    return tuple((f"{p.parent.name}/{p.name}",hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(set(files)))


def runtime_fingerprint():
    return {"panda_version":core.PandaSystem.getVersionString(),"bullet_version":bullet.getBulletVersion(),
            "math_scalar_bits":64 if core.LPoint3 is core.LPoint3d else 32,"files":dict(library_hashes())}


def validate_runtime_document(value):
    """外部实验文件边界；摘要只校验结构，不加载其中命名的库。"""
    required = {"panda_version","bullet_version","math_scalar_bits","files"}
    if not isinstance(value,dict) or not required<=value.keys():raise ValueError("运行时摘要字段不完整")
    if (not isinstance(value["panda_version"],str) or type(value["bullet_version"]) is not int
            or type(value["math_scalar_bits"]) is not int or value["math_scalar_bits"] not in (32,64)
            or not isinstance(value["files"],dict) or not value["files"]):
        raise ValueError("运行时精度、版本或库摘要无效")
    for name,digest in value["files"].items():
        if (not isinstance(name,str) or not isinstance(digest,str) or len(digest)!=64
                or any(char not in "0123456789abcdef" for char in digest)):
            raise ValueError("运行时库内容摘要无效")
