"""同车、同工况、同直接命令的参考/游戏积分对照与报告。"""

import html
import json
import math
from time import perf_counter

from lab_experiment import LabExperiment, LabOptions
from lab_records import LabRecord, export_record, model_fingerprint, plot_svg
from lab_runtime import runtime_fingerprint
from vehicle_designs import vehicle_design
from vehicle_parameters import config_from_document
from vehicle_workspace import WorkspaceVehicle


def reference_vehicle(record):
    """只有正常完成的参考试验可以作为已试验车辆。"""
    if record.metadata["summary"]["reason"] not in ("stopped", "time_limit"):
        raise ValueError("请先完成一次正常结束的试验，再应用车辆或运行游戏对照。")
    if record.metadata.get("runtime_profile", "reference") != "reference":
        raise ValueError("请选择参考实验记录，游戏对照记录不能代替参考试验。")
    options = record.metadata["summary"]["options"]
    design = vehicle_design(options["vehicle_id"])
    config = config_from_document(record.metadata["vehicle_config"], design.config)
    return WorkspaceVehicle(design.id, config, record.metadata.get("parameter_metadata"))


class GameComparison:
    def __init__(self, reference):
        vehicle = reference_vehicle(reference)
        if not reference.metadata["source_start"] == reference.metadata["source_end"] == model_fingerprint():
            raise ValueError("参考试验源码与当前版本不同，请重新运行参考试验。")
        if not reference.metadata.get("runtime_start") == reference.metadata.get("runtime_end") == runtime_fingerprint():
            raise ValueError("参考试验运行库与当前环境不同，请重新运行参考试验。")
        self.reference = reference
        self.run = LabExperiment(LabOptions(**reference.metadata["summary"]["options"]),
                                 config=vehicle.config, parameter_metadata=vehicle.parameter_metadata,
                                 runtime_profile="game")
        self.command_index = 1

    @property
    def done(self):
        return self.run.done or self.command_index == len(self.reference.commands)

    def advance(self, budget_seconds=.006):
        started = perf_counter()
        while not self.done and perf_counter()-started < budget_seconds:
            self.run.step(self.reference.commands[self.command_index])
            self.command_index += 1

    def close(self):
        self.run.close()

    def export(self, folder):
        game = LabRecord.from_run(self.run)
        export_record(self.reference, folder/"reference")
        export_record(game, folder/"game")
        report = comparison_report(self.reference, game)
        (folder/"comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                        allow_nan=False)+"\n", encoding="utf-8")
        def cell(value):
            return "未满足条件" if value is None else f"{value:.5g}"

        rows = "".join(f"<tr><td>{html.escape(item['label'])}</td><td>{cell(item['reference'])}</td>"
                       f"<td>{cell(item['game'])}</td><td>{cell(item['delta'])}</td><td>{item['unit']}</td></tr>"
                       for item in report["metrics"])
        plots = "".join(plot_svg((self.reference, game), key) for key in ("speed", "ax", "yaw", "steering"))
        details = html.escape(json.dumps({k: v for k, v in report.items() if k != "metrics"},
                                        ensure_ascii=False, indent=2))
        page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>车辆游戏对照</title>
<style>body{{font:16px system-ui;background:#f3efe3;color:#102b3a;max-width:1000px;margin:40px auto;padding:24px}}td,th{{padding:10px;border-bottom:1px solid #bbc9c8}}svg{{width:100%}}pre{{white-space:pre-wrap}}</style>
<h1>同一车辆 · 参考实验 / 游戏积分对照</h1>
<p>海蓝：参考；橙色：游戏。两者均为120Hz、直接VehicleCommand输入。仅游戏配置使用每拍一次机械求解。
闭环工况沿用参考驾驶员的命令，不在游戏侧重新纠偏；游戏键盘辅助与道路交通另由实际驾驶体验。
两次计算均使用当前 {report['precision_bits']} 位数学运行库，跨运行库误差另行测量。</p>
<p>此报告显示模型差异，尚未设置合格误差范围。未完成停车的距离不作停车距离比较。
公共时间段曲线偏差与各自终止时刻指标分别列出；计算耗时不含初始化、渲染和导出。</p>
<table><tr><th>指标</th><th>参考</th><th>游戏</th><th>游戏−参考</th><th>单位</th></tr>{rows}</table>{plots}
<h2>运行条件与公共时间段误差</h2><pre>{details}</pre>
<p><a href="reference/report.html">参考完整记录</a> · <a href="game/report.html">游戏完整记录</a></p></html>'''
        path = folder/"report.html"
        path.write_text(page, encoding="utf-8")
        return path


def comparison_report(reference, game):
    old, new = reference.metadata["summary"], game.metadata["summary"]
    count = min(len(reference.samples), len(game.samples))
    metrics = []
    for key, label, unit in (("stopping_distance_m", "停车距离", "m"),
            ("distance_m", "各自记录行驶距离", "m"), ("simulation_seconds", "记录时长", "s"),
            ("peak_deceleration_mps2", "峰值纵向减速度", "m/s²"),
            ("peak_lateral_acceleration_mps2", "峰值横向加速度", "m/s²"),
            ("peak_yaw_rate_radps", "峰值横摆角速度", "rad/s"),
            ("compute_seconds", "离线计算耗时", "s")):
        a, b = old[key], new[key]
        delta = b-a if a is not None and b is not None else None
        metrics.append({"key": key, "label": label, "unit": unit, "reference": a, "game": b, "delta": delta})
    errors = {}
    for key in ("speed", "ax", "ay", "yaw", "roll"):
        differences = [b[key]-a[key] for a, b in zip(reference.samples[:count], game.samples[:count], strict=True)
                       if a[key] is not None and b[key] is not None]
        errors[key] = {"rmse": math.sqrt(sum(x*x for x in differences)/len(differences)) if differences else None,
                       "max_absolute": max(map(abs, differences)) if differences else None}
    configs = (reference.metadata["vehicle_config"], game.metadata["vehicle_config"])
    return {"schema": "coastal-game-comparison-v1", "assessment": "未设置合格阈值",
            "reference_reason": old["reason"], "game_reason": new["reason"],
            "game_end_condition": new["reason"] or "reference_commands_exhausted",
            "precision_bits": reference.metadata["runtime_start"]["math_scalar_bits"],
            "reference_ticks": old["ticks"], "game_ticks": new["ticks"],
            "common_seconds": (count-1)/120,
            "same_command_prefix": reference.commands[:count] == game.commands[:count],
            "config_changes": {key: {"reference": configs[0][key], "game": configs[1][key]}
                               for key in configs[0] if configs[0][key] != configs[1][key]},
            "common_signal_errors": errors, "metrics": metrics}
