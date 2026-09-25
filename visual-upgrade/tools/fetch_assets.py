"""下载画面升级所需的 CC0 素材，并把来源、许可与本地路径登记下来。

沙箱里 .NET/schannel 的 HTTPS 不可用，Python 自带 OpenSSL 可以，所以统一走这里。
用法：
    python tools/fetch_assets.py             # 下载清单里缺失的素材
    python tools/fetch_assets.py --check     # 只报告本地状态
    python tools/fetch_assets.py --list      # 打印清单
"""

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "CoastalDrive-asset-fetch/1.0"
FILES_API = "https://api.polyhaven.com/files/{asset}"
MANIFEST_PATH = ROOT / "assets/raw/polyhaven-manifest.json"

# 每个条目：Poly Haven 资产 id、要取的贴图、分辨率、本地用途
MANIFEST = (
    {
        "asset": "cliff_side",
        "maps": {"diff": "Diffuse", "nor_gl": "nor_gl"},
        "resolution": "1k",
        "dest": "assets/game/materials",
        "use": "滨海岩壁与内侧重岩体",
    },
    {
        "asset": "coast_sand_rocks_02",
        "maps": {"diff": "Diffuse"},
        "resolution": "1k",
        "dest": "assets/game/materials",
        "use": "岸边礁石与砂砾",
    },
)


def fetch(url, timeout=180, attempts=4):
    """Poly Haven 的 CDN 偶尔握手超时，这里重试几次再放弃。"""
    last = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:  # noqa: BLE001 - 网络边界，重试后向上抛
            last = exc
            print(f"    第 {attempt} 次失败（{type(exc).__name__}），重试…")
    raise SystemExit(f"下载失败：{url}（{last}）")


def files_for(asset):
    return json.loads(fetch(FILES_API.format(asset=asset), timeout=60).decode("utf-8"))


def resolve(node, *keys):
    """按 files API 的层级取到具体文件的 url 与大小。"""
    current = node
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current if isinstance(current, dict) and "url" in current else None


def download(entry, listing):
    dest_dir = ROOT / entry["dest"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved = {}
    for suffix, map_name in entry["maps"].items():
        maps = listing.get(map_name)
        if maps is None:
            print(f"  跳过 {map_name}：该资产没有这张图")
            continue
        info = resolve(maps, entry["resolution"], "jpg") or resolve(
            maps, entry["resolution"], "png")
        if info is None:
            print(f"  跳过 {map_name}：没有 {entry['resolution']} 的 jpg/png")
            continue
        name = f"{entry['asset']}_{suffix}_{entry['resolution']}.jpg"
        target = dest_dir / name
        if target.exists() and target.stat().st_size == info.get("size", -1):
            print(f"  已存在 {name}")
            saved[suffix] = str(target.relative_to(ROOT))
            continue
        print(f"  下载 {name}（{info.get('size', 0) / 1024:.0f} KB）")
        target.write_bytes(fetch(info["url"]))
        saved[suffix] = str(target.relative_to(ROOT))
        saved[f"{suffix}_url"] = info["url"]
    return saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        for entry in MANIFEST:
            print(f"{entry['asset']}: {entry['use']} -> {entry['dest']}")
        return 0

    if args.check:
        for entry in MANIFEST:
            for suffix in entry["maps"]:
                path = ROOT / entry["dest"] / f"{entry['asset']}_{suffix}_{entry['resolution']}.jpg"
                print(f"{path.relative_to(ROOT)}: {'存在' if path.exists() else '缺失'}")
        return 0

    record = {
        "generated": datetime.now(UTC).date().isoformat(),
        "source": "Poly Haven (CC0)",
        "assets": [],
    }
    for entry in MANIFEST:
        print(f"{entry['asset']}（{entry['use']}）")
        listing = files_for(entry["asset"])
        files = download(entry, listing)
        record["assets"].append({
            "asset": entry["asset"],
            "page": f"https://polyhaven.com/a/{entry['asset']}",
            "license": "CC0",
            "use": entry["use"],
            "files": files,
        })
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(record, indent=2, ensure_ascii=False),
                             encoding="utf-8")
    print(f"登记写入：{MANIFEST_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
