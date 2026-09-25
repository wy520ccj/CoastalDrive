"""下载并安装界面用的像素中文字体（Ark Pixel Font，SIL OFL 1.1）。

沙箱里 .NET/schannel 的 HTTPS 不可用，但 Python 自带 OpenSSL 可以下载，
所以字体获取统一走这个脚本，来源与许可一并落盘，便于复核。

用法：
    python tools/fetch_font.py            # 安装 12px 比例字形
    python tools/fetch_font.py --check    # 只检查已安装情况
"""

import argparse
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets/game/ui/fonts"
RELEASE_API = "https://api.github.com/repos/TakWolf/ark-pixel-font/releases/latest"
WANTED = "ark-pixel-font-12px-proportional-ttf-"
INSTALLED = "ark-pixel-12px-proportional-zh_cn.ttf"
LICENSE_URL = "https://raw.githubusercontent.com/TakWolf/ark-pixel-font/master/LICENSE-OFL"


def fetch(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def find_asset(release):
    for asset in release["assets"]:
        if asset["name"].startswith(WANTED) and asset["name"].endswith(".zip"):
            return asset
    raise SystemExit(f"没有找到匹配 {WANTED} 的发布资产")


def install(release, asset):
    print(f"下载 {asset['name']}（{asset['size'] / 1024:.0f} KB）")
    archive = zipfile.ZipFile(io.BytesIO(fetch(asset["browser_download_url"])))
    members = [name for name in archive.namelist() if name.endswith(".ttf")
               and "zh_cn" in name]
    if not members:
        raise SystemExit("压缩包里没有 zh_cn 的 ttf")
    DEST.mkdir(parents=True, exist_ok=True)
    with archive.open(members[0]) as source:
        (DEST / INSTALLED).write_bytes(source.read())
    (DEST / "ark-pixel-LICENSE-OFL.txt").write_text(
        f"Ark Pixel Font\n来源：https://github.com/TakWolf/ark-pixel-font\n"
        f"版本：{release['tag_name']}\n资产：{asset['name']}\n"
        f"成员：{members[0]}\n许可：SIL Open Font License 1.1\n\n",
        encoding="utf-8",
    )
    (DEST / "ark-pixel-LICENSE-OFL.txt").open("a", encoding="utf-8").write(
        fetch(LICENSE_URL).decode("utf-8", "replace")
    )
    print(f"已安装：{DEST / INSTALLED}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        target = DEST / INSTALLED
        print(f"{target}: {'存在' if target.exists() else '缺失'}")
        return 0
    release = json.loads(fetch(RELEASE_API))
    install(release, find_asset(release))
    return 0


if __name__ == "__main__":
    sys.exit(main())
