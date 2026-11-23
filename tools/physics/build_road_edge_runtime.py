"""用固定的 Panda3D 源码和工具包构建本地赛道路面修正 SDK。"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/road-edge-sdk"
SOURCE = BUILD / "panda"
RUNTIME = SOURCE / "built-road-edge"
PATCH = Path(__file__).with_name("panda-road-internal-edges.patch")
PACKAGES = (
    ("panda-source.zip", "https://codeload.github.com/panda3d/panda3d/zip/refs/tags/v1.10.16",
     "259f7089116fef845de6bf6c9bcc7d393a3f953088e8dca9b564bf7d1fdde786"),
    ("panda-tools.zip", "https://www.panda3d.org/download/panda3d-1.10.16/panda3d-1.10.16-tools-win64.zip",
     "c94d346ce486c65a4a251c72360155b7f4f4aa8e6fd702690b7a0aca8ed3616c"),
)


def unpack(name, url, expected):
    archive = BUILD / name
    if not archive.exists():
        print(f"下载 {name}", flush=True)
        urllib.request.urlretrieve(url, archive.with_suffix(".part"))
        archive.with_suffix(".part").replace(archive)
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
            raise ValueError(f"SDK 压缩包校验失败：{archive}")
    with zipfile.ZipFile(archive) as package:
        for item in package.infolist():
            if item.is_dir():
                continue
            original = PurePosixPath(item.filename)
            target = SOURCE.joinpath(*original.parts[1:]).resolve()
            if not target.is_relative_to(SOURCE):
                raise ValueError(f"SDK 文件路径越界：{original}")
            data = package.read(item)
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                link = PurePosixPath(data.decode("utf-8"))
                if link.is_absolute() or ".." in link.parts:
                    raise ValueError(f"SDK 链接路径越界：{link}")
                linked = package.getinfo(str(original.parent / link))
                if (linked.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError(f"SDK 链接指向另一链接：{linked.filename}")
                data = package.read(linked)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def build():
    BUILD.mkdir(parents=True, exist_ok=True)
    ready = RUNTIME / ".road-edges-ready"
    ready.unlink(missing_ok=True)
    apply = ["git", "apply", "--directory=" + SOURCE.relative_to(ROOT).as_posix(), str(PATCH)]
    already_patched = SOURCE.exists() and subprocess.run(
        [*apply, "--reverse", "--check"], cwd=ROOT, capture_output=True, check=False).returncode == 0
    if not already_patched:
        for package in PACKAGES:
            unpack(*package)
        for line in PATCH.read_text(encoding="utf-8").splitlines():
            if line.startswith("+++ b/"):
                path = SOURCE / line.removeprefix("+++ b/")
                path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
        subprocess.run(apply, cwd=ROOT, check=True)
    features = ("python", "direct", "gl", "bullet", "zlib", "png", "jpeg", "freetype", "harfbuzz",
                "egg", "squish", "openal", "vorbis", "opus")
    with (BUILD / "build-runtime.log").open("wb") as log:
        print(f"构建记录：{log.name}", flush=True)
        subprocess.run([sys.executable, "makepanda/makepanda.py", "--nothing",
                        *("--use-" + name for name in features), "--no-copy-python", "--no-eigen",
                        "--msvc-version=14.3", "--windows-sdk=10", "--threads=6", "--optimize=4",
                        "--outputdir=" + RUNTIME.name], cwd=SOURCE, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    check_runtime = (
        "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
        "from panda3d import bullet, core; "
        "assert Path(bullet.__file__).is_relative_to(sys.argv[1]); "
        "assert bullet.getBulletVersion() == 284 and core.LPoint3 is core.LPoint3f; "
        "assert bullet.BulletTriangleMeshShape.enable_internal_edge_adjustment"
    )
    subprocess.run([sys.executable, "-c", check_runtime, str(RUNTIME)], check=True)
    ready.write_text(hashlib.sha256(PATCH.read_bytes()).hexdigest() + "\n", encoding="ascii")


def export_wheel(output):
    expected = hashlib.sha256(PATCH.read_bytes()).hexdigest()
    ready = RUNTIME / ".road-edges-ready"
    if not ready.is_file() or ready.read_text(encoding="ascii").strip() != expected:
        raise RuntimeError("请先完成当前补丁的本地运行库构建")
    if shutil.which("dumpbin") is None:
        raise RuntimeError("导出运行库需要 Visual Studio x64 开发命令环境（dumpbin）")
    output.mkdir(parents=True, exist_ok=True)
    version = "1.10.16+coastaldrive"
    name = f"panda3d-{version}-cp314-cp314-win_amd64.whl"
    target = output / name
    if target.exists():
        raise FileExistsError(target)
    # 上游导出器在当前目录写包，并从 Python 安装目录取部署 DLL。
    command = (
        "import sys,sysconfig; sysconfig.get_config_vars()['BINDIR']=sys.base_prefix; "
        "sys.path.insert(0,'makepanda'); from makewheel import makewheel; "
        "makewheel(sys.argv[1], sys.argv[2], 'win_amd64')"
    )
    subprocess.run([sys.executable, "-c", command, version, RUNTIME.name], cwd=SOURCE, check=True)
    shutil.move(SOURCE / name, target)
    print(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-output", type=Path, help="从已构建运行库导出冻结包所需的 wheel")
    args = parser.parse_args()
    if args.wheel_output is None:
        build()
    else:
        export_wheel(args.wheel_output.resolve())
