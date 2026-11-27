"""ISO 8608 (GB/T 4970) A–D 级随机路面生成与 ISO 2631-1 W_k 平顺性频谱分析。"""

import math
from collections.abc import Mapping

import numpy as np
from panda3d.bullet import (
    BulletBoxShape,
    BulletRigidBodyNode,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
)
from panda3d.core import BitMask32, TransformState, Vec3

from triangle_support import TriangleSupport

ISO_ROAD_CLASSES = {
    "A": 16e-6,
    "B": 64e-6,
    "C": 256e-6,
    "D": 1024e-6,
}
_N0 = 0.1
_WAVINESS = 2.0
_N_MIN = 0.011
_N_MAX = 2.83
_HARMONIC_BANDS = 256
_G = 9.81


def generate_iso_road_profile(
    *,
    road_class: str = "C",
    length_m: float = 260.0,
    dx_m: float = 0.08,
    seed: int = 0,
    flat_lead_m: float = 10.0,
    track_coherence: float = 0.85,
) -> dict:
    """合成满足 ISO 8608 空间功率谱 Gq(n)=Gq(n0)*(n/n0)^(-2) 的左右轮迹高程剖面。"""
    key = str(road_class).upper()
    if key not in ISO_ROAD_CLASSES:
        raise ValueError(f"未知 ISO 路面等级：{road_class}，须为 A/B/C/D")
    if length_m <= flat_lead_m or dx_m <= 0.0:
        raise ValueError("路面长度须大于平直引导段且采样步距须为正")

    gq_n0 = ISO_ROAD_CLASSES[key]
    rho = float(np.clip(track_coherence, 0.0, 1.0))

    # 对数等比划分频率带，使低频陡峭段 1/n² 积分与理论方差高度一致。
    edges = np.geomspace(_N_MIN, _N_MAX, _HARMONIC_BANDS + 1)
    dn = np.diff(edges)
    nk = np.sqrt(edges[:-1] * edges[1:])
    gq = gq_n0 * (nk / _N0) ** (-_WAVINESS)
    amps = np.sqrt(2.0 * gq * dn)
    theoretical_rms = float(np.sqrt(np.sum(gq * dn)))

    rng = np.random.default_rng(int(seed))
    phase1 = rng.uniform(0.0, 2.0 * math.pi, size=_HARMONIC_BANDS)
    phase2 = rng.uniform(0.0, 2.0 * math.pi, size=_HARMONIC_BANDS)

    count = math.floor(length_m / dx_m) + 1
    y_m = np.arange(count, dtype=float) * dx_m
    arg = 2.0 * math.pi * nk[:, None] * y_m[None, :]
    q1 = np.sum(amps[:, None] * np.cos(arg + phase1[:, None]), axis=0)
    q2 = np.sum(amps[:, None] * np.cos(arg + phase2[:, None]), axis=0)

    q_left = q1
    q_right = rho * q1 + math.sqrt(max(0.0, 1.0 - rho * rho)) * q2

    # 起点前 4 m 严格为 0.0，保证 settle_initial 与初速赋予处于完美水平面。
    lead_end = max(4.0, float(flat_lead_m))
    ramp = np.ones_like(y_m)
    ramp[y_m <= 4.0] = 0.0
    trans = (y_m > 4.0) & (y_m < lead_end)
    if lead_end > 4.0 and np.any(trans):
        ramp[trans] = 0.5 * (1.0 - np.cos(math.pi * (y_m[trans] - 4.0) / (lead_end - 4.0)))

    z_left = q_left * ramp
    z_right = q_right * ramp
    eval_mask = y_m >= lead_end
    measured_left_rms = float(np.sqrt(np.mean((z_left[eval_mask] - np.mean(z_left[eval_mask])) ** 2)))
    measured_right_rms = float(np.sqrt(np.mean((z_right[eval_mask] - np.mean(z_right[eval_mask])) ** 2)))

    return {
        "road_class": key,
        "gq_n0": gq_n0,
        "length_m": float(y_m[-1]),
        "dx_m": float(dx_m),
        "flat_lead_m": lead_end,
        "track_coherence": rho,
        "seed": int(seed),
        "y_m": y_m,
        "z_left_m": z_left,
        "z_right_m": z_right,
        "ramp": ramp,
        "theoretical_rms_m": theoretical_rms,
        "measured_left_rms_m": measured_left_rms,
        "measured_right_rms_m": measured_right_rms,
    }


def install_iso_road(
    simulation,
    *,
    road_class: str = "C",
    length_m: float = 260.0,
    width_m: float = 8.0,
    dx_m: float = 0.08,
    seed: int = 0,
) -> dict:
    """在实验场原点前方构建并挂载 ISO 随机路面刚体（独立簧下用双精度解析板元，刚体悬架用三角网格）。"""
    effective_dx = max(float(dx_m), 0.35) if simulation.config.unsprung_enabled else float(dx_m)
    profile = generate_iso_road_profile(
        road_class=road_class,
        length_m=length_m,
        dx_m=effective_dx,
        seed=seed,
    )
    origin = simulation.player.reference_pose().getPos()
    ox, oy = float(origin.x), float(origin.y)

    # 在 4..10 m 引导段同步抬升基底高度，避免随机波谷跌破 z=0 被 test-ground 平面遮挡。
    min_q = float(min(np.min(profile["z_left_m"]), np.min(profile["z_right_m"])))
    base_offset = max(0.0, -min_q) + 0.005
    z_left = profile["z_left_m"] + base_offset * profile["ramp"]
    z_right = profile["z_right_m"] + base_offset * profile["ramp"]

    y_vals = oy + profile["y_m"]
    half_w = 0.5 * float(width_m)
    start_row = next((i for i, yv in enumerate(profile["y_m"]) if yv >= max(0.0, profile["flat_lead_m"] - 1.0)), 0)

    if simulation.config.unsprung_enabled:
        # 单精度 Panda3D Bullet 下 btGjkEpaSolver2 存在 float32 ULP 台阶噪声；
        # 独立轮心采用零 margin 解析长方体板元，由 64 位双精度 box_section 连续精确求交。
        hz = 0.04
        track_half_w = max(1.0, 0.25 * float(width_m))
        track_centers = ((ox - track_half_w, z_left), (ox + track_half_w, z_right))
        slabs_per_body = 6
        element_count = 0
        for side_idx, (cx, z_arr) in enumerate(track_centers):
            indices = list(range(start_row, len(y_vals) - 1))
            for chunk_idx in range(0, len(indices), slabs_per_body):
                chunk = indices[chunk_idx : chunk_idx + slabs_per_body]
                body = BulletRigidBodyNode(f"lab-iso-rough-road-{side_idx}-{chunk_idx}")
                y_start = float(y_vals[chunk[0]])
                y_end = float(y_vals[chunk[-1] + 1])
                y_ref = 0.5 * (y_start + y_end)
                for idx in chunk:
                    y0, y1 = float(y_vals[idx]), float(y_vals[idx + 1])
                    z0, z1 = float(z_arr[idx]), float(z_arr[idx + 1])
                    dy, dz = y1 - y0, z1 - z0
                    chord = math.hypot(dy, dz)
                    theta = math.atan2(dz, dy)
                    shape = BulletBoxShape(Vec3(track_half_w, 0.5 * chord, hz))
                    shape.setMargin(0.0)
                    ym = 0.5 * (y0 + y1) + hz * math.sin(theta) - y_ref
                    zm = 0.5 * (z0 + z1) - hz * math.cos(theta)
                    ts = TransformState.makePosHpr(Vec3(0.0, ym, zm), Vec3(0.0, math.degrees(theta), 0.0))
                    body.addShape(shape, ts)
                    element_count += 1
                body.setTransform(TransformState.makePos(Vec3(cx, y_ref, 0.0)))
                body.setPythonTag("y_span", (y_start - 0.5, y_end + 0.5))
                body.setIntoCollideMask(BitMask32(7))
                simulation._world.attachRigidBody(body)
                simulation._prop_bodies.append(body)
        triangle_count = element_count
    else:
        xs = (ox - half_w, ox - 0.35, ox + 0.35, ox + half_w)
        mesh_margin = 0.01
        mesh = BulletTriangleMesh()
        triangles = []
        for idx in range(start_row, len(y_vals) - 1):
            y0, y1 = float(y_vals[idx]), float(y_vals[idx + 1])
            zl0, zl1 = float(z_left[idx] - mesh_margin), float(z_left[idx + 1] - mesh_margin)
            zr0, zr1 = float(z_right[idx] - mesh_margin), float(z_right[idx + 1] - mesh_margin)
            row0 = ((xs[0], y0, zl0), (xs[1], y0, zl0), (xs[2], y0, zr0), (xs[3], y0, zr0))
            row1 = ((xs[0], y1, zl1), (xs[1], y1, zl1), (xs[2], y1, zr1), (xs[3], y1, zr1))
            for col in range(3):
                p00, p10 = row0[col], row0[col + 1]
                p11, p01 = row1[col + 1], row1[col]
                tri1 = (p00, p10, p11)
                tri2 = (p00, p11, p01)
                mesh.addTriangle(Vec3(*p00), Vec3(*p10), Vec3(*p11))
                mesh.addTriangle(Vec3(*p00), Vec3(*p11), Vec3(*p01))
                triangles.append(tri1)
                triangles.append(tri2)

        shape = BulletTriangleMeshShape(mesh, dynamic=False)
        shape.setMargin(mesh_margin)
        body = BulletRigidBodyNode("lab-iso-rough-road")
        body.addShape(shape)
        body.setPythonTag("suspension_mesh", TriangleSupport.build(triangles))
        body.setIntoCollideMask(BitMask32(7))
        simulation._world.attachRigidBody(body)
        simulation._prop_bodies.append(body)
        triangle_count = len(triangles)

    return {
        "road_class": profile["road_class"],
        "gq_n0": profile["gq_n0"],
        "length_m": profile["length_m"],
        "width_m": float(width_m),
        "dx_m": profile["dx_m"],
        "seed": profile["seed"],
        "flat_lead_m": profile["flat_lead_m"],
        "base_offset_m": base_offset,
        "theoretical_rms_m": profile["theoretical_rms_m"],
        "measured_left_rms_m": profile["measured_left_rms_m"],
        "measured_right_rms_m": profile["measured_right_rms_m"],
        "triangle_count": triangle_count,
    }


def iso2631_wk_complex(freqs_hz: np.ndarray) -> np.ndarray:
    """ISO 2631-1:1997 垂向全身振动频率加权传递函数 W_k(s) = H_h * H_l * H_t * H_s。"""
    freqs = np.asarray(freqs_hz, dtype=float)
    result = np.zeros(freqs.shape, dtype=np.complex128)
    mask = freqs > 0.0
    if not np.any(mask):
        return result

    s = 1j * 2.0 * math.pi * freqs[mask]
    w1 = 2.0 * math.pi * 0.4
    w2 = 2.0 * math.pi * 100.0
    w3 = 2.0 * math.pi * 12.5
    w4 = 2.0 * math.pi * 12.5
    q4 = 0.63
    w5 = 2.0 * math.pi * 2.37
    q5 = 0.91
    w6 = 2.0 * math.pi * 3.35
    q6 = 0.91

    hh = (s * s) / (s * s + math.sqrt(2.0) * w1 * s + w1 * w1)
    hl = (w2 * w2) / (s * s + math.sqrt(2.0) * w2 * s + w2 * w2)
    ht = (1.0 + s / w3) / (1.0 + s / (q4 * w4) + (s / w4) ** 2)
    hs = (s * s + (w5 / q5) * s + w5 * w5) / (s * s + (w6 / q6) * s + w6 * w6)
    result[mask] = hh * hl * ht * hs
    return result


def iso2631_wk_gain(freqs_hz: np.ndarray) -> np.ndarray:
    """ISO 2631-1 W_k(f) 幅频增益 |W_k(j 2π f)|。"""
    return np.abs(iso2631_wk_complex(freqs_hz))


def iso2631_wk_weighted_rms(az_mps2, fs: float = 120.0) -> tuple[float, np.ndarray]:
    """对垂向加速度时程去均值并经 W_k 频域加权，返回 (awz_rms, awz_series)。"""
    signal = np.asarray(az_mps2, dtype=float)
    if signal.size == 0:
        return 0.0, np.empty(0, dtype=float)
    centered = signal - float(np.mean(signal))
    freqs = np.fft.rfftfreq(centered.size, d=1.0 / float(fs))
    weighted = np.fft.irfft(np.fft.rfft(centered) * iso2631_wk_complex(freqs), n=centered.size)
    rms = float(np.sqrt(np.mean(weighted * weighted)))
    return rms, weighted


def subjective_discomfort_label(awz_rms: float) -> str:
    """对照《汽车理论》表 6-2 / ISO 2631-1 给出加权加速度均方根的主观舒适度分级。"""
    val = float(awz_rms)
    if val < 0.315:
        return "没有不舒适 (<0.315 m/s²)"
    if val < 0.63:
        return "有一点不舒适 (0.315~0.63 m/s²)"
    if val < 1.0:
        return "比较不舒适 (0.5~1.0 m/s²)"
    if val < 1.6:
        return "不舒适 (0.8~1.6 m/s²)"
    if val < 2.5:
        return "很不舒适 (1.25~2.5 m/s²)"
    return "极不舒适 (>2.0 m/s²)"


def _smoothed_psd(signal: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Welch 平均周期图（50% 重叠 Hann 窗）；短序列自动退化为全长平滑周期图。"""
    x = signal - float(np.mean(signal))
    n = x.size
    if n < 8:
        return np.zeros(0, dtype=float), np.zeros(0, dtype=float)
    seg_len = 256 if n >= 512 else (128 if n >= 256 else n)
    step = max(1, seg_len // 2)
    window = np.hanning(seg_len)
    norm = float(fs * np.sum(window * window))
    starts = list(range(0, max(1, n - seg_len + 1), step))
    acc = np.zeros(seg_len // 2 + 1, dtype=float)
    for start in starts:
        seg = x[start : start + seg_len]
        if seg.size < seg_len:
            seg = np.pad(seg, (0, seg_len - seg.size))
        spec = np.fft.rfft(seg * window)
        psd = (np.abs(spec) ** 2) / norm
        if psd.size > 2:
            psd[1:-1] *= 2.0
        acc += psd
    avg = acc / len(starts)
    if avg.size >= 5:
        avg = np.convolve(avg, np.array((0.2, 0.6, 0.2)), mode="same")
    freqs = np.fft.rfftfreq(seg_len, d=1.0 / float(fs))
    return freqs, avg


def _band_peak_hz(freqs: np.ndarray, psd: np.ndarray, low_hz: float, high_hz: float) -> float | None:
    if freqs.size == 0 or psd.size == 0:
        return None
    mask = (freqs >= low_hz) & (freqs <= high_hz)
    if not np.any(mask):
        return None
    band_freqs = freqs[mask]
    band_psd = psd[mask]
    return float(band_freqs[int(np.argmax(band_psd))])


def rough_road_ride_analysis(samples, config, *, warmup_s: float = 0.6, fs: float = 120.0) -> dict:
    """分析随机路面平顺性：ISO 2631-1 W_k 加权 RMS、簧载/非簧载双峰 PSD 与相对动载。"""
    empty = {
        "status": "unavailable",
        "note": "有效采样不足，无法进行平顺性频谱分析",
        "awz_rms_mps2": None,
        "discomfort_level": None,
        "unweighted_az_rms_mps2": None,
        "sprung_peak_hz": None,
        "unsprung_peak_hz": None,
        "dynamic_load_ratio_fl": None,
        "suspension_travel_rms_mm": None,
        "freqs_hz": np.zeros(0, dtype=float),
        "sprung_psd": np.zeros(0, dtype=float),
        "unsprung_psd": np.zeros(0, dtype=float),
    }
    seq = list(samples)
    if len(seq) < 32:
        return empty

    is_mapping = isinstance(seq[0], Mapping)
    if is_mapping and "time" in seq[0] and seq[0]["time"] is not None:
        start_idx = next((i for i, row in enumerate(seq) if float(row["time"]) >= warmup_s), len(seq))
    else:
        start_idx = round(warmup_s * fs)
    start_idx = max(1, min(len(seq), start_idx))
    tail = seq[start_idx:]
    if len(tail) < 32:
        return empty

    sprung_az = []
    hub_az_fl = []
    travel_fl = []
    load_fl = []

    if is_mapping:
        for row in tail:
            az = row.get("sprung_az")
            if az is None:
                az = row.get("az")
            if az is not None:
                sprung_az.append(float(az))
            haz = row.get("hub_az_fl")
            if haz is not None:
                hub_az_fl.append(float(haz))
            trv = row.get("travel_fl")
            if trv is not None:
                travel_fl.append(float(trv))
            ld = row.get("load_fl")
            if ld is None:
                ld = row.get("sample_load_fl")
            if ld is not None:
                load_fl.append(float(ld))
        if not sprung_az:
            vzs = [float(row["sprung_vz"]) for row in seq[start_idx - 1 :] if row.get("sprung_vz") is not None]
            if len(vzs) >= 33:
                sprung_az = list(np.diff(np.asarray(vzs, dtype=float)) * fs)
        static_load = seq[0].get("load_fl") or seq[0].get("sample_load_fl")
    else:
        for idx, snap in enumerate(tail, start=start_idx):
            player = snap.player
            unsprung = player.unsprung_state
            if unsprung is not None and unsprung.sprung_acceleration is not None:
                sprung_az.append(float(unsprung.sprung_acceleration[2]))
                if unsprung.wheel_accelerations is not None:
                    hub_az_fl.append(float(unsprung.wheel_accelerations[0][2]))
            else:
                prev_vz = float(seq[idx - 1].player.velocity[2])
                curr_vz = float(player.velocity[2])
                sprung_az.append((curr_vz - prev_vz) * fs)
            if player.wheel_contacts:
                travel_fl.append(float(player.wheel_contacts[0].compression))
            if player.wheel_dynamics:
                load_fl.append(float(player.wheel_dynamics[0].normal_load))
        p0 = seq[0].player
        static_load = p0.wheel_dynamics[0].normal_load if p0.wheel_dynamics else None

    if len(sprung_az) < 32:
        return empty

    az_arr = np.asarray(sprung_az, dtype=float)
    awz_rms, _ = iso2631_wk_weighted_rms(az_arr, fs=fs)
    unweighted_rms = float(np.sqrt(np.mean((az_arr - np.mean(az_arr)) ** 2)))
    freqs, sprung_psd = _smoothed_psd(az_arr, fs)
    sprung_peak = _band_peak_hz(freqs, sprung_psd, 0.5, 4.0)

    if len(hub_az_fl) >= 32:
        _, unsprung_psd = _smoothed_psd(np.asarray(hub_az_fl, dtype=float), fs)
        unsprung_peak = _band_peak_hz(freqs, unsprung_psd, 6.0, 25.0)
    else:
        unsprung_psd = np.zeros(0, dtype=float)
        unsprung_peak = None

    g0 = float(static_load) if static_load is not None and float(static_load) > 0.0 else (
        0.5 * float(config.mass) * _G * float(config.front_weight_share)
    )
    dynamic_load_ratio = (
        float(np.std(np.asarray(load_fl, dtype=float)) / g0)
        if len(load_fl) >= 16 and g0 > 0.0
        else None
    )
    travel_rms_mm = (
        float(np.std(np.asarray(travel_fl, dtype=float)) * 1000.0)
        if len(travel_fl) >= 16
        else None
    )

    return {
        "status": "available",
        "note": f"跳过前 {warmup_s:g} s 起步瞬态后按 {fs:g} Hz 计算 W_k 加权 RMS 与双峰 PSD",
        "awz_rms_mps2": awz_rms,
        "discomfort_level": subjective_discomfort_label(awz_rms),
        "unweighted_az_rms_mps2": unweighted_rms,
        "sprung_peak_hz": sprung_peak,
        "unsprung_peak_hz": unsprung_peak,
        "dynamic_load_ratio_fl": dynamic_load_ratio,
        "suspension_travel_rms_mm": travel_rms_mm,
        "freqs_hz": freqs,
        "sprung_psd": sprung_psd,
        "unsprung_psd": unsprung_psd,
    }
