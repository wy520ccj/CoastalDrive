"""固定试验条件下的稳态部件标定，验证不参与参数优化。"""

import csv
import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from tire_forces import tire_force

FIELDS = ("series", "split", "kind", "fz_N", "kappa", "alpha_rad", "fx_N", "fy_N")
PARAMETERS = ("road_friction", "longitudinal_stiffness", "lateral_stiffness",
              "tire_peak_load_exponent", "longitudinal_load_exponent", "lateral_load_exponent")
LOWER = np.array((.05, 1000., 1000., .4, .2, .2))
UPPER = np.array((3., 1e6, 1e6, 1.5, 1.8, 1.8))
CONDITION_FIELDS = {"tire_id", "surface_id", "pressure_kpa", "temperature_c", "speed_mps", "slip_convention",
                    "camber_rad", "source", "source_kind", "measurement_mode", "installation"}


@dataclass(frozen=True)
class TireBench:
    rows: tuple
    conditions: dict
    fingerprint: dict


def validate_conditions(conditions):
    if set(conditions) != CONDITION_FIELDS:
        raise ValueError("试验条件必须完整且仅包含规定字段")
    for field in ("tire_id", "surface_id", "source"):
        if not isinstance(conditions[field], str) or not conditions[field].strip():
            raise ValueError(f"试验{field}不能为空")
    if (conditions["source_kind"] not in ("measured", "synthetic")
        or conditions["measurement_mode"] != "steady_state"
        or conditions["slip_convention"] != "drive_positive_alpha_right"
        or conditions["installation"] != "same_tire_all_wheels"):
        raise ValueError("仅接受同一套四轮轮胎的稳态数据；来源须标明measured或synthetic")
    for field in ("pressure_kpa", "temperature_c", "speed_mps", "camber_rad"):
        if isinstance(conditions[field], bool) or not isinstance(conditions[field], (int, float)) or not math.isfinite(conditions[field]):
            raise ValueError(f"试验条件{field}须为有限数")
    if conditions["pressure_kpa"] <= 0 or conditions["speed_mps"] <= 1 or conditions["camber_rad"] != 0:
        raise ValueError("胎压须为正、速度须>1m/s；当前标定不支持外倾推力")


def validate_fit_metadata(metadata):
    if not isinstance(metadata, dict):
        raise TypeError("工程来源metadata须为对象")
    if "basis" in metadata and not isinstance(metadata["basis"], str):
        raise TypeError("来源basis须为文字")
    if "tire_calibration" not in metadata:
        return
    fit = metadata["tire_calibration"]
    if fit["schema"] != "coastal-tire-fit-v1" or fit["passed"] is not True or fit["rank"] != 6:
        raise ValueError("轮胎标定未通过独立验证或版本不支持，不能应用候选")
    if set(fit["parameters"]) != set(PARAMETERS):
        raise ValueError("标定参数目录不完整")
    validate_conditions(fit["conditions"])
    for value in (*fit["parameters"].values(), fit["linked_rear_lateral_stiffness"]):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("标定报告参数须为有限数")
    if "data_domain" in fit:
        for split in ("train", "validation"):
            for field in ("fz_N", "kappa", "alpha_rad"):
                minimum, maximum = fit["data_domain"][split][field]
                if (any(isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value) for value in (minimum, maximum)) or minimum > maximum):
                    raise ValueError("标定数据范围无效")


def load_bench(csv_path, conditions_path):
    conditions_path, csv_path = Path(conditions_path), Path(csv_path)
    conditions = json.loads(conditions_path.read_text(encoding="utf-8"))
    validate_conditions(conditions)
    rows = []
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(FIELDS):
            raise ValueError("轮胎CSV字段或顺序不符合模板")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("CSV行存在多余或缺失字段")
            if (not row["series"].strip() or row["split"] not in ("train", "validation")
                or row["kind"] not in ("longitudinal", "lateral", "combined")):
                raise ValueError("序列/数据分区/工况类型无效")
            row = {**row, **{field: float(row[field]) for field in FIELDS[3:]}}
            if any(not math.isfinite(row[field]) for field in FIELDS[3:]) or row["fz_N"] <= 0:
                raise ValueError("轮荷须为有限正值，所有信号须为有限数")
            if abs(row["alpha_rad"]) > .6 or abs(row["kappa"]) > 2:
                raise ValueError("本稳态标定窗口要求|α|≤0.6rad、|κ|≤2")
            if ((row["kind"] == "longitudinal" and abs(row["alpha_rad"]) > 1e-8)
                or (row["kind"] == "lateral" and abs(row["kappa"]) > 1e-8)
                or (row["kind"] == "combined" and (row["kappa"] == 0 or row["alpha_rad"] == 0))):
                raise ValueError("工况类型与滑移输入不一致")
            if row["split"] == "train" and row["kind"] == "combined":
                raise ValueError("联合滑移留作独立验证，不能混入本阶段拟合")
            rows.append(row)
    roles = {}
    for row in rows:
        identity = (row["split"], row["kind"], row["fz_N"])
        if row["series"] in roles and roles[row["series"]] != identity:
            raise ValueError("同一试验序列不能跨拟合/验证、工况或轮荷")
        roles[row["series"]] = identity
    for kind, slip in (("longitudinal", "kappa"), ("lateral", "alpha_rad")):
        train = [row for row in rows if row["split"] == "train" and row["kind"] == kind]
        loads = {row["fz_N"] for row in train}
        if len(loads) < 3 or max(loads)/min(loads) < 1.5:
            raise ValueError("两种纯滑移拟合均需至少三个轮荷，最大/最小比≥1.5")
        for load in loads:
            slips = [row[slip] for row in train if row["fz_N"] == load]
            if (not any(0 < abs(value) <= .003 for value in slips)
                or min(slips) >= 0 or max(slips) <= 0
                or max(abs(value) for value in slips) < (.15 if kind == "longitudinal" else .10)):
                raise ValueError("每个轮荷需正负、小滑移及峰区覆盖；不能只靠峰值辨识刚度")
    for kind in ("longitudinal", "lateral", "combined"):
        validation = [row for row in rows if row["split"] == "validation" and row["kind"] == kind]
        if len(validation) < 4:
            raise ValueError("纯纵、纯横、联合滑移均需至少四个独立验证点")
    fingerprint = {"csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                   "conditions_sha256": hashlib.sha256(conditions_path.read_bytes()).hexdigest()}
    return TireBench(tuple(rows), conditions, fingerprint)


def config_at(values, base):
    updated = dict(zip(PARAMETERS, values, strict=True))
    # 数据明确声明同一套四轮轮胎，后轴采用同一部件侧偏刚度。
    return replace(base, **updated, rear_lateral_stiffness=updated["lateral_stiffness"])


def predict(rows, config):
    return np.array([tire_force(row["kappa"], row["alpha_rad"], row["fz_N"],
                                config.road_friction, config) for row in rows])


def fit_tire(bench, base):
    """缩放参数上的阻尼Gauss-Newton；显式界限、秩与留出误差决定候选可用性。"""
    train = [row for row in bench.rows if row["split"] == "train"]
    counts = Counter(row["series"] for row in train)
    scales = np.array([row["fz_N"]*math.sqrt(counts[row["series"]]) for row in train])[:, None]
    observed = np.array([(row["fx_N"], row["fy_N"]) for row in train])
    lower, upper = np.log(LOWER), np.log(UPPER)
    values = np.log(np.array([getattr(base, key) for key in PARAMETERS]))
    if np.any(values <= lower) or np.any(values >= upper):
        raise ValueError("初始工程配置超出公开标定搜索区间")

    def residual(parameters):
        return ((predict(train, config_at(np.exp(parameters), base))-observed)/scales).ravel()

    def jacobian(parameters):
        columns = []
        for index in range(len(PARAMETERS)):
            delta = np.zeros(len(PARAMETERS))
            delta[index] = 1e-5
            columns.append((residual(parameters+delta)-residual(parameters-delta))/(2e-5))
        return np.column_stack(columns)

    damping, converged, iterations = 1e-3, False, 0
    for iterations in range(1, 101):
        error, jac = residual(values), jacobian(values)
        gradient, hessian = jac.T@error, jac.T@jac
        if np.linalg.norm(gradient, ord=np.inf) < 1e-9:
            converged = True
            break
        step = np.linalg.solve(hessian+damping*np.diag(np.maximum(np.diag(hessian), 1e-8)), -gradient)
        candidate = np.clip(values+step, lower, upper)
        new_error = residual(candidate)
        if new_error@new_error < error@error:
            values = candidate
            damping = max(damping/3, 1e-12)
        else:
            damping *= 10
        if damping > 1e12:
            break
    config = config_at(np.exp(values), base)
    singular = np.linalg.svd(jacobian(values), compute_uv=False)
    rank = int(np.count_nonzero(singular > singular[0]*1e-8))
    condition = float(singular[0]/singular[-1]) if singular[-1] > 0 else None
    at_bound = bool(np.any(values-lower < 1e-5) or np.any(upper-values < 1e-5))
    metrics = []
    for split in ("train", "validation"):
        for kind in ("longitudinal", "lateral", "combined"):
            rows = [row for row in bench.rows if row["split"] == split and row["kind"] == kind]
            if not rows:
                continue
            difference = predict(rows, config)-np.array([(row["fx_N"], row["fy_N"]) for row in rows])
            # 用实测序列峰值归一化，不能靠抬高拟合D把验证误差变小。
            peaks = {series: max(math.hypot(row["fx_N"], row["fy_N"])
                                 for row in rows if row["series"] == series)
                     for series in {row["series"] for row in rows}}
            if any(peak <= 0 for peak in peaks.values()):
                raise ValueError("试验序列没有非零力响应，无法定义验证误差")
            budgets = np.array([peaks[row["series"]] for row in rows])
            normalized = np.linalg.norm(difference, axis=1)/budgets
            metrics.append({"split": split, "kind": kind, "count": len(rows),
                            "rmse_fx_N": float(np.sqrt(np.mean(difference[:, 0]**2))),
                            "rmse_fy_N": float(np.sqrt(np.mean(difference[:, 1]**2))),
                            "normalized_rms": float(np.sqrt(np.mean(normalized**2))),
                            "normalized_max": float(max(normalized))})
    passed = (converged and rank == 6 and condition is not None and condition < 1e8 and not at_bound
              and all(item["normalized_rms"] <= .05 and item["normalized_max"] <= .10 for item in metrics))
    report = {"schema": "coastal-tire-fit-v1", "passed": bool(passed), "iterations": iterations,
              "converged": converged, "rank": rank, "condition_number": condition,
              "singular_values": singular.tolist(), "parameter_at_bound": at_bound,
              "parameters": {key: getattr(config, key) for key in PARAMETERS},
              "linked_rear_lateral_stiffness": config.rear_lateral_stiffness,
              "fixed_parameters": {key: getattr(base, key) for key in (
                  "tire_reference_load", "tire_shape", "tire_curvature", "tire_contact_stiffness", "tire_contact_damping")},
              "conditions": bench.conditions, "input_fingerprint": bench.fingerprint,
              "data_domain": {split: {field: [min(row[field] for row in bench.rows if row["split"] == split),
                                                max(row[field] for row in bench.rows if row["split"] == split)]
                                      for field in ("fz_N", "kappa", "alpha_rad")}
                              for split in ("train", "validation")},
              "normalization": "observed force magnitude peak in each complete series",
              "parameter_bounds": {key: [float(low), float(high)]
                                   for key, low, high in zip(PARAMETERS, LOWER, UPPER, strict=True)},
              "criteria": {"validation_normalized_rms_max": .05, "validation_normalized_point_max": .10,
                           "full_rank": 6, "condition_number_max": 1e8}, "errors": metrics}
    return config, report
