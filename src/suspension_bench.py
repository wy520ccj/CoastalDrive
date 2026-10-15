"""线性部件台架与安装位移换算；生成唯一VehicleConfig使用的参考硬件和曲线。"""

import hashlib
import json
import math
from dataclasses import replace

from suspension_damper import damper_curve
from suspension_installation import installation_curve

SCHEMA = "coastal-suspension-bench-v1"
FIT_SCHEMA = "coastal-suspension-fit-v1"
INSTALLED_SCHEMA = "coastal-suspension-bench-v2"
INSTALLED_FIT_SCHEMA = "coastal-suspension-fit-v2"
INSTALLED_DEFINITION = "positive_compression_resistance;spring_input_from_free_length;installed_compression_at_zero_wheel_travel"
MOTION_SCHEMA = "coastal-suspension-bench-v3"
MOTION_FIT_SCHEMA = "coastal-suspension-fit-v3"
MOTION_DEFINITION = "positive_compression_resistance;installed_compression_at_zero_wheel_travel;curve_component_increments"
DAMPER_SCHEMA = "coastal-suspension-bench-v4"
DAMPER_FIT_SCHEMA = "coastal-suspension-fit-v4"
DAMPER_DEFINITION = MOTION_DEFINITION+";memoryless_piecewise_linear_damper"
CURVED_FITS = (MOTION_FIT_SCHEMA,DAMPER_FIT_SCHEMA)
GEOMETRY_LIMIT_M = .0002
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


def _geometry_validation(rows, validation):
    axes = installation_curve(rows)
    if len(validation)<3 or any(len(row)!=3 for row in validation):
        raise ValueError("安装几何留出须至少三个独立轮心位置及两部件增量")
    for row in validation:
        for value in row:_number(value,"几何留出坐标m")
    qs = [row[0] for row in validation]
    if (len(set(qs))!=len(qs) or not min(qs)<0.<max(qs)
        or any(q in [row[0] for row in rows] or q<rows[0][0] or q>rows[-1][0] for q in qs)):
        raise ValueError("几何留出位置须与插值节点分开，位于数据域内并覆盖正负行程")
    errors = [max(abs(axis.at(row[0])[0]-row[i+1]) for row in validation) for i,axis in enumerate(axes)]
    return {"passed":max(errors)<=GEOMETRY_LIMIT_M,"limit_m":GEOMETRY_LIMIT_M,
            "max_position_error_m":errors,"count":len(validation),"derivatives_directly_measured":False}


def _damper_nodes(groups):
    """重复同速训练读数取均值；留出序列不进入节点，零速偏置须另建物理模型。"""
    points={}
    for kind in ("compression","extension"):
        train=groups[kind,"train"]
        if not any(v==0. and f==0. for v,f in train) or any(v==0. and f!=0. for v,f in train):
            raise ValueError("力速表两方向训练均须有零速度/零阻力；气体预载或摩擦偏置须分离")
        for velocity,force in train:points.setdefault(velocity,[]).append(force)
    rows=tuple((velocity,sum(values)/len(values)) for velocity,values in sorted(points.items()))
    damper_curve(rows)
    return rows


def _fit_document(document):
    """各部件独立过原点最小二乘；整序列留出只验证，不调整拟合值。"""
    if set(document) != {"schema", "source", "source_kind", "temperature_c", "units", "definition", "corners"}:
        raise ValueError("悬架台架文件字段不完整或含未知字段")
    tabulated = document["schema"]==DAMPER_SCHEMA
    curved = tabulated or document["schema"]==MOTION_SCHEMA
    installed = curved or document["schema"] == INSTALLED_SCHEMA
    if (document["schema"] not in (SCHEMA,INSTALLED_SCHEMA,MOTION_SCHEMA,DAMPER_SCHEMA) or document["units"] != UNITS
        or document["definition"] != (DAMPER_DEFINITION if tabulated else MOTION_DEFINITION if curved else INSTALLED_DEFINITION if installed else DEFINITION)):
        raise ValueError("悬架台架版本、SI单位或零位/力方向定义不支持")
    if document["source_kind"] not in ("measured", "synthetic") or not isinstance(document["source"], str) or not document["source"].strip():
        raise ValueError("台架来源不能为空，须声明measured或synthetic")
    _number(document["temperature_c"], "台架温度")
    if set(document["corners"]) != set(WHEELS):
        raise ValueError("须逐一提供FL/FR/RL/RR部件与安装运动比")
    parameters = {field: [] for field in KINDS.values()}
    if installed:
        parameters.update(suspension_coil_enabled=True,suspension_spring_preloads=[])
    if curved:parameters["suspension_installation_curves"]=[]
    if tabulated:parameters["suspension_damper_curves"]=[]
    results,geometry_checks = {},{}
    for wheel in WHEELS:
        corner = document["corners"][wheel]
        fields = {"spring_id", "damper_id", "spring_motion_ratio", "damper_motion_ratio", "installation_source", "rows"}
        if installed: fields.add("spring_installed_compression_m")
        if curved:
            fields -= {"spring_motion_ratio","damper_motion_ratio"}
            fields |= {"installation_curve","installation_validation"}
        if set(corner) != fields:
            raise ValueError(f"{wheel}部件/安装字段不完整或含未知字段")
        for key in ("spring_id", "damper_id", "installation_source"):
            if not isinstance(corner[key], str) or not corner[key].strip():
                raise ValueError(f"{wheel}的{key}不能为空")
        if curved:
            rows = tuple(tuple(row) for row in corner["installation_curve"])
            axes = installation_curve(rows)
            ratios = [axis.reference_ratio for axis in axes]
            parameters["suspension_installation_curves"].append([list(row) for row in rows])
            geometry_checks[wheel]=_geometry_validation(rows,corner["installation_validation"])
        else:
            ratios = [corner[key] for key in ("spring_motion_ratio","damper_motion_ratio")]
            if any(_number(ratio,"压缩运动比")<=0. for ratio in ratios):
                raise ValueError("压缩运动比须为有限正值；反向安装不支持")
        if installed and _number(corner["spring_installed_compression_m"],"零行程处弹簧安装压缩m") < 0.:
            raise ValueError("安装压缩须为非负值；当前不支持带间隙的弹簧座安装")
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
        if tabulated:
            nodes=_damper_nodes(groups)
            curve=damper_curve(nodes)
            parameters["suspension_damper_curves"].append([[v/ratios[1],f*ratios[1]] for v,f in nodes])
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
            nonlinear_damper=tabulated and kind!="spring"
            if nonlinear_damper:
                zero=curve.speed.index(0.)
                first=zero+1 if kind=="compression" else zero-1
                rate=curve.force[first]/curve.speed[first]
            ratio = ratios[0 if kind=="spring" else 1]
            parameters[field].append(rate*ratio**2)
            scale = max(abs(f) for _, f in train)
            checks = {}
            for split, rows in (("train", train), ("validation", validation)):
                errors = [(curve.at(x)[0] if nonlinear_damper else rate*x)-f for x, f in rows]
                checks[split] = {"normalized_rms": math.sqrt(sum(e*e for e in errors)/len(errors))/scale,
                                 "normalized_peak": max(abs(e) for e in errors)/scale,
                                 "input_domain": [min(x for x, _ in rows), max(x for x, _ in rows)],
                                 "count": len(rows)}
            results[wheel][kind] = {"component_rate": rate, "motion_ratio": ratio,
                "wheel_rate": rate*ratio**2, "checks": checks}
            if nonlinear_damper:
                results[wheel][kind].update(rate_definition="origin segment tangent only; table governs force",
                    training_node_count=len(nodes),extrapolation="endpoint_segment_linear")
            if installed and kind == "spring":
                installed_compression = corner["spring_installed_compression_m"]
                preload = ratio*rate*installed_compression
                parameters["suspension_spring_preloads"].append(preload)
                results[wheel][kind].update(installed_compression_m=installed_compression,wheel_preload_N=preload)
    passed = all(check[key] <= limit for corner in results.values() for result in corner.values()
                 for check in result["checks"].values() for key, limit in LIMITS.items())
    if curved:passed = passed and all(item["passed"] for item in geometry_checks.values())
    report = {"schema": DAMPER_FIT_SCHEMA if tabulated else MOTION_FIT_SCHEMA if curved else INSTALLED_FIT_SCHEMA if installed else FIT_SCHEMA, "passed": passed, "limits": LIMITS, "results": results,
              "parameters": parameters, "input": document,
              "input_sha256": hashlib.sha256(json.dumps(document, sort_keys=True, ensure_ascii=False,
                    allow_nan=False).encode("utf-8")).hexdigest()}
    if curved:report["installation_validation"]=geometry_checks
    return report


def fit_bench(document, base):
    """部件数据生成完整硬件；安装模型须已具备实际独立轮心自由度。"""
    report = _fit_document(document)
    parameters = report["parameters"]
    values = {field:tuple(parameters[field]) for field in KINDS.values()}
    installed = report["schema"] in (INSTALLED_FIT_SCHEMA,*CURVED_FITS)
    values.update(suspension_coil_enabled=installed,
                  suspension_spring_preloads=tuple(parameters["suspension_spring_preloads"])
                      if installed else (0.,)*4,
                  suspension_installation_curves=tuple(tuple(tuple(row) for row in rows) for rows in parameters["suspension_installation_curves"])
                      if report["schema"] in CURVED_FITS else None,
                  suspension_damper_curves=tuple(tuple(tuple(row) for row in rows) for rows in parameters["suspension_damper_curves"])
                      if report["schema"]==DAMPER_FIT_SCHEMA else None)
    config = replace(base, **values, suspension_si_enabled=True)
    return config, report


def validate_metadata(metadata):
    """文件边界重算输入与报告，不能只凭passed标记授予台架来源。"""
    if metadata is None or "suspension_calibration" not in metadata:
        return
    report = metadata["suspension_calibration"]
    if report["schema"] not in (FIT_SCHEMA,INSTALLED_FIT_SCHEMA,*CURVED_FITS) or report["passed"] is not True:
        raise ValueError("悬架台架报告未通过或版本不支持")
    recomputed = _fit_document(report["input"])
    if recomputed != report or not recomputed["passed"]:
        raise ValueError("悬架台架报告未通过、版本不支持或与原始数据不一致")


def _installation_matches(report, config):
    # 旧保存记录的配置没有这两个字段，其明确语义是原双向弹性/零预载。
    coil = config.get("suspension_coil_enabled",False)
    preloads = config.get("suspension_spring_preloads",(0.,)*4)
    curves = config.get("suspension_installation_curves")
    if report["schema"] in CURVED_FITS:
        return (coil and list(preloads)==report["parameters"]["suspension_spring_preloads"] and
                json.loads(json.dumps(curves))==report["parameters"]["suspension_installation_curves"])
    if curves is not None:return False
    return ((coil and list(preloads)==report["parameters"]["suspension_spring_preloads"])
            if report["schema"]==INSTALLED_FIT_SCHEMA else not coil and not any(preloads))


def _damper_matches(report,config):
    table=config.get("suspension_damper_curves")
    return (json.loads(json.dumps(table))==report["parameters"]["suspension_damper_curves"]
            if report["schema"]==DAMPER_FIT_SCHEMA else table is None)


def source_note(metadata, field, value, config):
    """仅给实际相同的配置值沿用部件来源；覆盖值明确解除原标定归属。"""
    if metadata is None or "suspension_calibration" not in metadata:
        return None
    report = metadata["suspension_calibration"]
    if field not in report["parameters"]:
        return None
    saved = report["parameters"][field]
    if json.loads(json.dumps(value)) != saved:
        return "已覆盖部件换算值，不沿用其台架来源"
    kind = next((kind for kind, key in KINDS.items() if key == field),"compression" if field=="suspension_damper_curves" else "spring")
    if kind!="spring" and not _damper_matches(report,config):
        return "减振器本构已覆盖，不沿用原台架表/线性模型的来源和适用域"
    if (kind=="spring" or report["schema"] in CURVED_FITS) and not _installation_matches(report,config):
        return "部件斜率来自原台架；安装值已覆盖，不沿用其安装来源/适用域"
    values = [report["results"][wheel][kind] for wheel in WHEELS]
    ratios = " / ".join(f"{item['motion_ratio']:g}" for item in values)
    rates = " / ".join(f"{item['component_rate']:.4g}" for item in values)
    source = "合成数据，非实测" if report["input"]["source_kind"] == "synthetic" else "按文件声明：部件台架拟合"
    installation = ("安装压缩m："+" / ".join(f"{report['results'][wheel]['spring']['installed_compression_m']:g}" for wheel in WHEELS)
                    if report["schema"] in (INSTALLED_FIT_SCHEMA,*CURVED_FITS) and kind=="spring" else
                    "零预载" if kind=="spring" else
                    "分段力速表生效；系数仅零速切线" if report["schema"]==DAMPER_FIT_SCHEMA else "压缩/伸张分别拟合")
    return (f"{source}；{report['input']['temperature_c']:g}°C\n"
            f"部件系数 {rates}；r0={ratios}\n{installation}；"+
            ("独立留出通过；域外线性外推" if report["schema"] in CURVED_FITS else "范围见工程JSON"))


def record_coverage(metadata, config, samples):
    """完成拍采样的部件行程/活塞速度覆盖；不冒称机械子步峰值或温度覆盖。"""
    if metadata is None or "suspension_calibration" not in metadata:
        return None
    report = metadata["suspension_calibration"]
    result = {"scope": "120Hz completed samples only; temperature fixed at bench condition", "corners": {}}
    for index,wheel in enumerate(WHEELS):
        items = {}
        for kind, field in KINDS.items():
            fit = report["results"][wheel][kind]
            active_table=kind!="spring" and report["schema"]==DAMPER_FIT_SCHEMA
            if ((not active_table and list(config[field]) != report["parameters"][field])
                or kind!="spring" and not _damper_matches(report,config)
                or (kind=="spring" or report["schema"] in CURVED_FITS) and not _installation_matches(report,config)):
                items[kind] = {"status": "overridden"}
                continue
            key = ("travel_" if kind == "spring" else "travel_rate_")+wheel.lower()
            inputs = [row.get(key) for row in samples]
            if not inputs or any(value is None for value in inputs):
                items[kind] = {"status": "missing_observation"}
                continue
            offset = fit["installed_compression_m"] if kind=="spring" and report["schema"] in (INSTALLED_FIT_SCHEMA,*CURVED_FITS) else 0.
            installation_outside = 0
            if report["schema"] in CURVED_FITS:
                curve_rows=tuple(tuple(row) for row in config["suspension_installation_curves"][index])
                spring_axis,damper_axis=installation_curve(curve_rows)
                q_values=[row.get("travel_"+wheel.lower()) for row in samples]
                if any(q is None for q in q_values):
                    items[kind]={"status":"missing_observation"}
                    continue
                installation_outside=sum(q<curve_rows[0][0] or q>curve_rows[-1][0] for q in q_values)
                inputs=[max(0.,offset+spring_axis.at(q)[0]) if kind=="spring" else value*damper_axis.at(q)[1]
                        for q,value in zip(q_values,inputs,strict=True)
                        if kind=="spring" or (value>=0 if kind=="compression" else value<=0)]
            else:
                inputs = [max(0.,offset+value*fit["motion_ratio"]) if kind=="spring" and report["schema"]==INSTALLED_FIT_SCHEMA
                          else value*fit["motion_ratio"] for value in inputs
                          if kind == "spring" or (value >= 0 if kind == "compression" else value <= 0)]
            domains = [check["input_domain"] for check in fit["checks"].values()]
            domain = [min(d[0] for d in domains), max(d[1] for d in domains)]
            outside = sum(not domain[0] <= value <= domain[1] for value in inputs)
            items[kind] = {"status": ("not_excited" if not inputs else
                           "outside_bench_domain" if outside else "within_sampled_domain"),
                           "bench_input_domain": domain, "sampled_input_domain": [min(inputs), max(inputs)] if inputs else None,
                           "outside_samples": outside, "samples": len(inputs)}
            if active_table:
                rows=report["parameters"]["suspension_damper_curves"][index]
                table_domain=[rows[0][0]*fit["motion_ratio"],rows[-1][0]*fit["motion_ratio"]]
                items[kind].update(force_table_input_domain_mps=table_domain,
                    table_extrapolated_samples=sum(not table_domain[0]<=value<=table_domain[1] for value in inputs))
            if report["schema"] in CURVED_FITS:
                items[kind].update(installation_outside_samples=installation_outside,
                    installation_q_domain_m=[curve_rows[0][0],curve_rows[-1][0]],
                    extrapolation="endpoint_tangent_linear")
        result["corners"][wheel] = items
    return result
