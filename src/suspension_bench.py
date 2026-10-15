"""线性部件台架拟合与常运动比换算；生成唯一VehicleConfig使用的轮心等效硬件。"""

import hashlib
import json
import math
from dataclasses import replace

SCHEMA = "coastal-suspension-bench-v1"
FIT_SCHEMA = "coastal-suspension-fit-v1"
WHEELS = ("FL", "FR", "RL", "RR")
KINDS = {"spring": "suspension_spring_rates",
         "compression": "suspension_compression_damping",
         "extension": "suspension_extension_damping"}
UNITS = {"spring_input": "m", "damper_input": "m/s", "force": "N", "temperature": "degC"}
DEFINITION = "positive_compression_resistance;spring_zero_at_free_length_and_zero_wheel_compression"
LIMITS = {"normalized_rms": .05, "normalized_peak": .10}


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label}须为有限数")
    return value


def fit_bench(document, base):
    """各部件独立过原点最小二乘；整序列留出只验证，不调整拟合值。"""
    if set(document) != {"schema", "source", "source_kind", "temperature_c", "units", "definition", "corners"}:
        raise ValueError("悬架台架文件字段不完整或含未知字段")
    if document["schema"] != SCHEMA or document["units"] != UNITS or document["definition"] != DEFINITION:
        raise ValueError("悬架台架版本、SI单位或零位/力方向定义不支持")
    if document["source_kind"] not in ("measured", "synthetic") or not isinstance(document["source"], str) or not document["source"].strip():
        raise ValueError("台架来源不能为空，须声明measured或synthetic")
    _number(document["temperature_c"], "台架温度")
    if set(document["corners"]) != set(WHEELS):
        raise ValueError("须逐一提供FL/FR/RL/RR部件与安装运动比")
    parameters = {field: [] for field in KINDS.values()}
    results = {}
    for wheel in WHEELS:
        corner = document["corners"][wheel]
        if set(corner) != {"spring_id", "damper_id", "spring_motion_ratio", "damper_motion_ratio", "installation_source", "rows"}:
            raise ValueError(f"{wheel}部件/安装字段不完整或含未知字段")
        for key in ("spring_id", "damper_id", "installation_source"):
            if not isinstance(corner[key], str) or not corner[key].strip():
                raise ValueError(f"{wheel}的{key}不能为空")
        for key in ("spring_motion_ratio", "damper_motion_ratio"):
            if _number(corner[key], key) <= 0:
                raise ValueError("压缩运动比须为有限正值；不支持变运动比或反向安装")
        groups = {(kind, split): [] for kind in KINDS for split in ("train", "validation")}
        series = {}
        for row in corner["rows"]:
            if set(row) != {"series", "split", "kind", "input", "force_N"} or (row["kind"], row["split"]) not in groups:
                raise ValueError("台架行须声明序列、train/validation、spring/compression/extension及输入/力")
            identity = row["kind"], row["split"]
            if not isinstance(row["series"], str) or not row["series"].strip():
                raise ValueError("台架序列名不能为空")
            if row["series"] in series and series[row["series"]] != identity:
                raise ValueError("同一台架序列不能跨拟合/验证或部件方向")
            series[row["series"]] = identity
            x, force = _number(row["input"], "台架输入"), _number(row["force_N"], "台架力")
            if (row["kind"] == "extension" and (x > 0 or force > 0)
                or row["kind"] != "extension" and (x < 0 or force < 0)):
                raise ValueError("正压缩/负伸张，记录同号的本构阻力；不支持主动或带偏置部件")
            groups[identity].append((x, force))
        results[wheel] = {}
        for kind, field in KINDS.items():
            train, validation = groups[kind, "train"], groups[kind, "validation"]
            for rows in (train, validation):
                if len({x for x, _ in rows if x != 0}) < 3:
                    raise ValueError("每个部件方向的拟合/留出均须至少三个不同的非零输入")
            # 留出必须覆盖拟合域，不能只以接近零的小输入掩盖高输入处的非线性。
            if max(abs(x) for x, _ in validation) < max(abs(x) for x, _ in train):
                raise ValueError("独立留出须覆盖拟合最大输入")
            rate = sum(x*f for x, f in train)/sum(x*x for x, _ in train)
            if rate <= 0:
                raise ValueError("当前线性部件拟合须得到正刚度/阻尼")
            ratio = corner["spring_motion_ratio" if kind == "spring" else "damper_motion_ratio"]
            parameters[field].append(rate*ratio**2)
            scale = max(abs(f) for _, f in train)
            checks = {}
            for split, rows in (("train", train), ("validation", validation)):
                errors = [rate*x-f for x, f in rows]
                checks[split] = {"normalized_rms": math.sqrt(sum(e*e for e in errors)/len(errors))/scale,
                                 "normalized_peak": max(abs(e) for e in errors)/scale,
                                 "input_domain": [min(x for x, _ in rows), max(x for x, _ in rows)],
                                 "count": len(rows)}
            results[wheel][kind] = {"component_rate": rate, "motion_ratio": ratio,
                "wheel_rate": rate*ratio**2, "checks": checks}
    passed = all(check[key] <= limit for corner in results.values() for result in corner.values()
                 for check in result["checks"].values() for key, limit in LIMITS.items())
    report = {"schema": FIT_SCHEMA, "passed": passed, "limits": LIMITS, "results": results,
              "parameters": parameters, "input": document,
              "input_sha256": hashlib.sha256(json.dumps(document, sort_keys=True, ensure_ascii=False,
                    allow_nan=False).encode("utf-8")).hexdigest()}
    config = replace(base, **{field: tuple(values) for field, values in parameters.items()},
                     suspension_si_enabled=True)
    return config, report


def validate_metadata(metadata):
    """文件边界重算输入与报告，不能只凭passed标记授予台架来源。"""
    if metadata is None or "suspension_calibration" not in metadata:
        return
    from vehicle_config import CAR

    report = metadata["suspension_calibration"]
    if report["schema"] != FIT_SCHEMA or report["passed"] is not True:
        raise ValueError("悬架台架报告未通过或版本不支持")
    _, recomputed = fit_bench(report["input"], CAR)
    if recomputed != report or not recomputed["passed"]:
        raise ValueError("悬架台架报告未通过、版本不支持或与原始数据不一致")


def source_note(metadata, field, value):
    """仅给实际相同的配置值沿用部件来源；覆盖值明确解除原标定归属。"""
    if metadata is None or "suspension_calibration" not in metadata or field not in KINDS.values():
        return None
    report = metadata["suspension_calibration"]
    if list(value) != report["parameters"][field]:
        return "已覆盖部件换算值，不沿用其台架来源"
    kind = next(kind for kind, key in KINDS.items() if key == field)
    values = [report["results"][wheel][kind] for wheel in WHEELS]
    ratios = " / ".join(f"{item['motion_ratio']:g}" for item in values)
    rates = " / ".join(f"{item['component_rate']:.4g}" for item in values)
    source = "合成数据，非实测" if report["input"]["source_kind"] == "synthetic" else "按文件声明：部件台架拟合"
    return (f"{source}；{report['input']['temperature_c']:g}°C\n"
            f"部件系数 {rates}；r={ratios}\n独立序列留出通过；常运动比/零预载，范围见工程JSON")


def record_coverage(metadata, config, samples):
    """完成拍采样的部件行程/活塞速度覆盖；不冒称机械子步峰值或温度覆盖。"""
    if metadata is None or "suspension_calibration" not in metadata:
        return None
    report = metadata["suspension_calibration"]
    result = {"scope": "120Hz completed samples only; temperature fixed at bench condition", "corners": {}}
    for wheel in WHEELS:
        items = {}
        for kind, field in KINDS.items():
            fit = report["results"][wheel][kind]
            if list(config[field]) != report["parameters"][field]:
                items[kind] = {"status": "overridden"}
                continue
            key = ("travel_" if kind == "spring" else "travel_rate_")+wheel.lower()
            inputs = [row.get(key) for row in samples]
            if not inputs or any(value is None for value in inputs):
                items[kind] = {"status": "missing_observation"}
                continue
            inputs = [value*fit["motion_ratio"] for value in inputs
                      if kind == "spring" or (value >= 0 if kind == "compression" else value <= 0)]
            domains = [check["input_domain"] for check in fit["checks"].values()]
            domain = [min(d[0] for d in domains), max(d[1] for d in domains)]
            outside = sum(not domain[0] <= value <= domain[1] for value in inputs)
            items[kind] = {"status": ("not_excited" if not inputs else
                           "outside_bench_domain" if outside else "within_sampled_domain"),
                           "bench_input_domain": domain, "sampled_input_domain": [min(inputs), max(inputs)] if inputs else None,
                           "outside_samples": outside, "samples": len(inputs)}
        result["corners"][wheel] = items
    return result
