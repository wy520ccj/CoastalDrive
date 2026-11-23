"""从当前源码构建Windows试玩包、安装器、免安装包与输入哈希记录。"""

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

from release_assets import prepare_assets

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.9.0-dev.20261017.1"
NATIVE = ("physics_packet_kernels", "mechanical_kernels", "wheel_contact_kernels",
          "convex_cast_kernels", "radial_contact_kernels")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def native_gameplay_digest(path):
    # Windows x64 扩展的 COFF 和调试目录时间戳只记录构建时刻。
    data = bytearray(path.read_bytes())
    pe, = struct.unpack_from("<I", data, 0x3c)
    optional = pe + 24
    if data[pe:pe+4] != b"PE\0\0" or struct.unpack_from("<H", data, optional)[0] != 0x20b:
        raise ValueError(f"原生扩展不是 Windows x64 PE：{path}")
    sections, = struct.unpack_from("<H", data, pe+6)
    optional_size, = struct.unpack_from("<H", data, pe+20)
    struct.pack_into("<I", data, pe+8, 0)
    debug_rva, debug_size = struct.unpack_from("<II", data, optional+160)
    if debug_size:
        section_table = optional + optional_size
        for index in range(sections):
            rva, size, offset = struct.unpack_from("<III", data, section_table+index*40+12)
            if rva <= debug_rva and debug_rva+debug_size <= rva+size:
                first = offset+debug_rva-rva
                if debug_size % 28 or first+debug_size > len(data):
                    raise ValueError(f"原生扩展调试目录无效：{path}")
                for entry in range(first, first+debug_size, 28):
                    struct.pack_into("<I", data, entry+4, 0)
                break
        else:
            raise ValueError(f"原生扩展调试目录不在文件内：{path}")
    return hashlib.sha256(data).hexdigest()


def packaged_record_source(context, package):
    sys.path.insert(0, str(ROOT / "src"))
    from lap_ghost import gameplay_source_paths, packaged_source_paths, source_digest

    source = gameplay_source_paths(context)
    source.add(context / "src/road_test_driver.py")
    physical = source_digest(context, [path for path in source if path.suffix != ".pyd"])
    package_paths = packaged_source_paths(package)
    libraries = {path.name: native_gameplay_digest(path) if path.stem in NATIVE else sha(path)
                 for path in package_paths if path.suffix == ".pyd"}
    stable = hashlib.sha256(json.dumps([physical, libraries], sort_keys=True).encode()).hexdigest()
    return {"package": source_digest(package, package_paths), "gameplay": stable}


def inputs():
    paths = [ROOT / name for name in ("setup.py", "pyproject.toml", "requirements.txt")]
    for folder in ("src", "assets/game", "packaging", "licenses", "tools", "vendor"):
        paths.extend(path for path in (ROOT / folder).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts
                     and path.suffix not in (".pyd", ".pyc"))
    return {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(paths)}


def build(output, iscc, ffmpeg, *, road_edge_wheel=None, local_preview=False):
    if Path(sys.executable).resolve() != (ROOT / ".venv/Scripts/python.exe").resolve():
        raise RuntimeError("请使用项目.venv/Scripts/python.exe")
    output.mkdir(parents=True, exist_ok=False)
    before = inputs()
    version = VERSION + "+local-preview" if local_preview else VERSION
    receipt = {"version": version, "head": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "worktree": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
        "inputs": before, "status": "building"}
    receipt_path = output / "build-receipt.json"
    if road_edge_wheel is not None:
        receipt["runtime_wheel"] = {"name": road_edge_wheel.name, "sha256": sha(road_edge_wheel)}
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    context = output / "source"
    context.mkdir()
    for folder in ("src", "tools", "licenses", "packaging", "vendor", "assets/game"):
        shutil.copytree(ROOT / folder, context / folder,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyd"))
    for name in ("setup.py", "pyproject.toml", "requirements.txt"):
        shutil.copy2(ROOT / name, context / name)

    def run(name, command):
        print(name, flush=True)
        with (output / f"{name}.log").open("wb") as log:
            try:
                subprocess.run(command, cwd=context, stdout=log, stderr=subprocess.STDOUT, check=True)
            except subprocess.CalledProcessError:
                receipt.update(status="failed", stage=name)
                receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
                raise

    run("native", [sys.executable, "setup.py", "build_ext", "--build-lib", str(context / "src"),
                   "--build-temp", str(output / "native-temp")])
    freeze = [sys.executable, "setup.py", "build_apps", "--build-base", str(output / "app")]
    runtime = {}
    if road_edge_wheel is not None:
        requirements = context / "requirements.txt"
        lines = requirements.read_text(encoding="utf-8").splitlines()
        requirements.write_text("\n".join(
            "panda3d @ " + road_edge_wheel.as_uri() if line.startswith("panda3d==") else line
            for line in lines
        ) + "\n", encoding="utf-8")
        freeze += ["--requirements-path", str(requirements)]
        with ZipFile(road_edge_wheel) as wheel:
            bullet, = (name for name in wheel.namelist() if name.startswith("panda3d/bullet.") and name.endswith(".pyd"))
            for target, source in (("panda3d.bullet.pyd", bullet), ("libpandabullet.dll", "panda3d/libpandabullet.dll")):
                with wheel.open(source) as stream:
                    runtime[target] = hashlib.file_digest(stream, "sha256").hexdigest()
    run("freeze", freeze)
    package = output / "app/win_amd64"
    for name, digest in runtime.items():
        if sha(package / name) != digest:
            raise RuntimeError(f"冻结包未使用指定的路面运行库：{name}")
    if road_edge_wheel is not None and sha(road_edge_wheel) != receipt["runtime_wheel"]["sha256"]:
        raise RuntimeError("路面运行库在打包期间发生变化")
    native = {}
    for module in NATIVE:
        source, = (context / "src").glob(module + ".*.pyd")
        target = package / (module + ".pyd")
        if sha(source) != sha(target):
            raise RuntimeError(f"冻结包原生扩展与当前源码编译结果不一致：{module}")
        native[module] = sha(target)
    for source in (ROOT / "assets/game").rglob("*"):
        if source.is_file() and source.name != ".gitkeep":
            target = package / source.relative_to(ROOT)
            if not target.is_file() or sha(source) != sha(target):
                raise RuntimeError(f"运行资源缺失或哈希不同：{source}")
    resource_changes = prepare_assets(package, str(ffmpeg))
    diagnostics = output / "diagnostics"
    diagnostics.mkdir()
    shutil.move(str(package / "coastaldrive-check.exe"), diagnostics / "coastaldrive-check.exe")
    shutil.copy2(ROOT / "packaging/development-notice.txt", package / "README.txt")
    shutil.copytree(ROOT / "licenses", package / "licenses", dirs_exist_ok=True)
    records = packaged_record_source(context, package)
    receipt["record_source"] = records
    (package / "release.json").write_text(json.dumps(
        {"version": version, "source_head": receipt["head"], "native_sha256": native,
         "runtime_sha256": runtime, "local_preview": local_preview,
         "precision": "standard", "development_preview": True, "record_source": records}, indent=2), encoding="utf-8")
    if local_preview:
        if inputs() != before:
            raise RuntimeError("构建期间源码或素材发生变化，请冻结后重新构建")
        receipt.update(status="built", native_sha256=native, runtime_sha256=runtime,
                       resource_changes=resource_changes, package=str(package))
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        print(package)
        return
    artifacts = output / "artifacts"
    artifacts.mkdir()
    run("installer", [str(iscc), f"/DPackageDir={package}", f"/DReleaseDir={artifacts}",
                      str(context / "packaging/coastaldrive.iss")])
    print("portable", flush=True)
    shutil.make_archive(str(artifacts / f"CoastalDrive-{VERSION}-Windows-x64-Portable"),
                        "zip", root_dir=package.parent, base_dir=package.name)
    files = sorted(artifacts.iterdir())
    (artifacts / "SHA256SUMS.txt").write_text(
        "".join(f"{sha(path)}  {path.name}\n" for path in files), encoding="utf-8")
    if inputs() != before:
        raise RuntimeError("构建期间源码或素材发生变化，请冻结后重新构建")
    receipt.update(status="built", native_sha256=native, runtime_sha256=runtime, resource_changes=resource_changes,
                   installed_bytes=sum(path.stat().st_size for path in package.rglob("*") if path.is_file()),
                   artifacts={path.name: {"sha256": sha(path), "bytes": path.stat().st_size}
                              for path in artifacts.iterdir()})
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(artifacts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iscc", type=Path)
    parser.add_argument("--ffmpeg", type=Path, required=True, help="构建时无损压缩音乐，不随游戏分发")
    parser.add_argument("--road-edge-wheel", type=Path, help="显式使用本地赛道路面修正运行库")
    parser.add_argument("--local-preview", action="store_true", help="只构建本机可运行的游戏目录")
    args = parser.parse_args()
    if args.iscc is None and not args.local_preview:
        parser.error("构建安装包时须提供 --iscc")
    build(args.output.resolve(), None if args.iscc is None else args.iscc.resolve(), args.ffmpeg.resolve(),
          local_preview=args.local_preview,
          road_edge_wheel=None if args.road_edge_wheel is None else args.road_edge_wheel.resolve())
