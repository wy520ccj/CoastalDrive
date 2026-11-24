"""生成落日海岸工坊（Sunset Atelier）高质感拉丝材质、毛玻璃控件、写实模式缩略图与图标贴图。"""

import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "game" / "ui" / "atelier"
OUT.mkdir(parents=True, exist_ok=True)


def _noise_overlay(w, h, strength=6, seed=42):
    """生成细微哑光阳极氧化金属微颗粒噪点，消除纯色块塑料感。"""
    rng = random.Random(seed)
    vals = bytes(max(0, min(255, 128 + rng.randint(-strength, strength))) for _ in range(w * h))
    g = Image.frombytes("L", (w, h), vals)
    return Image.merge("RGBA", (g, g, g, Image.new("L", (w, h), 255)))


def _apply_micrograin(img, strength=5, seed=42):
    """将微颗粒叠加到带透明通道的图层内部，保持边缘抗锯齿干净。"""
    w, h = img.size
    alpha = img.getchannel("A")
    rng = random.Random(seed)
    base = img.convert("RGB")
    px = base.load()
    for y in range(h):
        for x in range(w):
            d = rng.randint(-strength, strength)
            r, g, b = px[x, y]
            px[x, y] = (
                max(0, min(255, r + d)),
                max(0, min(255, g + d)),
                max(0, min(255, b + d)),
            )
    out = base.convert("RGBA")
    out.putalpha(alpha)
    return out


def _draw_supersampled(size, draw_fn, scale=4):
    hi = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(hi)
    draw_fn(draw, size * scale)
    return hi.resize((size, size), Image.Resampling.LANCZOS)


def make_icons():
    white = (255, 255, 255, 255)

    def steering(d, s):
        w = max(4, s // 15)
        pad = s // 7
        d.ellipse((pad, pad, s - pad, s - pad), outline=white, width=w)
        c = s // 2
        r_hub = s // 9
        d.ellipse((c - r_hub, c - r_hub, c + r_hub, c + r_hub), outline=white, width=w)
        d.line((pad + w, c - s // 22, c - r_hub, c - s // 28), fill=white, width=w)
        d.line((c + r_hub, c - s // 28, s - pad - w, c - s // 22), fill=white, width=w)
        d.line((c, c + r_hub, c, s - pad - w), fill=white, width=w)

    def flask(d, s):
        w = max(4, s // 17)
        c = s // 2
        d.line((c - s // 7, s // 7, c + s // 7, s // 7), fill=white, width=w)
        pts = [
            (c - s // 11, s // 7),
            (c - s // 11, s * 38 // 100),
            (s * 18 // 100, s * 82 // 100),
            (s * 82 // 100, s * 82 // 100),
            (c + s // 11, s * 38 // 100),
            (c + s // 11, s // 7),
        ]
        d.line(pts, fill=white, width=w, joint="curve")
        d.line((s * 30 // 100, s * 64 // 100, s * 70 // 100, s * 64 // 100), fill=white, width=max(3, w - 2))

    def trophy(d, s):
        w = max(4, s // 16)
        c = s // 2
        d.rounded_rectangle((s * 26 // 100, s * 16 // 100, s * 74 // 100, s * 56 // 100), radius=s // 9, outline=white, width=w)
        d.arc((s * 13 // 100, s * 22 // 100, s * 32 // 100, s * 46 // 100), 90, 270, fill=white, width=w)
        d.arc((s * 68 // 100, s * 22 // 100, s * 87 // 100, s * 46 // 100), 270, 90, fill=white, width=w)
        d.line((c, s * 56 // 100, c, s * 77 // 100), fill=white, width=w)
        d.line((s * 32 // 100, s * 80 // 100, s * 68 // 100, s * 80 // 100), fill=white, width=w)

    def car(d, s):
        w = max(4, s // 16)
        pts = [
            (s * 14 // 100, s * 62 // 100),
            (s * 20 // 100, s * 46 // 100),
            (s * 34 // 100, s * 30 // 100),
            (s * 66 // 100, s * 30 // 100),
            (s * 80 // 100, s * 46 // 100),
            (s * 86 // 100, s * 62 // 100),
            (s * 86 // 100, s * 70 // 100),
            (s * 14 // 100, s * 70 // 100),
            (s * 14 // 100, s * 62 // 100),
        ]
        d.line(pts, fill=white, width=w, joint="curve")
        d.line((s * 22 // 100, s * 48 // 100, s * 78 // 100, s * 48 // 100), fill=white, width=max(3, w - 3))
        r = s * 9 // 100
        for cx in (s * 30 // 100, s * 70 // 100):
            cy = s * 70 // 100
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(18, 22, 30, 255), outline=white, width=w)

    def highway(d, s):
        w = max(4, s // 16)
        c = s // 2
        d.line((s * 34 // 100, s * 16 // 100, s * 16 // 100, s * 84 // 100), fill=white, width=w)
        d.line((s * 66 // 100, s * 16 // 100, s * 84 // 100, s * 84 // 100), fill=white, width=w)
        for y0, y1 in ((20, 32), (44, 58), (70, 84)):
            d.line((c, s * y0 // 100, c, s * y1 // 100), fill=white, width=max(3, w - 2))

    def stopwatch(d, s):
        w = max(4, s // 16)
        c = s // 2
        cy = s * 56 // 100
        r = s * 31 // 100
        d.ellipse((c - r, cy - r, c + r, cy + r), outline=white, width=w)
        d.line((c - s // 10, s * 14 // 100, c + s // 10, s * 14 // 100), fill=white, width=w)
        d.line((c, s * 14 // 100, c, cy - r), fill=white, width=w)
        d.line((c, cy, c + r * 55 // 100, cy - r * 42 // 100), fill=white, width=w)

    def compass(d, s):
        w = max(4, s // 16)
        pad = s // 7
        c = s // 2
        d.ellipse((pad, pad, s - pad, s - pad), outline=white, width=w)
        d.polygon([(c, s * 28 // 100), (s * 60 // 100, c), (c, s * 72 // 100), (s * 40 // 100, c)], outline=white, width=max(3, w - 2))

    def speaker(d, s):
        w = max(4, s // 16)
        pts = [
            (s * 18 // 100, s * 40 // 100),
            (s * 34 // 100, s * 40 // 100),
            (s * 54 // 100, s * 22 // 100),
            (s * 54 // 100, s * 78 // 100),
            (s * 34 // 100, s * 60 // 100),
            (s * 18 // 100, s * 60 // 100),
            (s * 18 // 100, s * 40 // 100),
        ]
        d.polygon(pts, fill=(255, 255, 255, 55), outline=white, width=w)
        d.arc((s * 52 // 100, s * 34 // 100, s * 74 // 100, s * 66 // 100), -52, 52, fill=white, width=w)
        d.arc((s * 56 // 100, s * 22 // 100, s * 88 // 100, s * 78 // 100), -56, 56, fill=white, width=w)

    def shield(d, s):
        w = max(4, s // 15)
        c = s // 2
        pts = [
            (c, s * 14 // 100),
            (s * 80 // 100, s * 26 // 100),
            (s * 76 // 100, s * 58 // 100),
            (c, s * 86 // 100),
            (s * 24 // 100, s * 58 // 100),
            (s * 20 // 100, s * 26 // 100),
            (c, s * 14 // 100),
        ]
        d.polygon(pts, fill=(255, 255, 255, 45), outline=white, width=w)
        d.line((s * 36 // 100, s * 50 // 100, s * 47 // 100, s * 61 // 100, s * 66 // 100, s * 38 // 100), fill=white, width=w)

    def sliders(d, s):
        w = max(4, s // 17)
        for y, kx in ((28, 36), (50, 66), (72, 46)):
            yy = s * y // 100
            xx = s * kx // 100
            r = s * 7 // 100
            d.line((s * 16 // 100, yy, s * 84 // 100, yy), fill=white, width=w)
            d.ellipse((xx - r, yy - r, xx + r, yy + r), fill=(18, 22, 30, 255), outline=white, width=w)

    def paint(d, s):
        w = max(4, s // 16)
        c = s // 2
        d.polygon([(c, s * 16 // 100), (s * 76 // 100, s * 56 // 100), (c, s * 84 // 100), (s * 24 // 100, s * 56 // 100)], outline=white, width=w)
        d.arc((s * 26 // 100, s * 40 // 100, s * 74 // 100, s * 84 // 100), 0, 180, fill=white, width=w)

    def tire(d, s):
        w = max(4, s // 16)
        pad = s // 8
        c = s // 2
        d.ellipse((pad, pad, s - pad, s - pad), fill=(255, 255, 255, 32), outline=white, width=w + 2)
        r2 = s * 22 // 100
        d.ellipse((c - r2, c - r2, c + r2, c + r2), outline=white, width=w)
        r3 = s * 8 // 100
        d.ellipse((c - r3, c - r3, c + r3, c + r3), fill=white)

    def brake(d, s):
        w = max(4, s // 16)
        pad = s // 7
        c = s // 2
        d.ellipse((pad, pad, s - pad, s - pad), outline=white, width=w)
        d.arc((pad - w, pad - w, s - pad + w, s - pad + w), -40, 40, fill=white, width=w * 2)
        r2 = s * 14 // 100
        d.ellipse((c - r2, c - r2, c + r2, c + r2), outline=white, width=w)

    specs = {
        "steering": steering,
        "flask": flask,
        "trophy": trophy,
        "car": car,
        "highway": highway,
        "stopwatch": stopwatch,
        "compass": compass,
        "speaker": speaker,
        "shield": shield,
        "sliders": sliders,
        "paint": paint,
        "tire": tire,
        "brake": brake,
    }
    for name, fn in specs.items():
        img = _draw_supersampled(128, fn, scale=4)
        img.save(OUT / f"icon-{name}.png")


def make_mode_thumbnails(source_grid: Path):
    """将 2x2 写实暗调汽车摄影网格切分并羽化为 4 枚卡片内嵌缩略图（平滑融入黑曜石卡片底）。"""
    if not source_grid.exists():
        return
    grid = Image.open(source_grid).convert("RGB")
    gw, gh = grid.size
    hw, hh = gw // 2, gh // 2
    # 四象限顺序：左上(轮毂/生涯)、右上(落日滨海公路/自由驾驶)、左下(精密仪表/计时挑战)、右下(黄昏大桥高速/无限高速)
    crops = {
        "thumb-career": (0, 0, hw, hh),
        "thumb-free": (hw, 0, gw, hh),
        "thumb-timetrial": (0, hh, hw, gh),
        "thumb-highway": (hw, hh, gw, gh),
    }
    tw, th = 220, 136
    # 构造平滑四边羽化蒙版（右侧更长渐隐，完美融合到文字区黑曜石背景）
    mask = Image.new("L", (tw, th), 255)
    mpx = mask.load()
    for y in range(th):
        vy = 1.0
        if y < 14:
            vy = y / 14.0
        elif y > th - 15:
            vy = (th - 1 - y) / 14.0
        for x in range(tw):
            vx = 1.0
            if x < 14:
                vx = x / 14.0
            elif x > tw - 76:
                vx = max(0.0, (tw - 1 - x) / 75.0)
                vx = vx * vx * (3.0 - 2.0 * vx)
            mpx[x, y] = round(255 * vx * vy)

    for name, box in crops.items():
        crop = grid.crop(box)
        # 按 220x136 居中裁切并微调对比度与饱和度，贴近参考图暗调高质感轮胎卡片
        cw, ch = crop.size
        target_ratio = tw / th
        if cw / ch > target_ratio:
            nw = round(ch * target_ratio)
            x0 = (cw - nw) // 2
            crop = crop.crop((x0, 0, x0 + nw, ch))
        else:
            nh = round(cw / target_ratio)
            y0 = (ch - nh) // 2
            crop = crop.crop((0, y0, cw, y0 + nh))
        crop = crop.resize((tw, th), Image.Resampling.LANCZOS)
        crop = ImageEnhance.Contrast(crop).enhance(1.12)
        crop = ImageEnhance.Brightness(crop).enhance(0.95)
        out = crop.convert("RGBA")
        out.putalpha(mask)
        out.save(OUT / f"{name}.png")


def make_controls():
    # 1. 拉丝微颗粒黑曜石右侧整栏底板（自带向左车库场景投射的柔和阴影，杜绝硬直角贴片感）
    dw, dh = 520, 900
    dock = Image.new("RGBA", (dw, dh), (0, 0, 0, 0))
    shadow_w = 34
    # 左缘投射到车库的柔和环境阴影
    for x in range(shadow_w):
        t = x / max(1, shadow_w - 1)
        a = round(145 * (t * t))
        ImageDraw.Draw(dock).line((x, 0, x, dh), fill=(6, 8, 12, a))
    # 右侧哑光拉丝面板主体（顶部略暖微光，底部沉稳黑曜石）
    body = Image.new("RGBA", (dw - shadow_w, dh), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(body)
    for y in range(dh):
        t = y / max(1, dh - 1)
        r = round(21 * (1 - t) + 12 * t)
        g = round(26 * (1 - t) + 15 * t)
        b = round(35 * (1 - t) + 22 * t)
        bdraw.line((0, y, dw - shadow_w, y), fill=(r, g, b, 249))
    body = _apply_micrograin(body, strength=3, seed=101)
    # 面板左缘 1px 冷钢高光棱线 + 顶栏分割细线
    ImageDraw.Draw(body).line((0, 0, 0, dh), fill=(64, 76, 98, 210), width=1)
    dock.paste(body, (shadow_w, 0), body)
    dock.save(OUT / "dock-surface.png")

    # 2. 拉丝黑曜石底部序号通栏（带顶部高光细棱与微颗粒质感）
    fw, fh = 1280, 96
    foot = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(foot)
    for y in range(fh):
        t = y / max(1, fh - 1)
        r = round(17 * (1 - t) + 10 * t)
        g = round(21 * (1 - t) + 13 * t)
        b = round(29 * (1 - t) + 19 * t)
        fdraw.line((0, y, fw, y), fill=(r, g, b, 252))
    foot = _apply_micrograin(foot, strength=3, seed=202)
    ImageDraw.Draw(foot).line((0, 0, fw, 0), fill=(72, 84, 108, 220), width=1)
    ImageDraw.Draw(foot).line((0, 1, fw, 1), fill=(255, 255, 255, 18), width=1)
    foot.save(OUT / "footer-surface.png")

    # 3. 顶部毛玻璃深色导览胶囊（复刻参考图「改装车辆 / 试车场 / 我的方案」背后深透玻璃条）
    nw, nh = 560, 76
    nav = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
    nd = ImageDraw.Draw(nav)
    for y in range(nh):
        t = y / max(1, nh - 1)
        a = round(168 * (1 - t) + 128 * t)
        nd.line((0, y, nw, y), fill=(13, 17, 25, a))
    nav = _apply_micrograin(nav, strength=2, seed=303)
    # 顶部与底部分别做水平渐隐，融合进车库顶部阴影
    nmask = Image.new("L", (nw, nh), 255)
    npx = nmask.load()
    for y in range(nh):
        for x in range(nw):
            fade_l = min(1.0, x / 42.0)
            fade_r = min(1.0, (nw - 1 - x) / 68.0)
            npx[x, y] = round(255 * fade_l * fade_r)
    nav.putalpha(ImageChops.multiply(nav.getchannel("A"), nmask))
    ImageDraw.Draw(nav).line((36, nh - 1, nw - 60, nh - 1), fill=(95, 110, 138, 70), width=1)
    nav.save(OUT / "top-nav-glass.png")

    # 4. 左下角毛玻璃当前车辆信息底卡（复刻参考图左下角半透深玻卡）
    sw, sh = 560, 132
    strip = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)
    for x in range(sw):
        t = x / max(1, sw - 1)
        a = round(176 * (1 - t * 0.72))
        sd.line((x, 2, x, sh - 2), fill=(12, 16, 24, a))
    strip = _apply_micrograin(strip, strength=2, seed=404)
    ImageDraw.Draw(strip).line((0, 2, round(sw * 0.78), 2), fill=(120, 138, 168, 95), width=1)
    strip.save(OUT / "car-strip-glass.png")

    # 5. 右下角斜切装饰角标（复刻参考图右下角斜边「设计方案」工业铭牌质感）
    cw, ch = 220, 56
    corner = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    cd = ImageDraw.Draw(corner)
    pts = [(26, 2), (cw, 2), (cw, ch), (0, ch)]
    cd.polygon(pts, fill=(20, 26, 36, 225))
    cd.line([(0, ch), (26, 2), (cw, 2)], fill=(78, 92, 118, 165), width=2)
    corner.save(OUT / "footer-corner-tag.png")

    # 6. 地面暖金落日反射柔光 + 车身底部深色接地暗晕（让 3D 实车与车库地面融为一体）
    gw, gh = 760, 260
    glow = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    # 宽幅暖金落日地面反光（贴近车头底部和两侧湿润水泥反光）
    gdraw.ellipse((40, 48, gw - 40, gh - 16), fill=(235, 135, 42, 48))
    gdraw.ellipse((120, 74, gw - 140, gh - 34), fill=(250, 165, 68, 42))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=34))
    # 车底核心接地深阴影（压实轮胎与底盘下方，彻底消除悬浮感）
    ao = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    ad = ImageDraw.Draw(ao)
    ad.ellipse((150, 88, gw - 150, gh - 74), fill=(4, 5, 8, 185))
    ad.ellipse((210, 104, gw - 210, gh - 86), fill=(2, 3, 5, 220))
    ao = ao.filter(ImageFilter.GaussianBlur(radius=20))
    glow.alpha_composite(ao)
    glow.save(OUT / "floor-warm-bounce.png")

    # 7. 右侧卡片（未选中：微颗粒深金属 + 顶部微高光棱；选中：暖琥珀金柔光晕 + 渐变微光底）
    w, h = 680, 152
    r = 14
    pad = 12

    card_idle = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(base)
    for y in range(pad, h - pad):
        t = (y - pad) / max(1, h - 2 * pad - 1)
        cr = round(28 * (1 - t) + 19 * t)
        cg = round(34 * (1 - t) + 23 * t)
        cb = round(45 * (1 - t) + 32 * t)
        bd.line((pad, y, w - pad, y), fill=(cr, cg, cb, 236))
    cmask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(cmask).rounded_rectangle((pad, pad, w - pad, h - pad), radius=r, fill=255)
    card_idle.paste(base, (0, 0), cmask)
    card_idle = _apply_micrograin(card_idle, strength=3, seed=505)
    d = ImageDraw.Draw(card_idle)
    d.rounded_rectangle((pad, pad, w - pad, h - pad), radius=r, outline=(74, 88, 112, 195), width=2)
    d.line((pad + r, pad + 2, w - pad - r, pad + 2), fill=(255, 255, 255, 28), width=1)
    card_idle.save(OUT / "card-idle.png")

    card_active = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    gd.rounded_rectangle((pad, pad, w - pad, h - pad), radius=r, outline=(248, 178, 62, 230), width=10)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=9))
    card_active.alpha_composite(glow_layer)

    abg = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    abd = ImageDraw.Draw(abg)
    for y in range(pad, h - pad):
        t = (y - pad) / max(1, h - 2 * pad - 1)
        cr = round(56 * (1 - t) + 34 * t)
        cg = round(44 * (1 - t) + 28 * t)
        cb = round(29 * (1 - t) + 22 * t)
        abd.line((pad, y, w - pad, y), fill=(cr, cg, cb, 244))
    abg = _apply_micrograin(abg, strength=3, seed=606)
    card_active.paste(abg, (0, 0), cmask)
    d = ImageDraw.Draw(card_active)
    d.rounded_rectangle((pad, pad, w - pad, h - pad), radius=r, outline=(248, 184, 72, 255), width=3)
    d.line((pad + r, pad + 3, w - pad - r, pad + 3), fill=(255, 224, 150, 85), width=1)
    card_active.save(OUT / "card-active.png")

    # 8. 左缘厚实毛玻璃悬浮页签（复刻参考图「前轮 / 制动」真实磨砂玻璃 + 暖橙左侧发光灯柱）
    tw, th = 320, 114
    tab_on = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    for x in range(tw):
        t = x / max(1, tw - 1)
        alpha = round(232 * (1.0 - t * 0.16))
        cr = round(68 * (1 - t) + 24 * t)
        cg = round(48 * (1 - t) + 26 * t)
        cb = round(24 * (1 - t) + 34 * t)
        ImageDraw.Draw(tab_on).line((x, 8, x, th - 8), fill=(cr, cg, cb, alpha))
    tab_on = _apply_micrograin(tab_on, strength=3, seed=707)
    tmask = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(tmask).rounded_rectangle((4, 8, tw - 6, th - 8), radius=10, fill=255)
    tab_on.putalpha(ImageChops.multiply(tab_on.getchannel("A"), tmask))
    tglow = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    ImageDraw.Draw(tglow).rounded_rectangle((2, 12, 20, th - 12), radius=6, fill=(250, 174, 54, 240))
    tglow = tglow.filter(ImageFilter.GaussianBlur(radius=9))
    tab_on.alpha_composite(tglow)
    td = ImageDraw.Draw(tab_on)
    td.rounded_rectangle((4, 10, 14, th - 10), radius=4, fill=(252, 188, 72, 255))
    td.rounded_rectangle((4, 8, tw - 6, th - 8), radius=10, outline=(245, 178, 66, 130), width=2)
    tab_on.save(OUT / "left-tab-active.png")

    tab_off = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    for x in range(tw):
        t = x / max(1, tw - 1)
        alpha = round(212 * (1.0 - t * 0.15))
        ImageDraw.Draw(tab_off).line((x, 8, x, th - 8), fill=(18, 23, 32, alpha))
    tab_off = _apply_micrograin(tab_off, strength=2, seed=808)
    tab_off.putalpha(ImageChops.multiply(tab_off.getchannel("A"), tmask))
    ImageDraw.Draw(tab_off).rounded_rectangle((4, 8, tw - 6, th - 8), radius=10, outline=(74, 88, 112, 125), width=2)
    tab_off.save(OUT / "left-tab-idle.png")

    # 9. 实心缎面琥珀金主行动按钮 + 细描边拉丝暗钢次按钮
    bw, bh = 440, 112
    bpad = 6
    bmask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(bmask).rounded_rectangle((bpad, bpad, bw - bpad, bh - bpad), radius=12, fill=255)
    for name, top_c, bot_c, border_c, top_hl in (
        ("btn-primary", (248, 182, 68, 255), (226, 148, 40, 255), (255, 208, 112, 255), (255, 236, 180, 120)),
        ("btn-primary-hover", (255, 196, 86, 255), (240, 166, 56, 255), (255, 226, 152, 255), (255, 245, 205, 155)),
        ("btn-ghost", (26, 32, 43, 240), (17, 21, 30, 244), (78, 92, 116, 235), (255, 255, 255, 36)),
        ("btn-ghost-hover", (52, 42, 28, 245), (34, 28, 20, 248), (245, 178, 66, 255), (255, 215, 130, 65)),
    ):
        btn = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        # 按钮下方柔和落地阴影
        sh_img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        ImageDraw.Draw(sh_img).rounded_rectangle((bpad, bpad + 3, bw - bpad, bh - bpad + 3), radius=12, fill=(0, 0, 0, 120))
        sh_img = sh_img.filter(ImageFilter.GaussianBlur(radius=4))
        btn.alpha_composite(sh_img)
        grad = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        for y in range(bh):
            t = y / max(1, bh - 1)
            col = tuple(round(top_c[i] * (1 - t) + bot_c[i] * t) for i in range(4))
            ImageDraw.Draw(grad).line((0, y, bw, y), fill=col)
        grad = _apply_micrograin(grad, strength=3, seed=909)
        btn.paste(grad, (0, 0), bmask)
        bd = ImageDraw.Draw(btn)
        bd.rounded_rectangle((bpad, bpad, bw - bpad, bh - bpad), radius=12, outline=border_c, width=2)
        bd.line((bpad + 14, bpad + 2, bw - bpad - 14, bpad + 2), fill=top_hl, width=1)
        btn.save(OUT / f"{name}.png")

    # 10. 发光单选指示圆环（idle / installed / active）
    def make_radio(kind):
        s = 128
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        if kind == "active":
            g = Image.new("RGBA", (s, s), (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse((22, 22, s - 22, s - 22), outline=(250, 182, 66, 235), width=16)
            img.alpha_composite(g.filter(ImageFilter.GaussianBlur(radius=10)))
            d = ImageDraw.Draw(img)
            d.ellipse((24, 24, s - 24, s - 24), fill=(36, 28, 16, 230), outline=(250, 186, 74, 255), width=8)
            d.ellipse((46, 46, s - 46, s - 46), fill=(255, 206, 108, 255))
        elif kind == "installed":
            d = ImageDraw.Draw(img)
            d.ellipse((24, 24, s - 24, s - 24), fill=(22, 28, 38, 230), outline=(146, 166, 198, 235), width=7)
            d.ellipse((48, 48, s - 48, s - 48), fill=(235, 242, 252, 245))
        else:
            d = ImageDraw.Draw(img)
            d.ellipse((24, 24, s - 24, s - 24), fill=(18, 22, 30, 160), outline=(104, 118, 144, 215), width=6)
        return img.resize((48, 48), Image.Resampling.LANCZOS)

    for k in ("idle", "installed", "active"):
        make_radio(k).save(OUT / f"radio-{k}.png")

    # 11. 底部步骤圆环（激活实心琥珀金 / 未激活细描边暗环）
    for active in (True, False):
        s = 160
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        if active:
            g = Image.new("RGBA", (s, s), (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse((26, 26, s - 26, s - 26), fill=(250, 178, 60, 185))
            img.alpha_composite(g.filter(ImageFilter.GaussianBlur(radius=14)))
            ImageDraw.Draw(img).ellipse((28, 28, s - 28, s - 28), fill=(246, 176, 62, 255), outline=(255, 220, 138, 230), width=4)
        else:
            ImageDraw.Draw(img).ellipse((28, 28, s - 28, s - 28), fill=(16, 20, 28, 230), outline=(92, 104, 128, 215), width=5)
        img.resize((56, 56), Image.Resampling.LANCZOS).save(OUT / f"step-{'active' if active else 'idle'}.png")

    # 12. 通用悬浮黑曜石磨砂面板底卡（微颗粒哑光渐变 + 柔和投影 + 顶部 1px 冷钢微光棱）
    pw, ph, ppad, pr = 760, 680, 14, 12
    panel = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    psh = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    ImageDraw.Draw(psh).rounded_rectangle((ppad, ppad + 4, pw - ppad, ph - ppad + 4), radius=pr, fill=(2, 4, 8, 165))
    panel.alpha_composite(psh.filter(ImageFilter.GaussianBlur(radius=10)))
    pgrad = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pgrad)
    for y in range(ppad, ph - ppad):
        t = (y - ppad) / max(1, ph - 2 * ppad - 1)
        cr = round(21 * (1 - t) + 12 * t)
        cg = round(26 * (1 - t) + 15 * t)
        cb = round(36 * (1 - t) + 22 * t)
        pdraw.line((ppad, y, pw - ppad, y), fill=(cr, cg, cb, 236))
    pgrad = _apply_micrograin(pgrad, strength=3, seed=1101)
    pmask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(pmask).rounded_rectangle((ppad, ppad, pw - ppad, ph - ppad), radius=pr, fill=255)
    panel.paste(pgrad, (0, 0), pmask)
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle((ppad, ppad, pw - ppad, ph - ppad), radius=pr, outline=(74, 88, 114, 195), width=2)
    pd.line((ppad + pr, ppad + 2, pw - ppad - pr, ppad + 2), fill=(255, 255, 255, 34), width=1)
    panel.save(OUT / "panel-obsidian.png")

    # 13. 顶部拉丝黑曜石通栏（与 footer-surface 镜像对称，用于调校/结算/暂停顶栏）
    tw, th = 1280, 108
    topbar = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(topbar)
    for y in range(th):
        t = y / max(1, th - 1)
        cr = round(14 * (1 - t) + 20 * t)
        cg = round(17 * (1 - t) + 24 * t)
        cb = round(24 * (1 - t) + 33 * t)
        tdraw.line((0, y, tw, y), fill=(cr, cg, cb, 238))
    topbar = _apply_micrograin(topbar, strength=3, seed=1202)
    ImageDraw.Draw(topbar).line((0, th - 2, tw, th - 2), fill=(255, 255, 255, 16), width=1)
    ImageDraw.Draw(topbar).line((0, th - 1, tw, th - 1), fill=(72, 84, 108, 220), width=1)
    topbar.save(OUT / "bar-top.png")


if __name__ == "__main__":
    make_icons()
    make_controls()
    grid_path = Path(r"C:\Users\15120\.gemini\antigravity\brain\06d07f29-3250-41d4-9352-9c8634a0eaa2\coastal_drive_ui_grid_1795505867729.jpg")
    make_mode_thumbnails(grid_path)
    print("Atelier tactile assets + photorealistic mode thumbnails generated in", OUT)
