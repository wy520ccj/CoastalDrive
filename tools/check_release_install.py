"""隔离安装、实际运行、覆盖升级及卸载，记录Windows快捷方式和注册项。"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import winreg
from pathlib import Path

UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{C53A2791-24D5-4BB5-8351-D2D683E3C8E8}_is1"


def registry():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except FileNotFoundError:
        return None
    with key:
        return {name: winreg.QueryValueEx(key, name)[0]
                for name in ("DisplayName", "DisplayVersion", "InstallLocation", "UninstallString")}


def check(installer, output, *, lifecycle_only=False, checker=None, previous=None, package=None):
    output.mkdir(parents=True, exist_ok=False)
    if registry() is not None:
        raise RuntimeError("已有同AppId安装；为保护用户安装，停止测试")
    install_dir = output / "中文路径 空格/CoastalDrive"
    shortcuts = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/CoastalDrive"
    if shortcuts.exists():
        raise RuntimeError("开始菜单已有CoastalDrive目录；停止覆盖")
    probe = Path(os.environ["LOCALAPPDATA"]) / "CoastalDrive/release-uninstall-preservation-probe.txt"
    if probe.exists():
        raise RuntimeError("卸载数据探针已存在；停止覆盖")
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_text("release-uninstall-data-must-survive", encoding="utf-8")
    probe_sha = hashlib.sha256(probe.read_bytes()).hexdigest()
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["LOCALAPPDATA"] = str(output / "isolated-user")
    report = {"passed": False, "installer": str(installer), "install_dir": str(install_dir), "checks": {}}

    def run(name, command, timeout=180):
        with (output / f"{name}.log").open("wb") as log:
            result = subprocess.run(command, cwd=output, env=environment, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        report["checks"][name] = {"returncode": result.returncode}
        if result.returncode:
            raise RuntimeError(f"{name}失败：{result.returncode}；见{output / (name + '.log')}")

    install_args = [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                    "/LANG=chinesesimp", f"/DIR={install_dir}"]
    try:
        if previous is not None:
            run("previous-install", [str(previous), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                                      f"/DIR={install_dir}"])
            report["previous_version"] = registry()["DisplayVersion"]
        run("install", install_args + [f"/LOG={output / 'install-inno.log'}"])
        report["registry_after_install"] = registry()
        assert report["registry_after_install"] is not None
        expected = ("CoastalDrive (开发试玩版).lnk", "车辆实验台.lnk", "下载与使用说明.lnk", "卸载 CoastalDrive.lnk")
        assert all((shortcuts / name).is_file() for name in expected)
        report["shortcuts"] = list(expected)
        if package is not None:
            expected_files = {f.relative_to(package).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
                              for f in package.rglob("*") if f.is_file()}
            actual_files = {f.relative_to(install_dir).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
                            for f in install_dir.rglob("*") if f.is_file() and not f.name.startswith("unins000.")}
            assert actual_files == expected_files, "安装文件与发行输入不同，或存在旧版残留"
            report["all_installed_files_equal"] = len(actual_files)
        executable = install_dir / "coastaldrive.exe"
        if lifecycle_only:
            report["runtime_checks"] = "not_run; reuse separately recorded results for identical installer SHA256"
        else:
            for seed in (0, 17, 23):
                run(f"headless-{seed}", [str(executable), "--headless", "--track", "test",
                                         "--steps", "1200", "--seed", str(seed)])
            smoke = output / "smoke"
            run("smoke", [str(executable), "--smoke", "--output", str(smoke)])
            assert json.loads((smoke / "h0-render-smoke.json").read_text(encoding="utf-8"))["passed"]
            diagnostic = install_dir / "coastaldrive-check.exe"
            if checker is not None:
                if diagnostic.exists():
                    raise FileExistsError(diagnostic)
                shutil.copy2(checker, diagnostic)
                report["external_diagnostic_sha256"] = hashlib.sha256(checker.read_bytes()).hexdigest()
            try:
                run("workspace", [str(diagnostic), "--output", str(output / "workspace")], 420)
            finally:
                if checker is not None:
                    diagnostic.unlink()
            assert json.loads((output / "workspace/report.json").read_text(encoding="utf-8"))["passed"]
        run("upgrade", install_args + [f"/LOG={output / 'upgrade-inno.log'}"])
        assert executable.is_file() and registry() is not None
        run("uninstall", [str(install_dir / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                          "/NORESTART", f"/LOG={output / 'uninstall-inno.log'}"])
        # Inno父进程可早于临时卸载进程返回；等待实际文件清理完成再验收。
        deadline = time.monotonic() + 15
        while install_dir.exists() and time.monotonic() < deadline:
            time.sleep(.1)
        assert not executable.exists() and registry() is None and not shortcuts.exists()
        assert not list(install_dir.rglob("*")), "卸载后安装目录仍有文件"
        assert hashlib.sha256(probe.read_bytes()).hexdigest() == probe_sha
        report.update(passed=True, user_data_preserved=True, program_removed=True,
                      registry_removed=True, shortcuts_removed=True)
    finally:
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        probe.unlink()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lifecycle-only", action="store_true", help="只复测安装升级卸载，运行证据另行引用")
    parser.add_argument("--checker", type=Path, help="不随玩家包分发的冻结诊断程序，仅测试时临时放入安装目录")
    parser.add_argument("--previous", type=Path, help="先安装上一版，再验证升级后的资源清理")
    parser.add_argument("--package", type=Path, help="发行文件目录；逐文件核对安装结果并拒绝旧版残留")
    args = parser.parse_args()
    check(args.installer.resolve(), args.output.resolve(), lifecycle_only=args.lifecycle_only,
          checker=args.checker.resolve() if args.checker else None,
          previous=args.previous.resolve() if args.previous else None,
          package=args.package.resolve() if args.package else None)
