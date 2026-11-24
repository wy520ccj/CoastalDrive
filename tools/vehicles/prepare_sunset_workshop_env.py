"""离线烘焙与落日海岸工坊实景（garage-sunset-workshop.png）光影方向完全一致的 360° HDRI 环境反射贴图。"""

import math
from pathlib import Path

from panda3d.core import Filename, PfmFile, Texture, Vec3
from simplepbr.envmap import EnvMap

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "assets/game/vehicles/garage-sunset-workshop.env"


def _sample_sunset_workshop(x: float, y: float, z: float) -> Vec3:
    """根据世界方向 (x, y, z) 计算落日车库物理辐射度（HDR 线性空间）。

    在 WorkshopVehicle 前左 3/4 视角（相机位于 (-X, +Y) 朝向原点）下：
    - 画面右侧（敞开落日海岸卷帘门）对应 (+X, -Y) 方向；
    - 画面左侧（工具墙与爱迪生暖光吊灯）对应 (-X, +Y) 与 (-X, -Y) 方向；
    - 上方 (+Z) 为深暗工业钢梁车库顶棚；
    - 下方 (-Z) 为深色抛光水泥地面与落日暖金地面反光。
    """
    length = math.sqrt(x * x + y * y + z * z) or 1.0
    dx, dy, dz = x / length, y / length, z / length

    # 基础室内暗棚氛围（极低亮度，保证车漆和车窗拥有深沉高级对比）
    r, g, b = 0.032, 0.036, 0.048

    # 1. 顶部钢梁顶棚：保持深沉暗棚基调，让机盖和车顶呈现参考图那样油润深邃的镜面车漆对比
    if dz > 0.08:
        truss = 0.5 + 0.5 * math.cos(dx * 16.0 + dy * 8.0)
        roof = 0.018 + 0.016 * truss
        r, g, b = roof * 0.92, roof * 0.96, roof * 1.15

    # 2. 右侧敞开卷帘门落日海景（偏右后方 (+0.92, -0.38) 开口，主高光掠过车身侧面与轮眉而非把机盖正面洗白）
    bay_dir_x, bay_dir_y = 0.92, -0.38
    bay_align = dx * bay_dir_x + dy * bay_dir_y
    if bay_align > 0.36 and -0.16 < dz < 0.34:
        # 门框软边缘过渡
        horiz_mask = min(1.0, (bay_align - 0.36) / 0.18)
        top_mask = min(1.0, (0.34 - dz) / 0.10)
        bot_mask = min(1.0, (dz + 0.16) / 0.08)
        bay_mask = horiz_mask * top_mask * bot_mask
        # 中间黑色门柱遮挡，形成参考图那种真实车库分段高光反射！
        pillar = abs(dx * 0.38 + dy * 0.92 - 0.04)
        if pillar < 0.075:
            bay_mask *= max(0.0, (pillar - 0.045) / 0.03)

        if dz >= 0.02:
            # 落日海平线（炽暖琥珀金）→ 高空晚霞（暖橙渐入深暮蓝）
            t = min(1.0, (dz - 0.02) / 0.32)
            sky_r = 2.85 * ((1.0 - t) ** 1.7) + 0.24 * t
            sky_g = 1.25 * ((1.0 - t) ** 2.1) + 0.18 * t
            sky_b = 0.38 * ((1.0 - t) ** 2.4) + 0.30 * t
            # 落日低角核心高光，锐利勾勒侧翼子板、轮毂与车顶边缘线
            sun_dot = max(0.0, dx * 0.94 + dy * (-0.30) + dz * 0.10)
            sun_core = (sun_dot ** 32) * 5.2
            sky_r += sun_core * 1.0
            sky_g += sun_core * 0.48
            sky_b += sun_core * 0.14
        else:
            # 海面金色反光与远岸公路
            sea_t = min(1.0, (0.02 - dz) / 0.18)
            sky_r = 1.15 * (1.0 - sea_t * 0.55)
            sky_g = 0.52 * (1.0 - sea_t * 0.60)
            sky_b = 0.20 * (1.0 - sea_t * 0.40)

        r = r * (1.0 - bay_mask) + sky_r * bay_mask
        g = g * (1.0 - bay_mask) + sky_g * bay_mask
        b = b * (1.0 - bay_mask) + sky_b * bay_mask

    # 3. 左侧工坊墙面 3 盏爱迪生暖钨丝吊灯点光源 + 工作台暖橙漫反射（复刻左侧精致暖金点状反光）
    lamps = (
        (-0.82, 0.48, 0.30, 5.2),
        (-0.68, 0.68, 0.26, 4.4),
        (-0.90, 0.18, 0.24, 3.8),
    )
    for lx, ly, lz, power in lamps:
        ln = math.sqrt(lx * lx + ly * ly + lz * lz)
        dot = max(0.0, (dx * lx + dy * ly + dz * lz) / ln)
        spot = (dot ** 64) * power + (dot ** 8) * (power * 0.055)
        r += spot * 1.0
        g += spot * 0.50
        b += spot * 0.14

    # 4. 地面层：深色湿润水泥基底 + 右侧落日斜照到地面的暖橙反光（照亮车身裙边与轮毂下沿）
    if dz <= 0.0:
        floor_t = min(1.0, -dz / 0.65)
        fr, fg, fb = 0.035, 0.038, 0.046
        # 右侧落日地面拉长反光带
        floor_glow = max(0.0, bay_align) ** 2.2 * (1.0 - floor_t * 0.65)
        fr += floor_glow * 0.88
        fg += floor_glow * 0.42
        fb += floor_glow * 0.14
        # 左侧暖灯微弱地面回弹
        left_glow = max(0.0, -dx * 0.75 + dy * 0.66) ** 2.5 * (1.0 - floor_t * 0.7)
        fr += left_glow * 0.22
        fg += left_glow * 0.11
        fb += left_glow * 0.04
        mix = min(1.0, -dz / 0.10)
        r = r * (1.0 - mix) + fr * mix
        g = g * (1.0 - mix) + fg * mix
        b = b * (1.0 - mix) + fb * mix

    return Vec3(r, g, b)


def build_cube(size: int = 128) -> Texture:
    cube = Texture("sunset-workshop-hdr")
    cube.setupCubeMap(size, Texture.TFloat, Texture.FRgb16)
    for face in range(6):
        pixels = PfmFile()
        pixels.clear(size, size, 3)
        for row in range(size):
            for col in range(size):
                u = 2.0 * (col + 0.5) / size - 1.0
                v = 2.0 * (row + 0.5) / size - 1.0
                x, y, z = (
                    (1.0, v, -u),
                    (-1.0, v, u),
                    (u, 1.0, -v),
                    (u, -1.0, v),
                    (u, v, 1.0),
                    (-u, v, -1.0),
                )[face]
                pixels.setPoint3(col, row, _sample_sunset_workshop(x, y, z))
        assert cube.load(pixels, face, 0)
    cube.generateRamMipmapImages()
    return cube


def prepare(output: Path = OUTPUT, size: int = 128):
    cube = build_cube(size)
    environment = EnvMap(cube, prefiltered_size=size, prefiltered_samples=64, blocking_prepare=True)
    environment.write(Filename.fromOsSpecific(str(output)))
    print("Baked sunset workshop HDRI:", output)


if __name__ == "__main__":
    prepare()
