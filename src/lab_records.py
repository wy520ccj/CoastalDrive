"""保存真实实验、模型摘要、120Hz曲线、动画快照与复算输入。"""

import csv
import hashlib
import html
import json
import math
import platform
from dataclasses import asdict, dataclass
from pathlib import Path

from lab_maneuvers import path_error, reference_path
from lab_metrics import engineering_analysis
from lab_signals import (
    LEGACY_SIGNAL_KEYS,
    PRE_ALIGN_SIGNAL_KEYS,
    PRE_UNSPRUNG_SIGNAL_KEYS,
    SIGNAL_BY_KEY,
    SIGNALS,
    sample_signals,
)
from paths import resource_root
from snapshot_wire import decode_snapshots, encode_snapshots
from tire_calibration import validate_fit_metadata
from vehicle_state import VehicleCommand

SCHEMA = "coastal-vehicle-lab-v1"


def model_fingerprint():
    """源码与实际原生模块内容共同标识版本，覆盖未提交构建。"""
    root = resource_root()
    files = [path for path in (root/"src").glob("*") if path.suffix in (".py", ".c", ".h", ".pyd")]
    files += list((root/"assets/game/vehicle-configs").glob("*.json"))
    # 独立包源码位于冻结资源中；实际包的exe/pyd也必须进入版本证据。
    if not files:
        files = list(root.glob("*.exe")) + list(root.glob("*.pyd"))
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files)}


@dataclass(frozen=True)
class LabRecord:
    metadata: dict
    samples: tuple
    snapshots: tuple
    commands: tuple

    @classmethod
    def from_run(cls, run):
        return cls({"schema": SCHEMA, "physics_hz": 120, "mode": "offline_fixed_step",
                    "vehicle_name": run.design.name,
                    "model_basis": (run.parameter_metadata["basis"] if run.parameter_metadata is not None
                                    and "basis" in run.parameter_metadata else run.design.basis),
                    "parameter_metadata": json.loads(json.dumps(run.parameter_metadata, allow_nan=False)),
                    "vehicle_config": json.loads(json.dumps(asdict(run.config), allow_nan=False)),
                    "summary": run.summary(),
                    "reference_path": reference_path(run.options, run.snapshots[0].player),
                    "driver": {"kind": "pure_pursuit_speed_pi", "preview_seconds": 1.2,
                               "minimum_preview_m": 6., "speed_p": .2, "speed_i": .08,
                               "lane_change_m": [20, 30, 20, 30], "lane_offset_m": 3.5}
                              if run.options.maneuver in ("constant_radius", "double_lane_change") else None,
                    "source_start": run.source_start, "source_end": model_fingerprint(),
                    "python": platform.python_version(), "hardware": platform.machine()},
                   tuple(dict(row) for row in run.samples), tuple(run.snapshots), tuple(run.commands))


def changed_conditions(baseline, candidate):
    """递归列出实际改动条件；多变量变化也完整呈现，不伪称单变量A/B。"""
    changes = {}

    def compare(prefix, old, new):
        if isinstance(old, dict) and isinstance(new, dict):
            for key in sorted(old.keys() | new.keys()):
                compare(f"{prefix}.{key}" if prefix else key, old.get(key), new.get(key))
        elif old != new:
            changes[prefix] = {"A": old, "B": new}

    for key in ("options",):
        compare(key, baseline.metadata["summary"][key], candidate.metadata["summary"][key])
    compare("vehicle", baseline.metadata["vehicle_config"], candidate.metadata["vehicle_config"])
    if baseline.metadata["source_start"] != candidate.metadata["source_start"]:
        changes["model_version"] = {"A": "基线源码摘要", "B": "不同源码摘要"}
    return changes


def plot_svg(records, key, width=760, height=220):
    signal = SIGNAL_BY_KEY[key]
    rows = [record.samples for record in records]
    values = [row[key] for series in rows for row in series if row[key] is not None]
    low, high = (min(values), max(values)) if values else (0., 1.)
    span = max(high-low, .1)
    low, high = low-.08*span, high+.08*span
    maximum_time = max((series[-1]["time"] for series in rows if series), default=1.) or 1.
    output = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
              '<rect width="100%" height="100%" fill="#fefcf5"/>',
              f'<text x="16" y="22" fill="#102b3a" font-size="14">{html.escape(signal.label)} / {signal.unit}</text>']
    for index in range(5):
        value = low+(high-low)*index/4
        y = height-32-index*(height-68)/4
        output += [f'<path d="M58 {y}H{width-16}" stroke="#c9d3cc"/>',
                   f'<text x="5" y="{y+4}" fill="#455c63" font-size="11">{value:.2f}</text>']
    for series, color in zip(rows, ("#247e96", "#f47c24")):
        path = []
        connected = False
        for row in series:
            value = row[key]
            if value is None:
                connected = False
                continue
            x = 58+row["time"]/maximum_time*(width-74)
            y = height-32-(value-low)/(high-low)*(height-68)
            path.append(f'{"L" if connected else "M"}{x:.2f},{y:.2f}')
            connected = True
        output.append(f'<path d="{" ".join(path)}" fill="none" stroke="{color}" stroke-width="1.7"/>')
    output += [f'<text x="58" y="{height-8}" fill="#455c63" font-size="11">0</text>',
               f'<text x="{width-75}" y="{height-8}" fill="#455c63" font-size="11">{maximum_time:.2f} s</text>', '</svg>']
    return "\n".join(output)


def export_record(record, folder, baseline=None):
    """每次新建结果目录，避免覆盖原始试验。"""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    payload = encode_snapshots((record.snapshots, ()))
    (folder/"snapshots.bin").write_bytes(payload)
    document = {**record.metadata, "snapshot_sha256": hashlib.sha256(payload).hexdigest(),
                "signals": [asdict(signal) for signal in SIGNALS],
                "samples": record.samples, "commands": [asdict(command) for command in record.commands]}
    (folder/"vehicle.json").write_text(json.dumps(record.metadata["vehicle_config"], ensure_ascii=False,
        indent=2, allow_nan=False)+"\n", encoding="utf-8")
    (folder/"experiment.json").write_text(json.dumps(document, ensure_ascii=False, indent=2,
        allow_nan=False)+"\n", encoding="utf-8")
    with (folder/"signals.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=record.samples[0].keys())
        writer.writeheader()
        writer.writerows(record.samples)
    records = (baseline, record) if baseline else (record,)
    analyses = [engineering_analysis(item.samples, item.snapshots, item.metadata["summary"]["options"],
                                    item.metadata["summary"]["reason"]) for item in records]
    (folder/"engineering.json").write_text(json.dumps({"definition_fingerprint": model_fingerprint(),
                                                      "A" if baseline else "current": analyses[0],
                                                      **({"B": analyses[1]} if baseline else {})},
                                                     ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    metrics_table = "".join(f'<tr><td>{html.escape(item["label"])}</td>'
                            + "".join(f'<td>{analysis["metrics"][index]["value"]:.4g}</td>'
                                      if analysis["metrics"][index]["value"] is not None else '<td>未满足条件</td>'
                                      for analysis in analyses)
                            + f'<td>{item["unit"]}</td><td>{html.escape(item["note"])}</td></tr>'
                            for index, item in enumerate(analyses[-1]["metrics"]))
    ride_table = "".join(f'<tr><td>{html.escape(item["label"])}</td>'
                        + "".join(f'<td>{analysis["ride"]["metrics"][i]["value"]:.4g}</td>'
                                  if analysis["ride"]["metrics"][i]["value"] is not None else '<td>未满足条件</td>'
                                  for analysis in analyses)
                        + f'<td>{item["unit"]}</td><td>{html.escape(item["note"])}</td></tr>'
                        for i,item in enumerate(analyses[-1]["ride"]["metrics"]))
    keys = ("speed", "path_error", "ay", "yaw", "steering", "kappa_fl") if record.metadata["driver"] else (
        "speed", "ax", "yaw", "steering", "kappa_fl", "load_fl")
    if record.metadata["summary"]["options"]["maneuver"]=="ride_bump":
        keys = ("sprung_az","hub_az_fl","travel_fl","radial_fl","load_fl","cg_speed")
    plots = "\n".join(plot_svg(records, key) for key in keys)
    summary = html.escape(json.dumps(record.metadata["summary"], ensure_ascii=False, indent=2))
    comparison = changed_conditions(baseline, record) if baseline else {}
    if baseline:
        export_record(baseline, folder/"baseline-A")
        (folder/"comparison.json").write_text(json.dumps({"conditions": comparison,
            "A": baseline.metadata["summary"], "B": record.metadata["summary"]}, ensure_ascii=False,
            indent=2, allow_nan=False)+"\n", encoding="utf-8")
    change_text = html.escape(json.dumps(comparison, ensure_ascii=False, indent=2))
    catalog = "".join(f'<tr><td>{signal.key}</td><td>{html.escape(signal.label)}</td>'
                      f'<td>{signal.unit}</td><td>{html.escape(signal.source)}</td></tr>' for signal in SIGNALS)
    report = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>CoastalDrive 实验报告</title>
<style>body{{background:#f3efe3;color:#102b3a;font:15px system-ui;max-width:1000px;margin:40px auto;padding:0 24px}}svg{{width:100%;margin:10px 0}}pre{{white-space:pre-wrap;background:#fefcf5;padding:20px;border-radius:8px}}td{{border-bottom:1px solid #c9d3cc;padding:8px}}h1{{color:#247e96}}</style>
<h1>CoastalDrive · 车辆动力学实验</h1><p>{html.escape(record.metadata["vehicle_name"])} · 120 Hz · 离线固定步</p>
<p>{html.escape(record.metadata["model_basis"])}</p><p>曲线来自真实物理记录。A 为海蓝，B 为橙色；单次记录为海蓝。制动距离使用完成步的三维行驶距离，停止阈值 |v| ≤ 0.1 m/s。</p>
<h2>试验结果</h2><pre>{summary}</pre><h2>工程指标</h2><p>列顺序：{"A / B" if baseline else "本次"}。未满足条件的原因及计算区间见engineering.json。</p><table>{metrics_table}</table><h2>乘坐运动与接地</h2><p>世界Z质心/轮心惯性加速度，未作频率加权，不作为ISO座椅舒适等级。实体刺激未完成或旧记录缺少自由度时保留未定义值。</p><table>{ride_table}</table>{plots}<h2>比较条件</h2><pre>{change_text}</pre>
<h2>信号单位与字段来源</h2><table>{catalog}</table><p>完整配置、命令序列与源码/原生模块摘要见 experiment.json；120 Hz 数据见 signals.csv，动画快照见 snapshots.bin。实际计算耗时不包含初始化与文件导出。</p></html>'''
    (folder/"report.html").write_text(report, encoding="utf-8")
    return folder/"report.html"


def load_record(folder):
    from lab_experiment import LabOptions

    folder = Path(folder)
    document = json.loads((folder/"experiment.json").read_text(encoding="utf-8"))
    if document["schema"] != SCHEMA or document["physics_hz"] != 120:
        raise ValueError("只支持当前120Hz实验记录")
    payload = (folder/"snapshots.bin").read_bytes()
    if hashlib.sha256(payload).hexdigest() != document["snapshot_sha256"]:
        raise ValueError("动画快照文件损坏或与记录不一致")
    snapshots, _ = decode_snapshots(payload)
    samples = tuple(document.pop("samples"))
    commands = tuple(VehicleCommand(**command) for command in document.pop("commands"))
    if not len(samples) == len(snapshots) == len(commands) or not samples:
        raise ValueError("信号、快照与输入记录长度不一致")
    declared = {item["key"] for item in document["signals"]}
    if (declared not in (LEGACY_SIGNAL_KEYS, PRE_ALIGN_SIGNAL_KEYS, PRE_UNSPRUNG_SIGNAL_KEYS,set(SIGNAL_BY_KEY))
        or any(set(row) != declared for row in samples)):
        raise ValueError("信号字段与当前或旧版完整目录不一致")
    options = LabOptions(**document["summary"]["options"])
    saved_config = json.loads((folder/"vehicle.json").read_text(encoding="utf-8"))
    if saved_config != document["vehicle_config"]:
        raise ValueError("车辆文件与实验中保存的完整配置不一致")
    if document.get("parameter_metadata") is not None:
        validate_fit_metadata(document["parameter_metadata"])
    for index, (row, state, command) in enumerate(zip(samples, snapshots, commands)):
        if (state.tick != snapshots[0].tick+index or row["tick"] != state.tick
            or not math.isclose(row["time"], index/120, abs_tol=1e-9)
            or not all(math.isfinite(value) for value in (*state.player.position, *state.player.orientation))):
            raise ValueError("信号与动画的120Hz时间或姿态不一致")
        expected = sample_signals(state, command, snapshots[0].time)
        expected["path_error"] = path_error(options, state.player, snapshots[0].player)
        # 旧记录严格验证原字段，再从其已有快照补新显示字段，不重算物理或覆盖原文件。
        if any(key not in expected for key in row) or {key: expected[key] for key in row} != row:
            raise ValueError("信号数据与对应的真实动画快照不一致")
    if set(samples[0]) != set(expected):
        document["display_signal_upgrade"] = {"basis": "original snapshots", "analysis": "current lab_signals"}
        samples = tuple({**sample_signals(state, command, snapshots[0].time),
                         "path_error": path_error(options, state.player, snapshots[0].player)}
                        for state, command in zip(snapshots, commands, strict=True))
    return LabRecord(document, samples, snapshots, commands)


def recalculate(record):
    """同版本逐拍重算保存的精确命令；回放动画本身不计算物理。"""
    from lab_experiment import LabExperiment, LabOptions
    from vehicle_designs import vehicle_design
    from vehicle_parameters import config_from_document

    if record.metadata["summary"]["reason"] in ("failed", "collision", "reset"):
        raise ValueError("终止试验可分析已完成记录；自动复算仅接受暂停、停止或时长完成的试验")
    if record.metadata["source_start"] != model_fingerprint():
        raise ValueError("当前模型版本与记录不同，不能声明确定性重算")
    options = LabOptions(**record.metadata["summary"]["options"])
    config = config_from_document(record.metadata["vehicle_config"], vehicle_design(options.vehicle_id).config)
    parameter_metadata = record.metadata.get("parameter_metadata")
    run = LabExperiment(options, config=config, parameter_metadata=parameter_metadata)
    try:
        for command in record.commands[1:]:
            run.step(command)
        return LabRecord.from_run(run)
    finally:
        run.close()
