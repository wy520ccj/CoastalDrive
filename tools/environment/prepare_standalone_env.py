"""离线烘焙独立、自然、风格统一的地中海/太平洋海岸写实植被、石灰岩巨石、三层草甸与晴空资产。

核心美术原则：
- 5 种真正异形的海岸树种（阔冠橡树、高拱榆栎、地中海伞松、多干海岸橄榄栎、海风金梢橡），
  树叶采用球壳法线平滑（Spherical Normal Transfer）+ 深层内膛 AO（编码于 v_color.a ∈ [0.45,1.0]）
  + 逐顶植物色相渐变（v_color.rgb），彻底消除纸片杂点与单一树种复制感；
- 5 种闭合雕塑感海岸石灰岩巨石（无镂空黑洞），带暖色岩层纹理与顶面青苔过渡；
- 8 种自然弧弯多叶草簇 + 极克制的海岸野花点缀，配合顶点风浪摇曳与地表无缝混色；
- 全部素材源自仓库开放许可（MIT EZ-Tree + CC0 Poly Haven / ambientCG）与原创程序几何。
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import shutil
from pathlib import Path

import gltf
import numpy as np
from panda3d.core import (
    Filename,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    NodePath,
)
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
EXPRESSWAY = ROOT / "assets/game/expressway"
TERRAIN_OUT = EXPRESSWAY / "terrain"
FOLIAGE_OUT = EXPRESSWAY / "standalone-foliage"
TEX_OUT = FOLIAGE_OUT / "textures"

V3N3C4T2_DTYPE = np.dtype([("p", "<f4", 3), ("n", "<f4", 3), ("c", "u1", 4), ("uv", "<f4", 2)])


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def dilate_rgb_by_alpha(rgba: np.ndarray, iterations: int = 20) -> np.ndarray:
    """将不透明像素 RGB 外扩至透明背景，彻底消除 Mipmap 与 A2C 边缘泛白/泛黑。"""
    rgb = rgba[:, :, :3].astype(np.float32).copy()
    alpha = rgba[:, :, 3]
    valid = alpha > 20
    if np.all(valid) or not np.any(valid):
        return rgba
    for _ in range(iterations):
        if np.all(valid):
            break
        acc = np.zeros_like(rgb)
        cnt = np.zeros(valid.shape, dtype=np.float32)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            s_val = np.roll(np.roll(valid, dy, axis=0), dx, axis=1)
            s_rgb = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
            mask = s_val & (~valid)
            acc[mask] += s_rgb[mask]
            cnt[mask] += 1.0
        grow = cnt > 0
        if not np.any(grow):
            break
        rgb[grow] = acc[grow] / cnt[grow, None]
        valid[grow] = True
    if not np.all(valid):
        rgb[~valid] = rgb[valid].mean(axis=0)
    out = rgba.copy()
    out[:, :, :3] = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
    return out


def make_geom_node(
    name: str,
    points: np.ndarray,
    normals: np.ndarray,
    colors: np.ndarray,
    uv: np.ndarray,
    indices: np.ndarray,
) -> NodePath:
    """构造紧凑的 V3n3c4t2 索引三角 GeomNode（uint32 索引）。"""
    packed = np.empty(len(points), dtype=V3N3C4T2_DTYPE)
    packed["p"] = points.astype(np.float32)
    n_len = np.linalg.norm(normals, axis=1, keepdims=True)
    safe = np.where(n_len > 1e-8, n_len, 1.0)
    packed["n"] = (normals / safe).astype(np.float32)
    packed["c"] = np.clip(np.rint(colors * 255.0), 0, 255).astype(np.uint8)
    packed["uv"] = uv.astype(np.float32)

    vdata = GeomVertexData(name, GeomVertexFormat.getV3n3c4t2(), Geom.UHStatic)
    vdata.setNumRows(len(packed))
    vdata.modifyArray(0).modifyHandle().setData(packed.tobytes())

    prim = GeomTriangles(Geom.UHStatic)
    prim.setIndexType(Geom.NTUint32)
    prim.modifyVertices().modifyHandle().setData(np.ascontiguousarray(indices, dtype="<u4").tobytes())

    geom = Geom(vdata)
    geom.addPrimitive(prim)
    gnode = GeomNode(name)
    gnode.addGeom(geom)
    return NodePath(gnode)


def _normal_from_luma(img_rgb: np.ndarray, strength: float = 2.0) -> Image.Image:
    luma = (0.299 * img_rgb[:, :, 0] + 0.587 * img_rgb[:, :, 1] + 0.114 * img_rgb[:, :, 2]).astype(np.float32) / 255.0
    gx = (np.roll(luma, -1, axis=1) - np.roll(luma, 1, axis=1)) * strength
    gy = (np.roll(luma, -1, axis=0) - np.roll(luma, 1, axis=0)) * strength
    nx, ny, nz = -gx, gy, np.ones_like(gx)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    nor = np.stack((nx * inv * 0.5 + 0.5, ny * inv * 0.5 + 0.5, nz * inv * 0.5 + 0.5), axis=-1)
    return Image.fromarray(np.clip(np.rint(nor * 255.0), 0, 255).astype(np.uint8), mode="RGB")


def _height_from_luma(rgb_u8: np.ndarray, size: int = 512) -> Image.Image:
    luma = (0.299 * rgb_u8[:, :, 0] + 0.587 * rgb_u8[:, :, 1] + 0.114 * rgb_u8[:, :, 2]).astype(np.float32)
    lo, hi = np.percentile(luma, 5), np.percentile(luma, 95)
    norm = np.clip((luma - lo) / max(hi - lo, 1.0), 0.0, 1.0)
    im = Image.fromarray(np.clip(np.rint(norm * 255.0), 0, 255).astype(np.uint8), mode="L")
    return im.resize((size, size), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=0.8))


def _tileable_lowfreq_field(size: int, seed: int, harmonics: int = 4) -> np.ndarray:
    rng = random.Random(seed)
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) * (math.tau / size)
    field = np.zeros((size, size), dtype=np.float32)
    total_w = 0.0
    for k in range(1, harmonics + 1):
        w = 1.0 / k
        for _ in range(2):
            fx = rng.choice((-k, k))
            fy = rng.choice((-k, 0, k))
            ph = rng.uniform(0.0, math.tau)
            field += w * np.sin(fx * x + fy * y + ph)
            total_w += w
    return field / max(total_w, 1.0)


def _extract_panda_tex_fast(tex) -> Image.Image:
    tmp = FOLIAGE_OUT / "_tmp_tex.png"
    tex.write(Filename.fromOsSpecific(str(tmp)))
    im = Image.open(tmp).copy()
    tmp.unlink(missing_ok=True)
    return im


def promote_daylight_sky():
    """沿用 CC0 kloofendal_48d_partly_cloudy_puresky 晴空与离线环境立方体。"""
    src_dir = ROOT / "logs/visual-upgrade-20261024/daylight-29"
    if (src_dir / "daylight-manifest.json").is_file():
        for name in ("daylight-sky.hdr", "daylight.env"):
            shutil.copy2(src_dir / name, EXPRESSWAY / name)
        manifest = json.loads((src_dir / "daylight-manifest.json").read_text(encoding="utf-8"))
        manifest["source"]["status"] = "production standalone default"
        (EXPRESSWAY / "daylight-manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    license_text = (
        "CoastalDrive Expressway Daylight Sky\n"
        "Source: https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky\n"
        "File: kloofendal_48d_partly_cloudy_puresky_4k.hdr\n"
        "Authors: Greg Zaal (Original), Jarod Guest (Sky edits)\n"
        "License: CC0-1.0 (https://creativecommons.org/publicdomain/zero/1.0/)\n"
    )
    (EXPRESSWAY / "License-Daylight.txt").write_text(license_text, encoding="utf-8")
    return {
        "sky_sha256": sha256_file(EXPRESSWAY / "daylight-sky.hdr"),
        "env_sha256": sha256_file(EXPRESSWAY / "daylight.env"),
    }


def build_terrain_textures():
    """烘焙饱满温暖的地中海海岸三层地表 PBR（鲜草甸、阳光暖枯草、林下腐殖苔藓）。"""
    TERRAIN_OUT.mkdir(parents=True, exist_ok=True)
    mats = ROOT / "assets/game/materials"
    leafy_diff = np.asarray(
        Image.open(mats / "leafy_grass_diff_2k.jpg").convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS),
        dtype=np.float32,
    ) / 255.0
    leafy_nor = Image.open(mats / "leafy_grass_nor_gl_2k.jpg").convert("RGB").resize(
        (1024, 1024), Image.Resampling.LANCZOS
    )
    leafy_rough = np.asarray(
        Image.open(mats / "leafy_grass_rough_2k.jpg").convert("L").resize((1024, 1024), Image.Resampling.LANCZOS),
        dtype=np.float32,
    ) / 255.0
    grass_ground = np.asarray(
        Image.open(mats / "grass_ground_diff_2k.jpg").convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS),
        dtype=np.float32,
    ) / 255.0

    lin_leafy = np.power(np.clip(leafy_diff, 1e-4, 1.0), 2.2)
    lin_gg = np.power(np.clip(grass_ground, 1e-4, 1.0), 2.2)

    # 1) Pasture：自然耐看的地中海青翠草甸（克制黄绿饱和度，阳光下绝不刺眼发荧光）
    pasture_lin = lin_leafy * 0.45 + lin_gg * 0.55
    pasture_lin *= np.array([0.36, 0.56, 0.22], dtype=np.float32)
    macro_p = 1.0 + 0.24 * _tileable_lowfreq_field(1024, seed=101, harmonics=3)
    pasture_lin = np.clip(pasture_lin * macro_p[:, :, None], 0.002, 0.95)
    pasture_lin *= 0.062 / max(float(pasture_lin[:, :, 1].mean()), 1e-4)
    pasture_srgb = np.clip(np.rint(np.power(np.clip(pasture_lin, 0.0, 1.0), 1.0 / 2.2) * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(pasture_srgb, mode="RGB").save(TERRAIN_OUT / "pasture-albedo.png", optimize=True)
    leafy_nor.save(TERRAIN_OUT / "pasture-normal.png", optimize=True)
    pasture_gloss = np.clip(np.rint((1.0 - np.clip(leafy_rough, 0.74, 0.98)) * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(pasture_gloss, mode="L").save(TERRAIN_OUT / "pasture-gloss.png", optimize=True)
    _height_from_luma(pasture_srgb, 512).save(TERRAIN_OUT / "pasture-height.png", optimize=True)

    # 2) Dry：自然向阳暖麦穗/枯草斑块（低饱和自然暖草色）
    dry_base = np.roll(np.roll(lin_leafy, 384, axis=0), 512, axis=1)
    dry_gg = np.roll(np.roll(lin_gg, 256, axis=0), 640, axis=1)
    dry_lin = (dry_base * 0.62 + dry_gg * 0.38) * np.array([0.66, 0.68, 0.34], dtype=np.float32)
    macro_d = 1.0 + 0.28 * _tileable_lowfreq_field(1024, seed=202, harmonics=3)
    dry_lin = np.clip(dry_lin * macro_d[:, :, None], 0.004, 0.95)
    dry_lin *= 0.150 / max(float(dry_lin[:, :, 1].mean()), 1e-4)
    dry_srgb = np.clip(np.rint(np.power(np.clip(dry_lin, 0.0, 1.0), 1.0 / 2.2) * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(dry_srgb, mode="RGB").save(TERRAIN_OUT / "dry-albedo.png", optimize=True)
    Image.fromarray(np.roll(np.roll(np.asarray(leafy_nor), 384, axis=0), 512, axis=1), mode="RGB").save(
        TERRAIN_OUT / "dry-normal.png", optimize=True
    )
    dry_gloss = np.clip(np.rint((1.0 - np.clip(np.roll(leafy_rough, 384, axis=0), 0.78, 0.99)) * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(dry_gloss, mode="L").save(TERRAIN_OUT / "dry-gloss.png", optimize=True)
    _height_from_luma(dry_srgb, 512).save(TERRAIN_OUT / "dry-height.png", optimize=True)

    # 3) Forest：树冠下深邃落叶腐殖土与阴生青苔
    litter_a = np.roll(np.roll(lin_leafy, 512, axis=0), 256, axis=1) * np.array([0.48, 0.36, 0.16], dtype=np.float32)
    litter_b = np.rot90(np.roll(lin_gg, 320, axis=0), 1) * np.array([0.36, 0.34, 0.14], dtype=np.float32)
    moss_mask = np.clip(0.5 + 0.5 * _tileable_lowfreq_field(1024, seed=303, harmonics=4), 0.0, 1.0)
    forest_lin = litter_a * 0.50 + litter_b * 0.50
    forest_lin = forest_lin * (1.0 - 0.42 * moss_mask[:, :, None]) + (
        pasture_lin * np.array([0.55, 0.92, 0.42], dtype=np.float32) * 0.42 * moss_mask[:, :, None]
    )
    forest_lin *= 0.062 / max(float(forest_lin.mean()), 1e-4)
    forest_srgb = np.clip(np.rint(np.power(np.clip(forest_lin, 0.0, 1.0), 1.0 / 2.2) * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(forest_srgb, mode="RGB").save(TERRAIN_OUT / "forest-albedo.png", optimize=True)
    Image.fromarray(np.roll(np.roll(np.asarray(leafy_nor), 512, axis=0), 256, axis=1), mode="RGB").save(
        TERRAIN_OUT / "forest-normal.png", optimize=True
    )
    forest_gloss = np.clip(np.rint((1.0 - np.clip(np.roll(leafy_rough, 512, axis=0), 0.78, 0.99)) * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(forest_gloss, mode="L").save(TERRAIN_OUT / "forest-gloss.png", optimize=True)
    _height_from_luma(forest_srgb, 512).save(TERRAIN_OUT / "forest-height.png", optimize=True)

    return {
        "pasture_lin_mean": [round(float(v), 4) for v in pasture_lin.mean(axis=(0, 1))],
        "dry_lin_mean": [round(float(v), 4) for v in dry_lin.mean(axis=(0, 1))],
        "forest_lin_mean": [round(float(v), 4) for v in forest_lin.mean(axis=(0, 1))],
    }


def _compose_dense_leaf_cluster(single_twig: Image.Image) -> Image.Image:
    """将单支实拍橡叶多角度丰满叠合成圆形浓密叶簇，让树冠在远近都饱满自然无碎孔。"""
    # 先清理原图里极亮发白叶背反光
    arr = np.asarray(single_twig.convert("RGBA"), dtype=np.uint8)
    rgb = np.power(np.clip(arr[:, :, :3].astype(np.float32) / 255.0, 1e-4, 1.0), 2.2)
    luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    pale = np.clip((luma - 0.14) / 0.20, 0.0, 1.0) * np.clip(1.0 - (rgb[:, :, 1] - rgb[:, :, 0]) / 0.09, 0.0, 1.0)
    rich_green = np.array([0.08, 0.16, 0.03], dtype=np.float32)
    rgb = rgb * (1.0 - 0.85 * pale[:, :, None]) + rich_green * (0.85 * pale[:, :, None])
    # 转为中性偏亮绿基准（最终色相与深浅由逐树种 v_color.rgb 控制，发挥单材质合批优势）
    rgb = np.clip(rgb * np.array([0.78, 0.95, 0.62], dtype=np.float32), 0.0, 0.42)
    cleaned_srgb = np.clip(np.rint(np.power(rgb, 1.0 / 2.2) * 255.0), 0, 255).astype(np.uint8)
    twig = Image.fromarray(np.dstack((cleaned_srgb, arr[:, :, 3])), mode="RGBA")

    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    # 围绕中心叠加 5 支清晰分明、带自然通透叶隙的实拍橡叶枝，保留外缘锯齿叶轮廓不发糊
    placements = (
        (-58, 0.68, (-135, 30), 0.84),
        (54, 0.68, (135, 25), 0.84),
        (-138, 0.64, (-95, -125), 0.80),
        (132, 0.64, (105, -120), 0.80),
        (8, 0.74, (0, 55), 1.00),
    )
    for angle, scale, (dx, dy), shade in placements:
        sz = int(1024 * scale)
        layer = twig.resize((sz, sz), Image.Resampling.LANCZOS).rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        if shade < 0.99:
            l_arr = np.asarray(layer, dtype=np.float32)
            l_arr[:, :, :3] *= shade
            layer = Image.fromarray(np.clip(np.rint(l_arr), 0, 255).astype(np.uint8), mode="RGBA")
        px = 512 - layer.width // 2 + dx
        py = 512 - layer.height // 2 + dy
        canvas.alpha_composite(layer, (px, py))

    # 软圆边缘微修剪，保证轮廓绝不贴画布四边产生矩形切痕
    yy, xx = np.mgrid[0:1024, 0:1024].astype(np.float32)
    rad = np.hypot((xx - 512.0) / 485.0, (yy - 512.0) / 485.0)
    edge_fade = np.clip((1.0 - rad) / 0.12, 0.0, 1.0)
    out = np.asarray(canvas, dtype=np.uint8).copy()
    out[:, :, 3] = np.clip(np.rint(out[:, :, 3].astype(np.float32) * edge_fade), 0, 255).astype(np.uint8)
    out = dilate_rgb_by_alpha(out, iterations=24)
    return Image.fromarray(out, mode="RGBA")


def _make_blade_grass_texture() -> tuple[Image.Image, Image.Image, Image.Image, Image.Image]:
    """绘制丝滑细腻的 1024×1024 草叶与微花贴图（上半柔顺草叶，右下角含少量海岸野花），无锯齿噪点。"""
    # 左侧 0..0.75: 柔和自然草叶纹理（含根部深阴影、纵叶脉、阳光金绿梢）；右侧 0.75..1.0: 海岸小野花头
    w, h = 512, 512
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = xx / float(w)
    v = 1.0 - yy / float(h)  # v=0 根部, v=1 梢部

    # 草叶纵脉细纹
    veins = 0.92 + 0.08 * np.sin(u * math.tau * 24.0) + 0.04 * np.sin(u * math.tau * 62.0 + v * 4.0)
    # 根部沉稳深青绿 -> 中段自然柔和草绿 -> 梢部微暖麦绿（克制高饱和荧光绿）
    r = (0.12 + 0.17 * (v ** 1.35)) * veins
    g = (0.22 + 0.23 * (v ** 1.08)) * veins
    b = (0.06 + 0.08 * (v ** 1.45)) * veins
    rgb = np.stack((r, g, b), axis=-1)
    # 叶片平滑边缘（草叶本体占 u ∈ [0, 0.75]，全不透明，因为轮廓由真实弧形几何决定！）
    alpha = np.full((h, w), 255, dtype=np.uint8)

    # 右上块 u ∈ [0.76, 1.0], v ∈ [0.5, 1.0]：柔和金黄海岸罂粟花瓣（圆瓣轮廓）
    # 右下块 u ∈ [0.76, 1.0], v ∈ [0.0, 0.5]：柔和奶白海雏菊（含淡黄花蕊）
    rgb_u8 = np.clip(np.rint(np.clip(rgb, 0.0, 1.0) * 255.0), 0, 255).astype(np.uint8)
    rgba = np.dstack((rgb_u8, alpha))
    # 清空右侧花区 alpha 后绘制 5 瓣柔和野花
    rgba[:, int(w * 0.75):, 3] = 0
    im = Image.fromarray(rgba, mode="RGBA")
    draw = ImageDraw.Draw(im)

    def draw_flower(cx: float, cy: float, radius: float, petal_col, center_col):
        for k in range(5):
            a = k * (math.tau / 5.0) + 0.3
            px = cx + math.cos(a) * radius * 0.48
            py = cy + math.sin(a) * radius * 0.48
            pr = radius * 0.46
            draw.ellipse((px - pr, py - pr, px + pr, py + pr), fill=petal_col + (255,))
        cr = radius * 0.26
        draw.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=center_col + (255,))

    # 上：阳光海岸金花（柔和鹅黄/琥珀，不刺眼）
    draw_flower(w * 0.875, h * 0.25, 44.0, (238, 198, 72), (178, 112, 34))
    # 下：海滨小白菊（柔和暖白 + 淡金蕊）
    draw_flower(w * 0.875, h * 0.75, 42.0, (242, 238, 224), (222, 186, 68))

    out_rgba = dilate_rgb_by_alpha(np.asarray(im, dtype=np.uint8), iterations=16)
    diff_im = Image.fromarray(out_rgba, mode="RGBA")
    nor_im = _normal_from_luma(out_rgba[:, :, :3], strength=1.2)
    gloss_arr = np.clip(np.rint((0.18 + 0.14 * v) * 255.0), 0, 255).astype(np.uint8)
    gloss_im = Image.fromarray(gloss_arr, mode="L")
    trans_arr = np.clip(np.rint((0.45 + 0.45 * v) * 255.0), 0, 255).astype(np.uint8)
    trans_im = Image.fromarray(trans_arr, mode="L")
    return diff_im, nor_im, gloss_im, trans_im


def _make_limestone_textures() -> tuple[Image.Image, Image.Image, Image.Image]:
    """使用 Poly Haven CC0 实拍 coast_rocks_01 2K 岩面漫反射/法线/ARM 制作无缝三平面石灰岩贴图。"""
    rock_dir = ROOT / "art/expressway/sources/coastal-scans/coast_rocks_01/textures"
    diff_im = Image.open(rock_dir / "coast_rocks_01_diff_2k.jpg").convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS)
    nor_im = Image.open(rock_dir / "coast_rocks_01_nor_gl_2k.jpg").convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS)
    arm_im = Image.open(rock_dir / "coast_rocks_01_arm_2k.jpg").convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS)

    # 镜像半移拼缝 + 温和提亮为自然日光暖灰海岸砂岩/花岗岩，保留全部真实岩纹、裂隙与地衣细节
    def make_seamless(arr: np.ndarray) -> np.ndarray:
        h, w = arr.shape[:2]
        shifted = np.roll(np.roll(arr, h // 2, axis=0), w // 2, axis=1)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        wx = np.sin(xx / w * math.pi) ** 2
        wy = np.sin(yy / h * math.pi) ** 2
        mask = (wx * wy)[:, :, None] if arr.ndim == 3 else (wx * wy)
        return arr * mask + shifted * (1.0 - mask)

    d_arr = make_seamless(np.asarray(diff_im, dtype=np.float32) / 255.0)
    d_lin = np.power(np.clip(d_arr, 1e-4, 1.0), 2.2)
    # 校准到自然海岸暖灰岩色域，保留高对比岩裂明暗
    d_lin = np.clip(d_lin * np.array([1.22, 1.18, 1.08], dtype=np.float32) + 0.015, 0.01, 0.85)
    d_srgb = np.clip(np.rint(np.power(d_lin, 1.0 / 2.2) * 255.0), 0, 255).astype(np.uint8)

    n_arr = make_seamless(np.asarray(nor_im, dtype=np.float32))
    n_u8 = np.clip(np.rint(n_arr), 0, 255).astype(np.uint8)

    arm_arr = make_seamless(np.asarray(arm_im, dtype=np.float32) / 255.0)
    gloss_u8 = np.clip(np.rint((1.0 - np.clip(arm_arr[:, :, 1], 0.65, 0.97)) * 255.0), 0, 255).astype(np.uint8)
    return Image.fromarray(d_srgb, mode="RGB"), Image.fromarray(n_u8, mode="RGB"), Image.fromarray(gloss_u8, mode="L")


def build_foliage_textures():
    """烘焙全套边缘扩色植被与石灰岩贴图。"""
    TEX_OUT.mkdir(parents=True, exist_ok=True)
    ez_lod1 = NodePath(
        gltf.load_model(Filename.fromOsSpecific(str(ROOT / "art/expressway/sources/ez-tree/lods/tree_LOD1.glb")))
    )
    mesh0 = ez_lod1.find("**/mesh0")
    mesh1 = ez_lod1.find("**/mesh1")
    bark_imgs = [_extract_panda_tex_fast(t) for t in mesh0.findAllTextures()]
    bark_diff = bark_nor = bark_rough = None
    for im in bark_imgs:
        arr = np.asarray(im.convert("RGB"), dtype=np.float32)
        mean = arr.mean(axis=(0, 1))
        if mean[2] > 200 and mean[0] < 160 and mean[1] < 160:
            bark_nor = im.convert("RGB")
        elif abs(mean[0] - mean[1]) < 4 and abs(mean[1] - mean[2]) < 4 and mean[0] > 155:
            bark_rough = im.convert("L")
        else:
            bark_diff = im.convert("RGB")
    if bark_diff is None or bark_nor is None:
        raise RuntimeError("未能识别 ez-tree 树皮贴图")
    if bark_rough is None:
        bark_rough = Image.new("L", bark_diff.size, 232)

    # 自然温暖的橡木/灰棕树皮（日光下可读清晰纵裂纹理，不发黑成剪影）
    bd_lin = np.power(np.clip(np.asarray(bark_diff, dtype=np.float32) / 255.0, 1e-4, 1.0), 2.2)
    bd_lin *= np.array([0.92, 0.80, 0.66], dtype=np.float32)
    bd_srgb = np.clip(np.rint(np.power(np.clip(bd_lin, 0.0, 1.0), 1.0 / 2.2) * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(bd_srgb, mode="RGB").save(TEX_OUT / "oak-bark-diff.png", optimize=True)
    bark_nor.save(TEX_OUT / "oak-bark-normal.png", optimize=True)
    bg_arr = np.clip(np.rint((1.0 - np.clip(np.asarray(bark_rough, dtype=np.float32) / 255.0, 0.80, 0.98)) * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(bg_arr, mode="L").save(TEX_OUT / "oak-bark-gloss.png", optimize=True)
    Image.new("L", (64, 64), 0).save(TEX_OUT / "oak-bark-transmission.png", optimize=True)

    # 浓密圆形实拍叶簇（单张高质量贴图，全树种共享合批！）
    raw_leaf = _extract_panda_tex_fast(next(iter(mesh1.findAllTextures())))
    cluster_im = _compose_dense_leaf_cluster(raw_leaf)
    cluster_im.save(TEX_OUT / "oak-leaf-diff.png", optimize=True)
    cluster_arr = np.asarray(cluster_im, dtype=np.uint8)
    _normal_from_luma(cluster_arr[:, :, :3], strength=1.8).save(TEX_OUT / "oak-leaf-normal.png", optimize=True)
    greenness = np.clip((cluster_arr[:, :, 1].astype(np.float32) - cluster_arr[:, :, 0].astype(np.float32) * 0.82) / 55.0, 0.0, 1.0)
    Image.fromarray(np.clip(np.rint((0.14 + 0.12 * greenness) * 255.0), 0, 255).astype(np.uint8), mode="L").save(
        TEX_OUT / "oak-leaf-gloss.png", optimize=True
    )
    Image.fromarray(np.clip(np.rint((0.12 + 0.68 * greenness) * 255.0), 0, 255).astype(np.uint8), mode="L").save(
        TEX_OUT / "oak-leaf-transmission.png", optimize=True
    )

    # 灌丛共享浓密叶簇（略加深饱和度）
    sh_lin = np.power(np.clip(cluster_arr[:, :, :3].astype(np.float32) / 255.0, 1e-4, 1.0), 2.2) * np.array([0.82, 0.90, 0.78], dtype=np.float32)
    sh_srgb = np.clip(np.rint(np.power(np.clip(sh_lin, 0.0, 1.0), 1.0 / 2.2) * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(np.dstack((sh_srgb, cluster_arr[:, :, 3])), mode="RGBA").save(TEX_OUT / "shrub-leaf-diff.png", optimize=True)

    # 丝滑草叶 + 海岸微野花贴图
    g_diff, g_nor, g_gloss, g_trans = _make_blade_grass_texture()
    g_diff.save(TEX_OUT / "grass-diff.png", optimize=True)
    g_nor.save(TEX_OUT / "grass-normal.png", optimize=True)
    g_gloss.save(TEX_OUT / "grass-gloss.png", optimize=True)
    g_trans.save(TEX_OUT / "grass-transmission.png", optimize=True)

    # 林下蕨草/高草（grass_medium_01）
    gm_dir = ROOT / "art/expressway/sources/vegetation/grass_medium_01/textures"
    gm_diff = np.asarray(Image.open(gm_dir / "grass_medium_01_diff_1k.jpg").convert("RGB"), dtype=np.uint8)
    gm_alpha = np.asarray(Image.open(gm_dir / "grass_medium_01_alpha_1k.png").convert("L"), dtype=np.uint8)
    gm_rgba = dilate_rgb_by_alpha(np.dstack((gm_diff, gm_alpha)), iterations=16)
    gm_lin = np.power(np.clip(gm_rgba[:, :, :3].astype(np.float32) / 255.0, 1e-4, 1.0), 2.2) * np.array([0.72, 0.90, 0.62], dtype=np.float32)
    gm_srgb = np.clip(np.rint(np.power(np.clip(gm_lin, 0.0, 1.0), 1.0 / 2.2) * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(np.dstack((gm_srgb, gm_alpha)), mode="RGBA").save(TEX_OUT / "fern-diff.png", optimize=True)
    Image.open(gm_dir / "grass_medium_01_nor_gl_1k.jpg").convert("RGB").save(TEX_OUT / "fern-normal.png", optimize=True)
    gm_arm = np.asarray(Image.open(gm_dir / "grass_medium_01_arm_1k.jpg").convert("RGB"), dtype=np.float32) / 255.0
    Image.fromarray(np.clip(np.rint((1.0 - np.clip(gm_arm[:, :, 1], 0.68, 0.98)) * 255.0), 0, 255).astype(np.uint8), mode="L").save(
        TEX_OUT / "fern-gloss.png", optimize=True
    )
    Image.new("L", (256, 256), 185).save(TEX_OUT / "fern-transmission.png", optimize=True)

    # 海岸风化石灰岩 PBR
    b_diff, b_nor, b_gloss = _make_limestone_textures()
    b_diff.save(TEX_OUT / "boulder-diff.png", optimize=True)
    b_nor.save(TEX_OUT / "boulder-normal.png", optimize=True)
    b_gloss.save(TEX_OUT / "boulder-gloss.png", optimize=True)

    return sorted(p.name for p in TEX_OUT.glob("*.png"))


# ==============================================================================
# 程序化有机 3D 树木雕塑器（真实树干根基、分叉枝干 + 球壳法线浓密叶冠）
# ==============================================================================


class _MeshBuilder:
    def __init__(self):
        self.pts: list[np.ndarray] = []
        self.nrm: list[np.ndarray] = []
        self.col: list[np.ndarray] = []
        self.uv: list[np.ndarray] = []
        self.idx: list[np.ndarray] = []
        self.v_off = 0

    def add(self, pts: np.ndarray, nrm: np.ndarray, col: np.ndarray, uv: np.ndarray, idx: np.ndarray) -> None:
        self.pts.append(pts.astype(np.float32))
        self.nrm.append(nrm.astype(np.float32))
        self.col.append(col.astype(np.float32))
        self.uv.append(uv.astype(np.float32))
        self.idx.append(idx.astype(np.uint32) + np.uint32(self.v_off))
        self.v_off += len(pts)

    def build(self, name: str) -> NodePath:
        pts = np.concatenate(self.pts, axis=0)
        nrm = np.concatenate(self.nrm, axis=0)
        col = np.concatenate(self.col, axis=0)
        uv = np.concatenate(self.uv, axis=0)
        idx = np.concatenate(self.idx, axis=0)
        return make_geom_node(name, pts, nrm, col, uv, idx)


def _add_branch_tube(
    builder: _MeshBuilder,
    spine: list[np.ndarray],
    radii: list[float],
    sides: int,
    bark_tint: tuple[float, float, float],
    *,
    flare_base: bool = False,
) -> None:
    """沿 3D 曲线生成平滑收细的树干/枝干管网（含根基外扩与自然环向 UV）。"""
    rings = len(spine)
    pts = np.empty((rings * (sides + 1), 3), dtype=np.float32)
    nrm = np.empty_like(pts)
    uv = np.empty((rings * (sides + 1), 2), dtype=np.float32)
    col = np.ones((rings * (sides + 1), 4), dtype=np.float32)

    # 稳定参考法架（平行传输，避免急弯扭绞）
    t0 = spine[1] - spine[0]
    t0 = t0 / max(float(np.linalg.norm(t0)), 1e-6)
    ref = np.array([1.0, 0.0, 0.0], dtype=np.float32) if abs(t0[0]) < 0.8 else np.array([0.0, 1.0, 0.0], dtype=np.float32)
    u_vec = np.cross(t0, ref)
    u_vec /= max(float(np.linalg.norm(u_vec)), 1e-6)
    v_vec = np.cross(t0, u_vec)

    v_dist = 0.0
    for r_idx in range(rings):
        p = spine[r_idx]
        if r_idx > 0:
            v_dist += float(np.linalg.norm(p - spine[r_idx - 1]))
        if r_idx == 0:
            tang = spine[1] - spine[0]
        elif r_idx == rings - 1:
            tang = spine[-1] - spine[-2]
        else:
            tang = spine[r_idx + 1] - spine[r_idx - 1]
        tang = tang / max(float(np.linalg.norm(tang)), 1e-6)
        # 平行传输正交化
        u_vec = u_vec - np.dot(u_vec, tang) * tang
        un = float(np.linalg.norm(u_vec))
        if un < 1e-5:
            ref = np.array([1.0, 0.0, 0.0], dtype=np.float32) if abs(tang[0]) < 0.8 else np.array([0.0, 1.0, 0.0], dtype=np.float32)
            u_vec = np.cross(tang, ref)
            un = float(np.linalg.norm(u_vec))
        u_vec /= un
        v_vec = np.cross(tang, u_vec)

        rad = radii[r_idx]
        frac = r_idx / max(rings - 1, 1)
        # 根部略暗、向上自然提亮，AO 编码在 alpha ∈ [0.55, 0.92]
        ao = 0.56 + 0.34 * frac
        for s_idx in range(sides + 1):
            ang = (s_idx / sides) * math.tau
            fl = (1.0 + 0.28 * math.cos(ang * 5.0 + 0.4)) if (flare_base and r_idx == 0) else 1.0
            radial = math.cos(ang) * u_vec + math.sin(ang) * v_vec
            row = r_idx * (sides + 1) + s_idx
            pts[row] = p + radial * (rad * fl)
            nrm[row] = radial
            uv[row] = (s_idx / sides * 2.0, v_dist * 0.45)
            col[row] = (bark_tint[0], bark_tint[1], bark_tint[2], ao)

    faces = []
    stride = sides + 1
    for r_idx in range(rings - 1):
        for s_idx in range(sides):
            a = r_idx * stride + s_idx
            b = a + 1
            c = a + stride + 1
            d = a + stride
            faces.extend((a, b, c, a, c, d))
    builder.add(pts, nrm, col, uv, np.asarray(faces, dtype=np.uint32))


def _add_foliage_lobe(
    builder: _MeshBuilder,
    lobe_center: np.ndarray,
    radii: tuple[float, float, float],
    card_count: int,
    card_size: float,
    crown_center: np.ndarray,
    crown_r: float,
    crown_z0: float,
    crown_z1: float,
    color_shadow: tuple[float, float, float],
    color_mid: tuple[float, float, float],
    color_sun: tuple[float, float, float],
    rng: random.Random,
    *,
    flat_top: bool = False,
) -> None:
    """在树冠云团内生成多层次双面弧折叶簇，法线球壳平滑 + 逐顶点植物色相与深度 AO。"""
    rx, ry, rz = radii
    c_sh = np.asarray(color_shadow, dtype=np.float32)
    c_md = np.asarray(color_mid, dtype=np.float32)
    c_sn = np.asarray(color_sun, dtype=np.float32)

    # 每张叶卡采用略微拱起的 2×2 折叠片（5 顶点，4 三角）消除纯平面纸感
    local_xy = np.array(
        [
            [-0.5, -0.5, 0.08],
            [0.5, -0.5, 0.08],
            [0.5, 0.5, 0.08],
            [-0.5, 0.5, 0.08],
            [0.0, 0.0, -0.10],
        ],
        dtype=np.float32,
    )
    local_uv = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.5, 0.5]], dtype=np.float32)
    local_faces = np.array([0, 1, 4, 1, 2, 4, 2, 3, 4, 3, 0, 4], dtype=np.uint32)

    for _ in range(card_count):
        # 优先分布在外壳与中层（shell-biased），内部只保留少量填实阴影核心
        u_dir = np.array([rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)], dtype=np.float32)
        u_len = float(np.linalg.norm(u_dir))
        if u_len < 1e-4:
            u_dir = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        else:
            u_dir /= u_len
        if flat_top and u_dir[2] < -0.35:
            u_dir[2] *= 0.45
        shell_r = 0.35 + 0.65 * (rng.random() ** 0.42)
        pos = lobe_center + np.array([u_dir[0] * rx, u_dir[1] * ry, u_dir[2] * rz], dtype=np.float32) * shell_r

        # 随机 3D 朝向，略倾向朝外与朝上（伞松更偏水平叠层）
        yaw = rng.uniform(0.0, math.tau)
        pitch = rng.uniform(-0.45, 0.45) if flat_top else rng.uniform(-1.15, 1.15)
        roll = rng.uniform(-0.65, 0.65)
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cr, sr = math.cos(roll), math.sin(roll)
        rot = (
            np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]], dtype=np.float32)
            @ np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]], dtype=np.float32)
            @ np.array([[cr, 0, sr], [0, 1, 0], [-sr, 0, cr]], dtype=np.float32)
        )
        sz = card_size * rng.uniform(0.76, 1.24)
        pts = (local_xy * sz) @ rot.T + pos

        # 球壳法线平滑：78% 指向局部云团外法线 + 22% 指向整冠外法线（绝不产生硬纸片明暗断层！）
        lobe_out = pts - lobe_center[None, :]
        lobe_out /= np.maximum(np.linalg.norm(lobe_out, axis=1, keepdims=True), 1e-4)
        crown_out = pts - crown_center[None, :]
        crown_out[:, 2] += 0.35 * crown_r
        crown_out /= np.maximum(np.linalg.norm(crown_out, axis=1, keepdims=True), 1e-4)
        nrm = lobe_out * 0.72 + crown_out * 0.28
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-4)

        # 逐顶点深度 AO（存入 alpha ∈ [0.45, 1.0]，确保阴影图 > 0.25 裁切不漏影，着色器重映射回 [0.16, 1.0]）
        z_t = np.clip((pts[:, 2] - crown_z0) / max(crown_z1 - crown_z0, 1.0), 0.0, 1.0)
        r_t = np.clip(np.hypot(pts[:, 0] - crown_center[0], pts[:, 1] - crown_center[1]) / max(crown_r, 0.5), 0.0, 1.0)
        lobe_r = np.clip(np.linalg.norm((pts - lobe_center) / np.array([rx, ry, rz], np.float32), axis=1), 0.0, 1.2)
        ao_01 = np.clip(0.12 + 0.42 * z_t + 0.26 * r_t + 0.28 * lobe_r, 0.0, 1.0)
        ao_encoded = 0.45 + 0.55 * ao_01

        # 植物色相层次：内膛阴影冷绿 -> 中层浓郁主绿 -> 顶冠阳光暖绿（再叠加极轻微逐叶微差）
        leaf_jitter = rng.uniform(0.92, 1.08)
        sun_t = np.clip(0.55 * z_t + 0.35 * np.clip(nrm[:, 2] * 0.5 + 0.5, 0.0, 1.0) + 0.10 * r_t, 0.0, 1.0)
        low_mix = np.clip(sun_t * 2.0, 0.0, 1.0)[:, None]
        high_mix = np.clip((sun_t - 0.5) * 2.0, 0.0, 1.0)[:, None]
        rgb = np.where(
            sun_t[:, None] < 0.5,
            c_sh * (1.0 - low_mix) + c_md * low_mix,
            c_md * (1.0 - high_mix) + c_sn * high_mix,
        ) * leaf_jitter
        col = np.concatenate((np.clip(rgb, 0.05, 1.0), ao_encoded[:, None]), axis=-1)

        # 随机旋转 UV 90° 倍数，打破重复
        uv_rot = rng.randrange(4)
        uv = local_uv.copy()
        if uv_rot == 1:
            uv = np.stack((1.0 - uv[:, 1], uv[:, 0]), axis=-1)
        elif uv_rot == 2:
            uv = 1.0 - uv
        elif uv_rot == 3:
            uv = np.stack((uv[:, 1], 1.0 - uv[:, 0]), axis=-1)

        builder.add(pts, nrm, col, uv, local_faces)


def _build_species_tree(species: str, seed: int, *, lod_scale: float = 1.0) -> tuple[NodePath, NodePath, float, float]:
    """根据树种原型构建完整 3D 骨架与体积化树冠。"""
    rng = random.Random(seed)
    bark = _MeshBuilder()
    leaves = _MeshBuilder()
    tube_sides = 7 if lod_scale > 0.7 else 5
    sub_sides = 5 if lod_scale > 0.7 else 4

    def make_spine(p0, p1, bend_xy=(0.0, 0.0), steps=5):
        pts = []
        for i in range(steps):
            t = i / (steps - 1)
            arch = math.sin(t * math.pi)
            p = p0 * (1.0 - t) + p1 * t + np.array([bend_xy[0] * arch, bend_xy[1] * arch, 0.0], dtype=np.float32)
            pts.append(p)
        return pts

    lobes = []  # (center, radii, cards, card_size, flat_top)

    if species == "coastal-oak":
        # 1) 阔冠海岸活橡：低垂丰满的下层枝叶（2.8m 起即可见绿冠）+ 宽广层次云状大冠，避免光秃 V 字枝
        bark_tint = (0.86, 0.80, 0.72)
        c_sh, c_md, c_sn = (0.24, 0.40, 0.20), (0.44, 0.64, 0.30), (0.68, 0.80, 0.38)
        trunk_top = np.array([rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 3.4], dtype=np.float32)
        _add_branch_tube(
            bark,
            make_spine(np.array([0, 0, -0.15], np.float32), trunk_top, (rng.uniform(-0.35, 0.35), rng.uniform(-0.25, 0.25)), 6),
            [0.64, 0.46, 0.40, 0.36, 0.32, 0.28],
            tube_sides,
            bark_tint,
            flare_base=True,
        )
        # 5 条低展粗壮主枝 + 下垂侧冠（让橡树枝冠自然垂落，包裹主干分叉）
        for bi in range(5):
            ang = bi * (math.tau / 5.0) + rng.uniform(-0.25, 0.25)
            reach = rng.uniform(3.8, 5.4)
            z_end = rng.uniform(5.2, 8.2)
            b_start = trunk_top * rng.uniform(0.72, 1.0)
            b_end = np.array([math.cos(ang) * reach, math.sin(ang) * reach, z_end], dtype=np.float32)
            _add_branch_tube(
                bark,
                make_spine(b_start, b_end, (math.cos(ang + 1.0) * 0.55, math.sin(ang + 1.0) * 0.55), 5),
                [0.24, 0.19, 0.14, 0.10, 0.06],
                sub_sides,
                bark_tint,
            )
            lobes.append((b_end + np.array([0, 0, 0.4], np.float32), (3.5, 3.4, 2.5), int(96 * lod_scale), 2.25, False))
            sub_ang = ang + rng.choice((-0.55, 0.55))
            sub_end = b_end + np.array([math.cos(sub_ang) * 2.2, math.sin(sub_ang) * 2.2, rng.uniform(-0.8, 1.4)], np.float32)
            _add_branch_tube(bark, make_spine((b_start + b_end) * 0.55, sub_end, (0, 0), 4), [0.12, 0.09, 0.06, 0.04], 4, bark_tint)
            lobes.append((sub_end + np.array([0, 0, 0.3], np.float32), (2.8, 2.7, 2.1), int(62 * lod_scale), 2.05, False))
        # 树干分叉处内膛过渡叶团 + 中央高冠
        lobes.append((trunk_top + np.array([0.0, 0.0, 2.8], np.float32), (3.6, 3.5, 2.4), int(75 * lod_scale), 2.15, False))
        top_end = trunk_top + np.array([rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), 6.8], np.float32)
        _add_branch_tube(bark, make_spine(trunk_top, top_end, (0.25, -0.2), 5), [0.24, 0.18, 0.13, 0.09, 0.05], sub_sides, bark_tint)
        lobes.append((top_end + np.array([0, 0, 0.9], np.float32), (4.3, 4.1, 2.9), int(125 * lod_scale), 2.35, False))

    elif species == "tall-elm":
        # 2) 高拱海岸榆栎：自然深绿大冠 + 适度下垂侧枝
        bark_tint = (0.80, 0.76, 0.68)
        c_sh, c_md, c_sn = (0.20, 0.36, 0.22), (0.38, 0.60, 0.30), (0.60, 0.76, 0.38)
        trunk_top = np.array([rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), 4.6], dtype=np.float32)
        _add_branch_tube(
            bark,
            make_spine(np.array([0, 0, -0.15], np.float32), trunk_top, (0.25, -0.18), 6),
            [0.54, 0.40, 0.35, 0.31, 0.27, 0.24],
            tube_sides,
            bark_tint,
            flare_base=True,
        )
        for bi in range(5):
            ang = bi * (math.tau / 5.0) + rng.uniform(-0.2, 0.2)
            reach = rng.uniform(3.4, 4.8)
            z_end = rng.uniform(7.6, 10.4)
            b_end = np.array([math.cos(ang) * reach, math.sin(ang) * reach, z_end], dtype=np.float32)
            _add_branch_tube(
                bark,
                make_spine(trunk_top * 0.85, b_end, (math.cos(ang) * 0.7, math.sin(ang) * 0.7), 5),
                [0.20, 0.16, 0.12, 0.08, 0.05],
                sub_sides,
                bark_tint,
            )
            lobes.append((b_end + np.array([0, 0, 0.5], np.float32), (3.3, 3.2, 2.6), int(92 * lod_scale), 2.20, False))
        top_end = trunk_top + np.array([0.0, 0.0, 7.6], np.float32)
        _add_branch_tube(bark, make_spine(trunk_top, top_end, (-0.2, 0.2), 5), [0.20, 0.15, 0.11, 0.07, 0.04], sub_sides, bark_tint)
        lobes.append((top_end + np.array([0, 0, 0.8], np.float32), (4.0, 3.9, 3.0), int(125 * lod_scale), 2.30, False))

    elif species == "umbrella-pine":
        # 3) 地中海伞松（Stone Pine）：暖红棕微弯高干 + 标志性深翡翠平顶伞冠！
        bark_tint = (0.98, 0.72, 0.54)
        c_sh, c_md, c_sn = (0.14, 0.30, 0.20), (0.26, 0.48, 0.28), (0.46, 0.64, 0.34)
        trunk_top = np.array([rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7), 8.2], dtype=np.float32)
        _add_branch_tube(
            bark,
            make_spine(np.array([0, 0, -0.15], np.float32), trunk_top, (rng.uniform(-0.8, 0.8), rng.uniform(-0.5, 0.5)), 7),
            [0.52, 0.38, 0.34, 0.30, 0.27, 0.24, 0.21],
            tube_sides,
            bark_tint,
            flare_base=True,
        )
        for bi in range(6):
            ang = bi * (math.tau / 6.0) + rng.uniform(-0.18, 0.18)
            reach = rng.uniform(3.6, 5.0)
            z_end = trunk_top[2] + rng.uniform(2.2, 3.4)
            b_end = np.array([trunk_top[0] + math.cos(ang) * reach, trunk_top[1] + math.sin(ang) * reach, z_end], np.float32)
            _add_branch_tube(
                bark,
                make_spine(trunk_top * np.array([1.0, 1.0, 0.90], np.float32), b_end, (0, 0), 4),
                [0.17, 0.13, 0.09, 0.05],
                sub_sides,
                bark_tint,
            )
            lobes.append((b_end + np.array([0, 0, 0.5], np.float32), (3.2, 3.1, 1.35), int(80 * lod_scale), 2.10, True))
        lobes.append((trunk_top + np.array([0, 0, 3.8], np.float32), (5.0, 4.8, 1.85), int(145 * lod_scale), 2.25, True))

    elif species == "olive-oak":
        # 4) 多干海岸橄榄栎：低矮宽展银橄榄绿树丛，丰满贴近草坡
        bark_tint = (0.82, 0.78, 0.70)
        c_sh, c_md, c_sn = (0.26, 0.38, 0.24), (0.46, 0.58, 0.36), (0.68, 0.76, 0.46)
        for si in range(3):
            ang = si * (math.tau / 3.0) + rng.uniform(-0.3, 0.3)
            reach = rng.uniform(2.2, 3.3)
            z_end = rng.uniform(4.4, 6.2)
            p_end = np.array([math.cos(ang) * reach, math.sin(ang) * reach, z_end], dtype=np.float32)
            _add_branch_tube(
                bark,
                make_spine(np.array([0, 0, -0.15], np.float32), p_end, (math.cos(ang) * 0.7, math.sin(ang) * 0.7), 6),
                [0.34, 0.26, 0.21, 0.17, 0.12, 0.07],
                sub_sides,
                bark_tint,
                flare_base=(si == 0),
            )
            lobes.append((p_end + np.array([0, 0, 0.4], np.float32), (3.2, 3.1, 2.2), int(86 * lod_scale), 2.00, False))
        lobes.append((np.array([0.0, 0.0, 6.4], np.float32), (3.5, 3.4, 2.3), int(92 * lod_scale), 2.10, False))

    else:
        # 5) 海风暖阳橡（golden-oak）：受海风微倾，沉稳橄榄绿底 + 暖琥珀金梢点缀林带
        bark_tint = (0.88, 0.76, 0.64)
        c_sh, c_md, c_sn = (0.28, 0.38, 0.18), (0.52, 0.62, 0.26), (0.84, 0.76, 0.32)
        trunk_top = np.array([0.55, 0.22, 3.6], dtype=np.float32)
        _add_branch_tube(
            bark,
            make_spine(np.array([0, 0, -0.15], np.float32), trunk_top, (0.45, 0.15), 6),
            [0.56, 0.42, 0.36, 0.32, 0.28, 0.24],
            tube_sides,
            bark_tint,
            flare_base=True,
        )
        for bi in range(4):
            ang = bi * (math.tau / 4.0) + 0.45 + rng.uniform(-0.25, 0.25)
            reach = rng.uniform(3.2, 4.6)
            z_end = rng.uniform(5.8, 8.6)
            b_end = trunk_top * 0.4 + np.array([math.cos(ang) * reach + 0.5, math.sin(ang) * reach, z_end], np.float32)
            _add_branch_tube(
                bark,
                make_spine(trunk_top * 0.85, b_end, (0.3, 0.2), 5),
                [0.21, 0.16, 0.12, 0.08, 0.05],
                sub_sides,
                bark_tint,
            )
            lobes.append((b_end + np.array([0, 0, 0.5], np.float32), (3.3, 3.2, 2.4), int(90 * lod_scale), 2.15, False))
        lobes.append((trunk_top + np.array([0.7, 0.2, 5.4], np.float32), (3.9, 3.7, 2.6), int(105 * lod_scale), 2.25, False))

    # 计算整体树冠包围参数供球壳 AO 使用
    lobe_centers = np.array([item[0] for item in lobes], dtype=np.float32)
    crown_center = lobe_centers.mean(axis=0)
    crown_r = max(float(np.max(np.hypot(lobe_centers[:, 0] - crown_center[0], lobe_centers[:, 1] - crown_center[1]))) + 2.8, 4.5)
    crown_z0 = float(np.min(lobe_centers[:, 2])) - 2.2
    crown_z1 = float(np.max(lobe_centers[:, 2])) + 2.4

    for center, rads, count, csize, flat in lobes:
        _add_foliage_lobe(
            leaves, center, rads, max(16, count), csize, crown_center, crown_r, crown_z0, crown_z1,
            c_sh, c_md, c_sn, rng, flat_top=flat,
        )

    bark_node = bark.build("bark")
    leaf_node = leaves.build("leaves")
    # 测量真实高度与冠半径
    all_pts = np.concatenate(bark.pts + leaves.pts, axis=0)
    real_h = float(all_pts[:, 2].max())
    leaf_pts = np.concatenate(leaves.pts, axis=0)
    real_r = float(np.percentile(np.hypot(leaf_pts[:, 0], leaf_pts[:, 1]), 92))
    return bark_node, leaf_node, real_h, real_r


def build_oaks_and_young_oaks():
    """烘焙 5 种异形海岸乔木（LOD1 近景 + LOD2 远景/阴影）与 3 种海岸幼树。"""
    oaks_root = NodePath("standalone-oaks")
    oak_stats = {}
    species_specs = (
        ("a", "coastal-oak", 1001),
        ("b", "tall-elm", 1002),
        ("c", "umbrella-pine", 1003),
        ("d", "olive-oak", 1004),
        ("e", "golden-oak", 1005),
    )
    for letter, species, seed in species_specs:
        holder = oaks_root.attachNewNode(f"oak-{letter}")
        b1, l1, h1, r1 = _build_species_tree(species, seed, lod_scale=1.0)
        lod1 = holder.attachNewNode("lod1")
        b1.reparentTo(lod1)
        l1.reparentTo(lod1)

        b2, l2, _h2, _r2 = _build_species_tree(species, seed, lod_scale=0.52)
        lod2 = holder.attachNewNode("lod2")
        b2.reparentTo(lod2)
        l2.reparentTo(lod2)

        holder.setTag("source-height", f"{h1:.4f}")
        holder.setTag("source-crown-radius", f"{r1:.4f}")
        holder.setTag("source-base", "0.0")
        t1 = sum(pr.getNumPrimitives() for gp in lod1.findAllMatches("**/+GeomNode") for g in gp.node().getGeoms() for pr in g.getPrimitives())
        t2 = sum(pr.getNumPrimitives() for gp in lod2.findAllMatches("**/+GeomNode") for g in gp.node().getGeoms() for pr in g.getPrimitives())
        oak_stats[f"oak-{letter}"] = {"species": species, "height_m": round(h1, 2), "crown_radius_m": round(r1, 2), "lod1_tris": t1, "lod2_tris": t2}
    oaks_root.writeBamFile(Filename.fromOsSpecific(str(FOLIAGE_OUT / "oaks.bam")))

    # 3 种幼树/海岸小乔木（3.4–4.4 m）
    young_root = NodePath("standalone-young-oaks")
    young_stats = {}
    for letter, species, seed, target_h in (
        ("a", "olive-oak", 2001, 3.8),
        ("b", "coastal-oak", 2002, 4.3),
        ("c", "golden-oak", 2003, 3.5),
    ):
        holder = young_root.attachNewNode(f"young-{letter}")
        b, l, h_raw, _r = _build_species_tree(species, seed, lod_scale=0.38)
        sc = target_h / h_raw
        b.setScale(sc)
        l.setScale(sc)
        b.flattenLight()
        l.flattenLight()
        b.reparentTo(holder)
        l.reparentTo(holder)
        holder.setTag("source-height", f"{target_h:.4f}")
        holder.setTag("source-base", "0.0")
        tris = sum(pr.getNumPrimitives() for gp in holder.findAllMatches("**/+GeomNode") for g in gp.node().getGeoms() for pr in g.getPrimitives())
        young_stats[f"young-{letter}"] = {"species": species, "height_m": target_h, "tris": tris}
    young_root.writeBamFile(Filename.fromOsSpecific(str(FOLIAGE_OUT / "young-oaks.bam")))
    return oak_stats, young_stats


def build_shrubs():
    """生成 3 种球壳法线平滑的饱满地中海灌丛（底部深接地 AO、梢头暖绿）。"""
    shrub_root = NodePath("standalone-shrubs")
    stats = {}
    configs = (
        ("a", 1.35, (1.15, 1.05, 0.72), 82, 0.92, (0.24, 0.40, 0.22), (0.44, 0.66, 0.30), (0.68, 0.84, 0.38), 3001),
        ("b", 1.55, (1.35, 1.18, 0.82), 95, 0.98, (0.22, 0.38, 0.24), (0.42, 0.62, 0.36), (0.66, 0.78, 0.44), 3002),
        ("c", 1.15, (1.10, 0.95, 0.62), 72, 0.82, (0.28, 0.42, 0.20), (0.54, 0.68, 0.30), (0.84, 0.84, 0.38), 3003),
    )
    for letter, target_h, rads, cards, csize, c_sh, c_md, c_sn, seed in configs:
        rng = random.Random(seed)
        leaves = _MeshBuilder()
        center = np.array([0.0, 0.0, target_h * 0.45], dtype=np.float32)
        # 2 个微错位的灌丛副团组成自然非对称轮廓
        _add_foliage_lobe(leaves, center, rads, int(cards * 0.65), csize, center, rads[0], 0.0, target_h, c_sh, c_md, c_sn, rng)
        off = np.array([rng.uniform(-0.45, 0.45), rng.uniform(-0.45, 0.45), -0.08], dtype=np.float32)
        _add_foliage_lobe(
            leaves, center + off, (rads[0] * 0.72, rads[1] * 0.72, rads[2] * 0.78), int(cards * 0.35), csize * 0.85,
            center, rads[0], 0.0, target_h, c_sh, c_md, c_sn, rng,
        )
        # 落地对齐
        pts = np.concatenate(leaves.pts, axis=0)
        z_min = float(pts[:, 2].min())
        for arr in leaves.pts:
            arr[:, 2] -= z_min
        real_h = float(np.concatenate(leaves.pts, axis=0)[:, 2].max())
        holder = shrub_root.attachNewNode(f"shrub-{letter}")
        leaves.build("leaves").reparentTo(holder)
        holder.setTag("source-height", f"{real_h:.4f}")
        holder.setTag("source-base", "0.0")
        stats[f"shrub-{letter}"] = {"height_m": round(real_h, 2), "tris": sum(len(x) for x in leaves.idx) // 3}
    shrub_root.writeBamFile(Filename.fromOsSpecific(str(FOLIAGE_OUT / "shrubs.bam")))
    return stats


def _add_arched_blade(
    builder: _MeshBuilder,
    base_xy: tuple[float, float],
    yaw: float,
    height: float,
    width: float,
    bend: float,
    tilt: float,
    *,
    u_span: tuple[float, float] = (0.05, 0.68),
) -> None:
    """生成一根 3 段优雅弧弯收尖的 3D 草叶（5 三角），饱满丝滑无纸片杂噪。"""
    co, si = math.cos(yaw), math.sin(yaw)
    # 4 行: t=0, 0.33, 0.68, 1.0（顶行收尖为 1 点）
    ts = (0.0, 0.34, 0.70, 1.0)
    ws = (0.50, 0.42, 0.24, 0.0)
    pts = []
    nrm = []
    uv = []
    for t, w_half in zip(ts, ws):
        out_r = tilt * t + bend * (t ** 2.2)
        z = height * (t - 0.14 * bend * (t ** 2.6))
        cx = base_xy[0] + co * out_r
        cy = base_xy[1] + si * out_r
        # 垂直于伸展方向的叶宽向量
        sx, sy = -si * width * w_half, co * width * w_half
        # 柔和向上的草叶法线（随高度略向叶背弯曲）
        nx, ny, nz = co * (0.28 + 0.35 * t), si * (0.28 + 0.35 * t), 0.92
        inv = 1.0 / math.sqrt(nx * nx + ny * ny + nz * nz)
        if w_half > 0.0:
            pts.append((cx - sx, cy - sy, z))
            pts.append((cx + sx, cy + sy, z))
            nrm.extend(((nx * inv, ny * inv, nz * inv),) * 2)
            uv.append((u_span[0], t))
            uv.append((u_span[1], t))
        else:
            pts.append((cx, cy, z))
            nrm.append((nx * inv, ny * inv, nz * inv))
            uv.append(((u_span[0] + u_span[1]) * 0.5, 1.0))
    pts_a = np.asarray(pts, dtype=np.float32)
    nrm_a = np.asarray(nrm, dtype=np.float32)
    uv_a = np.asarray(uv, dtype=np.float32)
    col_a = np.ones((len(pts_a), 4), dtype=np.float32)
    faces = np.array([0, 1, 3, 0, 3, 2, 2, 3, 5, 2, 5, 4, 4, 5, 6], dtype=np.uint32)
    builder.add(pts_a, nrm_a, col_a, uv_a, faces)


def _add_wildflower_head(builder: _MeshBuilder, pos: tuple[float, float, float], size: float, golden: bool, rng: random.Random) -> None:
    """在草丛梢头点缀一朵极小巧的海岸野花（2 三角柔面）。"""
    yaw = rng.uniform(0.0, math.tau)
    tilt = rng.uniform(0.12, 0.38)
    co, si = math.cos(yaw), math.sin(yaw)
    half = size * 0.5
    local = np.array([[-half, -half, 0.0], [half, -half, 0.0], [half, half, 0.0], [-half, half, 0.0]], dtype=np.float32)
    # 微倾斜朝天
    ct, st = math.cos(tilt), math.sin(tilt)
    rot = np.array([[co, -si * ct, si * st], [si, co * ct, -co * st], [0, st, ct]], dtype=np.float32)
    pts = local @ rot.T + np.asarray(pos, dtype=np.float32)
    nrm = np.tile(np.array([0.0, 0.0, 1.0], dtype=np.float32), (4, 1))
    v0, v1 = (0.52, 0.98) if golden else (0.02, 0.48)
    uv = np.array([[0.76, v0], [0.99, v0], [0.99, v1], [0.76, v1]], dtype=np.float32)
    col = np.ones((4, 4), dtype=np.float32)
    builder.add(pts, nrm, col, uv, np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32))


def build_ferns_and_grass():
    """烘焙 8 种自然弧弯多叶草簇（含极少量海岸野花簇）与 2 种林下高草/蕨丛。"""
    # 1) 林下高草/蕨丛（沿用 CC0 grass_medium_01 的轻量簇组合）
    from panda3d.core import GeomVertexReader

    gm = NodePath(
        gltf.load_model(Filename.fromOsSpecific(str(ROOT / "art/expressway/sources/vegetation/grass_medium_01/grass_medium_01_1k.gltf")))
    )
    gm_parts = []
    for gp in gm.findAllMatches("**/+GeomNode"):
        geom = gp.node().getGeom(0)
        vd = geom.getVertexData()
        cnt = vd.getNumRows()
        pr = GeomVertexReader(vd, "vertex")
        nr = GeomVertexReader(vd, "normal")
        cols = {c.getName().getName() for c in vd.getFormat().getColumns()}
        tr = GeomVertexReader(vd, "texcoord.0" if "texcoord.0" in cols else "texcoord")
        pts = np.array([tuple(pr.getData3f()) for _ in range(cnt)], dtype=np.float32)
        nrm = np.array([tuple(nr.getData3f()) for _ in range(cnt)], dtype=np.float32)
        uv = np.array([tuple(tr.getData2f()) for _ in range(cnt)], dtype=np.float32)
        tris = [prim.decompose().getVertex(vi) for prim in geom.getPrimitives() for vi in range(prim.decompose().getNumVertices())]
        if 150 <= len(tris) // 3 <= 450:
            pts[:, 0] -= float(pts[:, 0].mean())
            pts[:, 1] -= float(pts[:, 1].mean())
            pts[:, 2] -= float(pts[:, 2].min())
            gm_parts.append((pts, nrm, uv, np.asarray(tris, dtype=np.uint32)))

    ferns_root = NodePath("standalone-ferns")
    fern_stats = {}
    for fi, letter in enumerate(("a", "b")):
        fb = _MeshBuilder()
        rng = random.Random(4000 + fi)
        for k in range(3):
            pts, nrm, uv, idx = gm_parts[(fi * 2 + k) % len(gm_parts)]
            ang = k * (math.tau / 3.0) + rng.uniform(-0.25, 0.25)
            ca, sa = math.cos(ang), math.sin(ang)
            sc = rng.uniform(1.85, 2.35)
            p = pts.copy() * sc
            p[:, 0], p[:, 1] = p[:, 0] * ca - p[:, 1] * sa + math.cos(ang) * 0.14, p[:, 0] * sa + p[:, 1] * ca + math.sin(ang) * 0.14
            n = nrm.copy()
            n[:, 0], n[:, 1] = n[:, 0] * ca - n[:, 1] * sa, n[:, 0] * sa + n[:, 1] * ca
            h_max = max(float(p[:, 2].max()), 0.2)
            ao = 0.50 + 0.50 * np.clip(p[:, 2] / h_max, 0.0, 1.0)
            col = np.ones((len(p), 4), dtype=np.float32)
            col[:, 0:3] = np.array([0.74, 0.90, 0.62], dtype=np.float32)
            col[:, 3] = ao
            fb.add(p, n, col, uv, idx)
        real_h = float(np.concatenate(fb.pts, axis=0)[:, 2].max())
        holder = ferns_root.attachNewNode(f"fern-{letter}")
        fb.build("leaves").reparentTo(holder)
        holder.setTag("source-height", f"{real_h:.4f}")
        holder.setTag("source-base", "0.0")
        fern_stats[f"fern-{letter}"] = {"height_m": round(real_h, 2), "tris": sum(len(x) for x in fb.idx) // 3}
    ferns_root.writeBamFile(Filename.fromOsSpecific(str(FOLIAGE_OUT / "ferns.bam")))

    # 2) 8 种自然弧弯多叶草簇（0-2 鲜绿草甸、3-5 暖金高草、6-7 带极克制海岸野花草簇）
    grass_root = NodePath("standalone-grass-tufts")
    tuft_tris = []
    for ti in range(8):
        rng = random.Random(5000 + ti)
        gb = _MeshBuilder()
        is_dry = 3 <= ti <= 5
        is_flower = ti >= 6
        blades = 11 if not is_flower else 10
        base_h = 0.34 if not is_dry else 0.44
        if is_flower:
            base_h = 0.40
        for bi in range(blades):
            ang = bi * (math.tau / blades) + rng.uniform(-0.28, 0.28)
            r0 = rng.uniform(0.02, 0.14)
            bh = base_h * rng.uniform(0.68, 1.26)
            bw = rng.uniform(0.048, 0.078)
            bend = rng.uniform(0.12, 0.32)
            tilt = rng.uniform(0.05, 0.16)
            _add_arched_blade(gb, (math.cos(ang) * r0, math.sin(ang) * r0), ang, bh, bw, bend, tilt)
        if is_flower:
            # 每株野花草簇仅 2 朵极柔小花（且仅在草格约 12% 位置出现），自然克制
            for fk in range(2):
                fa = rng.uniform(0.0, math.tau)
                fr = rng.uniform(0.08, 0.20)
                fz = base_h * rng.uniform(0.88, 1.12)
                _add_wildflower_head(gb, (math.cos(fa) * fr, math.sin(fa) * fr, fz), rng.uniform(0.085, 0.115), ti == 6, rng)
        gb.build(f"tuft-{ti}").reparentTo(grass_root)
        tuft_tris.append(sum(len(x) for x in gb.idx) // 3)
    grass_root.writeBamFile(Filename.fromOsSpecific(str(FOLIAGE_OUT / "grass-tufts.bam")))
    return fern_stats, tuft_tris


# ==============================================================================
# 闭合 3D 海岸石灰岩巨石雕塑器（绝无开放黑洞与贴图发黑）
# ==============================================================================


def _icosphere(subdivisions: int) -> tuple[np.ndarray, np.ndarray]:
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    verts = [
        (-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0),
        (0, -1, phi), (0, 1, phi), (0, -1, -phi), (0, 1, -phi),
        (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1),
    ]
    verts = [tuple(np.array(v, dtype=np.float32) / np.linalg.norm(v)) for v in verts]
    faces = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]
    for _ in range(subdivisions):
        mid_cache = {}
        new_faces = []

        def midpoint(a: int, b: int, cache=mid_cache) -> int:
            key = (a, b) if a < b else (b, a)
            if key not in cache:
                m = np.array(verts[a], dtype=np.float32) + np.array(verts[b], dtype=np.float32)
                m /= np.linalg.norm(m)
                cache[key] = len(verts)
                verts.append(tuple(m))
            return cache[key]

        for a, b, c in faces:
            ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
            new_faces.extend(((a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)))
        faces = new_faces
    return np.asarray(verts, dtype=np.float32), np.asarray(faces, dtype=np.uint32)


def _sculpt_boulder(subdiv: int, axes: tuple[float, float, float], seed: int) -> tuple[NodePath, float, float]:
    """雕刻带锐利棱脊、层状解理面与硬朗切面的闭合海岸岩石（拒绝平滑土豆块）。"""
    rng = random.Random(seed)
    dirs, faces = _icosphere(subdiv)
    # 12 个 Voronoi 岩体解理削切面 + 阶梯沉积岩层，塑造棱角分明的天然花岗岩/石灰岩体块
    planes = []
    for _ in range(12):
        n = np.array([rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 0.85)], dtype=np.float32)
        n /= max(float(np.linalg.norm(n)), 1e-5)
        planes.append((n, rng.uniform(0.56, 0.82), rng.uniform(0.42, 0.72)))
    freqs = [
        (np.array([rng.uniform(-4.5, 4.5), rng.uniform(-4.5, 4.5), rng.uniform(-4.5, 4.5)], np.float32), rng.uniform(0, math.tau), amp)
        for amp in (0.16, 0.11, 0.075, 0.045, 0.03)
    ]

    pts = dirs.copy()
    disp = np.ones(len(pts), dtype=np.float32)
    for fv, ph, amp in freqs:
        # 绝对值折痕（ridged noise）构造硬朗岩石棱线
        disp += amp * (1.0 - np.abs(np.sin(pts @ fv + ph)) * 2.0) * 0.7
    # 沉积岩阶梯台阶
    z_steps = pts[:, 2] * 7.5 + 0.6 * np.sin(pts[:, 0] * 3.0)
    disp += 0.065 * (np.sin(z_steps) + 0.35 * np.sin(z_steps * 2.0))
    pts *= disp[:, None]
    for pn, cutoff, strength in planes:
        proj = pts @ pn
        excess = np.maximum(0.0, proj - cutoff)
        pts -= (excess * strength)[:, None] * pn[None, :]

    pts[:, 0] *= axes[0]
    pts[:, 1] *= axes[1]
    pts[:, 2] *= axes[2]
    pts[:, 2] = np.where(pts[:, 2] < -axes[2] * 0.42, -axes[2] * 0.42 + (pts[:, 2] + axes[2] * 0.42) * 0.22, pts[:, 2])
    pts[:, 2] -= float(pts[:, 2].min())
    real_h = float(pts[:, 2].max())

    # 按面展开混合 65% 面法线 + 35% 平滑顶点法线，让日光切出真实锐利的石面明暗棱线！
    tri_pts = pts[faces]
    face_n = np.cross(tri_pts[:, 1] - tri_pts[:, 0], tri_pts[:, 2] - tri_pts[:, 0])
    face_n_unit = face_n / np.maximum(np.linalg.norm(face_n, axis=1, keepdims=True), 1e-6)
    v_nrm = np.zeros_like(pts)
    for corner in range(3):
        np.add.at(v_nrm, faces[:, corner], face_n)
    v_nrm /= np.maximum(np.linalg.norm(v_nrm, axis=1, keepdims=True), 1e-6)

    flat_pts = tri_pts.reshape(-1, 3)
    flat_vn = v_nrm[faces].reshape(-1, 3)
    flat_fn = np.repeat(face_n_unit, 3, axis=0)
    flat_n = flat_fn * 0.62 + flat_vn * 0.38
    flat_n /= np.maximum(np.linalg.norm(flat_n, axis=1, keepdims=True), 1e-6)

    # 三平面投影 UV（按面主法向选 XY/XZ/YZ，彻底消除极点拉伸！）
    abs_fn = np.abs(flat_fn)
    uv = np.empty((len(flat_pts), 2), dtype=np.float32)
    use_xy = (abs_fn[:, 2] >= abs_fn[:, 0]) & (abs_fn[:, 2] >= abs_fn[:, 1])
    use_xz = (~use_xy) & (abs_fn[:, 1] >= abs_fn[:, 0])
    uv[use_xy] = flat_pts[use_xy][:, [0, 1]] * 0.32
    uv[use_xz] = flat_pts[use_xz][:, [0, 2]] * 0.32
    use_yz = (~use_xy) & (~use_xz)
    uv[use_yz] = flat_pts[use_yz][:, [1, 2]] * 0.32

    z_frac = np.clip(flat_pts[:, 2] / max(real_h, 0.5), 0.0, 1.0)
    top_moss = np.clip((flat_n[:, 2] - 0.56) / 0.32, 0.0, 1.0) * np.clip((z_frac - 0.30) / 0.45, 0.0, 1.0) * 0.52
    base_ao = 0.64 + 0.36 * np.clip(z_frac / 0.30, 0.0, 1.0)
    stone_col = np.array([1.0, 0.98, 0.94], dtype=np.float32)
    moss_col = np.array([0.36, 0.52, 0.22], dtype=np.float32)
    rgb = (stone_col * (1.0 - top_moss[:, None]) + moss_col * top_moss[:, None]) * base_ao[:, None]
    col = np.concatenate((np.clip(rgb, 0.25, 1.0), np.ones((len(flat_pts), 1), dtype=np.float32)), axis=-1)

    return make_geom_node("rock", flat_pts, flat_n, col, uv, np.arange(len(flat_pts), dtype=np.uint32)), real_h, 0.0


def build_boulders():
    """烘焙 5 种闭合暖色海岸石灰岩巨石（双 LOD，绝无开放黑面）。"""
    boulders_root = NodePath("standalone-boulders")
    specs = (
        ("huge", (4.6, 3.5, 3.0), 6001),
        ("large_a", (3.6, 2.8, 2.5), 6002),
        ("large_b", (3.9, 2.5, 2.8), 6003),
        ("medium", (2.8, 2.3, 2.0), 6004),
        ("small", (1.9, 1.6, 1.3), 6005),
    )
    stats = {}
    for label, axes, seed in specs:
        holder = boulders_root.attachNewNode(f"boulder-{label}")
        lod0, h0, base0 = _sculpt_boulder(3, axes, seed)
        lod0.setName("lod0")
        lod0.reparentTo(holder)
        lod1, _h1, _b1 = _sculpt_boulder(2, axes, seed)
        lod1.setName("lod1")
        lod1.reparentTo(holder)
        holder.setTag("source-height", f"{h0:.4f}")
        holder.setTag("source-base", f"{base0:.4f}")
        stats[label] = {"height_m": round(h0, 2), "lod0_tris": 1280, "lod1_tris": 320}
    boulders_root.writeBamFile(Filename.fromOsSpecific(str(FOLIAGE_OUT / "boulders.bam")))
    return stats


def write_license_and_manifest(sky_info, terrain_info, tex_names, oak_stats, young_stats, shrub_stats, fern_stats, tuft_tris, boulder_stats):
    license_text = (
        "CoastalDrive Standalone Mediterranean Coast Foliage, Terrain & Limestone Pack\n"
        "Zero proprietary / external game dependencies.\n\n"
        "1. Sculpted 3D Coastal Trees, Shrubs, Grass Blades & Closed Limestone Boulders:\n"
        "   - Original procedural geometry by CoastalDrive (tools/environment/prepare_standalone_env.py).\n"
        "   - Oak leaf cluster derived from EZ-Tree (MIT, Daniel Greenheck) + ambientCG bark (CC0-1.0).\n"
        "2. Ground, Ferns & Cliff Scans:\n"
        "   - Poly Haven leafy_grass, grass_ground, grass_medium_01, coastal_cliff_01, coast_rocks_01 (CC0-1.0).\n"
        "3. Daylight Sky & IBL:\n"
        "   - Poly Haven kloofendal_48d_partly_cloudy_puresky (Greg Zaal, Jarod Guest), CC0-1.0.\n"
    )
    (FOLIAGE_OUT / "License-Standalone-Foliage.txt").write_text(license_text, encoding="utf-8")
    manifest = {
        "generator": "tools/environment/prepare_standalone_env.py",
        "style": "Mediterranean / Pacific Coast Natural Stylized-Photoreal",
        "sky": sky_info,
        "terrain": terrain_info,
        "textures": tex_names,
        "oaks": oak_stats,
        "young_oaks": young_stats,
        "shrubs": shrub_stats,
        "ferns": fern_stats,
        "grass_tuft_tris": tuft_tris,
        "boulders": boulder_stats,
        "bam_sha256": {p.name: sha256_file(p) for p in sorted(FOLIAGE_OUT.glob("*.bam"))},
    }
    (FOLIAGE_OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    FOLIAGE_OUT.mkdir(parents=True, exist_ok=True)
    print("[1/6] 确认 CC0 晴空与 IBL...")
    sky_info = promote_daylight_sky()
    print("[2/6] 烘焙温暖饱满的三层地中海草甸 PBR...")
    terrain_info = build_terrain_textures()
    print("[3/6] 烘焙浓密实拍叶簇、丝滑草叶野花与海岸石灰岩贴图...")
    tex_names = build_foliage_textures()
    print("[4/6] 雕塑 5 种异形海岸乔木（活橡/高榆/伞松/橄榄栎/金梢橡）与 3 种幼树...")
    oak_stats, young_stats = build_oaks_and_young_oaks()
    print("[5/6] 雕塑 3 种球壳平滑灌丛、2 种林下蕨草与 8 种弧弯草簇...")
    shrub_stats = build_shrubs()
    fern_stats, tuft_tris = build_ferns_and_grass()
    print("[6/6] 雕塑 5 种闭合暖色海岸石灰岩巨石...")
    boulder_stats = build_boulders()
    write_license_and_manifest(
        sky_info, terrain_info, tex_names, oak_stats, young_stats, shrub_stats, fern_stats, tuft_tris, boulder_stats
    )
    print("海岸独立美术包烘焙完成:")
    print("  乔木:", oak_stats)
    print("  幼树:", young_stats)
    print("  灌丛:", shrub_stats)
    print("  草簇:", tuft_tris, "蕨草:", fern_stats)
    print("  巨石:", boulder_stats)


if __name__ == "__main__":
    main()
