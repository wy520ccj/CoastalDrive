"""从当前源码构建Windows试玩包、安装器、免安装包与输入哈希记录。"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.9.0-dev.20261017"
NATIVE = ("physics_packet_kernels", "mechanical_kernels", "wheel_contact_kernels",
          "convex_cast_kernels", "radial_contact_kernels")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inputs():
    paths = [ROOT / name for name in ("setup.py", "pyproject.toml", "requirements.txt")]
    for folder in ("src", "assets/game", "packaging", "licenses", "tools", "vendor"):
        paths.extend(path for path in (ROOT / folder).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts
                     and path.suffix not in (".pyd", ".pyc"))
    return {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(paths)}


def build(output, iscc):
    if Path(sys.executable).resolve() != (ROOT / ".venv/Scripts/python.exe").resolve():
        raise RuntimeError("请使用项目.venv/Scripts/python.exe")
    output.mkdir(parents=True, exist_ok=False)
    before = inputs()
    receipt = {"version": VERSION, "head": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "worktree": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
        "inputs": before, "status": "building"}
    receipt_path = output / "build-receipt.json"
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
            subprocess.run(command, cwd=context, stdout=log, stderr=subprocess.STDOUT, check=True)

    run("native", [sys.executable, "setup.py", "build_ext", "--build-lib", str(context / "src"),
                   "--build-temp", str(output / "native-temp")])
    run("freeze", [sys.executable, "setup.py", "build_apps", "--build-base", str(output / "app")])
    package = output / "app/win_amd64"
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
    shutil.copy2(ROOT / "packaging/development-notice.txt", package / "README.txt")
    shutil.copytree(ROOT / "licenses", package / "licenses", dirs_exist_ok=True)
    (package / "release.json").write_text(json.dumps(
        {"version": VERSION, "source_head": receipt["head"], "native_sha256": native,
         "precision": "standard", "development_preview": True}, indent=2), encoding="utf-8")
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
    receipt.update(status="built", native_sha256=native,
                   artifacts={path.name: {"sha256": sha(path), "bytes": path.stat().st_size}
                              for path in artifacts.iterdir()})
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(artifacts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iscc", type=Path, required=True)
    args = parser.parse_args()
    build(args.output.resolve(), args.iscc.resolve())
