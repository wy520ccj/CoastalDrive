"""同策略道路A/B：顺序拥有唯一Simulation，完整保存完成步/请求。"""

import csv
import hashlib
import html
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from time import perf_counter

from driving_modes import DrivingMode
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from road_review import gate_crossings
from simulation import Simulation
from slalom_lesson import GATES, SlalomLesson
from snapshot_wire import encode_snapshots
from vehicle_state import FIXED_DT
from virtual_test_driver import POLICY, VirtualTestDriver, target_x

ENVIRONMENT = {"seed": 0, "track": "endless", "road_shape": "straight", "traffic_count": 0,
               "road_friction": 1.1, "runtime_profile": "game", "decision_ticks": 6}


class TrialScores:
    """只供课题规则使用，不读写玩家成绩或奖牌。"""
    def __init__(self):
        self.best = None
        self.notice = ""

    def record(self, seconds):
        self.best = seconds


@dataclass(frozen=True)
class RoadRecord:
    metadata: dict
    snapshots: tuple
    controls: tuple
    rows: tuple


@dataclass(frozen=True)
class RoadResults:
    """同窗交接只携带结束记录，不保留上一世界或试车控制器。"""
    records: tuple
    status: str
    done: bool = True

    def close(self):
        pass


class RoadTrial:
    def __init__(self, vehicle):
        self.original = vehicle
        self.policy, self.environment = POLICY.copy(), ENVIRONMENT.copy()
        self.config = replace(DrivingMode.GAME.configured_vehicle(base_config=vehicle.config),
                              road_friction=self.environment["road_friction"])
        self.source_start, self.runtime_start = model_fingerprint(), runtime_fingerprint()
        setup_started = perf_counter()
        self.simulation = Simulation(0, track="endless", road_shape="straight", traffic_count=0,
            config=self.config, input_config=DrivingMode.GAME.input_config, physics_workers=0)
        try:
            self.simulation.settle_initial()
            self.current = self.simulation.snapshot()
        except (ArithmeticError, ValueError, RuntimeError, OSError):
            self.simulation.close()
            raise
        self.initial = self.current
        self.initialization_seconds = perf_counter()-setup_started
        self.driver = VirtualTestDriver(self.config, self.initial.player.position[1], self.policy)
        self.lesson = SlalomLesson(self.initial.player.position[1], TrialScores(), self.config)
        self.snapshots, self.controls, self.rows = [self.initial], [], []
        self.control = None
        self.ticks, self.compute_seconds = 0, 0.
        self.closed = False
        self.end_reason = None

    @property
    def done(self):
        return self.lesson.snapshot.finished or self.end_reason is not None

    def step(self):
        if self.closed or self.done:
            raise RuntimeError("道路试车已停止")
        started = perf_counter()
        try:
            self._step()
        finally:
            self.compute_seconds += perf_counter()-started

    def _step(self):
        if self.ticks % 6 == 0:
            self.control = self.driver.sample(self.current, 6*FIXED_DT)
        self.simulation.step(self.control, FIXED_DT)
        self.current = self.simulation.snapshot()
        self.ticks += 1
        car = self.current.player
        elapsed = self.ticks*FIXED_DT
        result = self.lesson.update(car.position[1]+self.current.origin_y, car.velocity[1], elapsed,
            lateral=car.position[0], heading=car.heading, collisions=self.current.collisions,
            reset="player_reset" in self.current.events)
        self.snapshots.append(self.current)
        self.controls.append(self.control)
        self.rows.append({"tick": self.ticks, "time": elapsed,
            "position": result.position, "x": car.position[0], "speed_kph": car.speed*3.6,
            "path_error_m": car.position[0]-target_x(result.position),
            "steering_deg": car.steering, "beta_deg": car.dynamics.sideslip,
            "roll_deg": car.roll, "esc_active": car.stability_state.active, "gates": result.gates,
            "steering_request": self.control.steering, "throttle_request": self.control.throttle,
            "brake_request": self.control.brake})

    def stop(self, reason):
        if not self.done:
            self.end_reason = reason
            self.lesson.stop(reason)

    def record(self):
        if not self.done:
            raise ValueError("先结束或取消道路试车再保存结果")
        result = self.lesson.snapshot
        metrics = {"completed": result.succeeded, "valid_seconds": result.run_seconds if result.succeeded else None,
            "gates": result.gates, "reason": "完成全部6门（试车）" if result.succeeded else result.reason,
            "minimum_clearance_m": min(result.clearances) if result.clearances else None,
            "peak_beta_deg": max((abs(row["beta_deg"]) for row in self.rows), default=0.),
            "peak_roll_deg": max((abs(row["roll_deg"]) for row in self.rows), default=0.),
            "peak_steering_deg": max((abs(row["steering_deg"]) for row in self.rows), default=0.),
            "esc_seconds": sum(row["esc_active"] for row in self.rows)*FIXED_DT,
            "collisions": self.current.collisions}
        metadata = {"schema": "coastal-virtual-road-v1", "policy": self.policy, "environment": self.environment,
            "original_vehicle": asdict(self.original),
            "actual_config": asdict(self.config), "input_config": asdict(DrivingMode.GAME.input_config),
            "source_start": self.source_start, "source_end": model_fingerprint(),
            "runtime_start": self.runtime_start, "runtime_end": runtime_fingerprint(),
            "simulation_seconds": self.ticks*FIXED_DT, "compute_seconds": self.compute_seconds,
            "initialization_seconds": self.initialization_seconds,
            "initialization_ticks": self.simulation.initialisation_ticks,
            "ticks": self.ticks, "end_reason": self.end_reason or "course_finished", "result": asdict(result),
            "metrics": metrics, "updates_player_progress": False}
        return RoadRecord(metadata, tuple(self.snapshots), tuple(self.controls), tuple(self.rows))

    def close(self):
        if not self.closed:
            self.simulation.close()
            self.closed = True


class RoadComparison:
    def __init__(self, left, right):
        self.vehicles = (left, right)
        self.records = []
        self.index = 0
        self.status = "running"
        self.run = RoadTrial(left)

    @property
    def done(self):
        return self.status != "running"

    def advance(self, budget_seconds=.006):
        started = perf_counter()
        while not self.done and perf_counter()-started < budget_seconds:
            try:
                self.run.step()
            except (ArithmeticError, ValueError, RuntimeError, OSError):
                self.run.stop("physics_failed")
                self.status = "failed"
                self._finish_current()
                raise
            if self.run.done:
                try:
                    self._finish_current()
                except (ArithmeticError, ValueError, RuntimeError, OSError):
                    self.status = "failed"
                    raise
                if self.index == 0:
                    self.index = 1
                    try:
                        self.run = RoadTrial(self.vehicles[1])
                    except (ArithmeticError, ValueError, RuntimeError, OSError):
                        self.status = "failed"
                        raise
                else:
                    self.status = "complete"

    def close(self):
        if not self.done:
            self.run.stop("cancelled")
            self.status = "cancelled"
            self._finish_current()
        self.run.close()

    def _finish_current(self):
        try:
            self.records.append(self.run.record())
        finally:
            self.run.close()


def context_mismatches(records):
    mismatches = []
    for record in records:
        if (record.metadata["source_start"] != record.metadata["source_end"]
                or record.metadata["runtime_start"] != record.metadata["runtime_end"]):
            mismatches.append("试车中源码/运行库改变")
    if len(records) == 2:
        for key, label in (("source_start", "源码"), ("runtime_start", "运行库"),
                           ("environment", "道路工况"), ("policy", "试车策略"), ("input_config", "输入辅助")):
            if records[0].metadata[key] != records[1].metadata[key]:
                mismatches.append(label)
    return mismatches


def comparison_rows(records):
    rows = []
    if len(records) != 2:
        return rows
    comparable = not context_mismatches(records)
    for key, label, unit in (("valid_seconds", "有效用时", "s"), ("gates", "通过门数", "/6"),
            ("minimum_clearance_m", "最小车身余量", "m"), ("peak_beta_deg", "峰值侧偏", "°"),
            ("peak_roll_deg", "峰值侧倾", "°"), ("esc_seconds", "ESC介入时间", "s")):
        a, b = (record.metadata["metrics"][key] for record in records)
        delta = b-a if comparable and a is not None and b is not None else None
        rows.append({"key": key, "label": label, "unit": unit, "A": a, "B": b, "delta": delta})
    return rows


def path_svg(records):
    """按真实道路进度并列画轨迹；失败轨迹不外推到终点。"""
    width, height = 960, 250
    samples = [record.rows for record in records]
    limit = max(4., max((abs(row["x"]) for series in samples for row in series), default=0.))
    def point(distance, x):
        return f"{55+distance/320*(width-80):.2f},{height/2-x/limit*(height/2-40):.2f}"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="#fefcf5"/>']
    for x in (-limit, 0., limit):
        y = height/2-x/limit*(height/2-40)
        parts.append(f'<path d="M55 {y}H{width-25}" stroke="#c9d3cc"/><text x="5" y="{y+4}" font-size="13">{x:g}m</text>')
    target = " ".join(point(distance, target_x(distance)) for distance in range(0, 321, 2))
    parts.append(f'<polyline points="{target}" fill="none" stroke="#657878" stroke-dasharray="5 4"/>')
    for rows, color in zip(samples, ("#247e96", "#f47c24")):
        points = " ".join(point(row["position"], row["x"]) for row in rows)
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
    parts.append(f'<text x="55" y="{height-8}" font-size="13">0m / 起步</text><text x="{width-125}" y="{height-8}" font-size="13">320m / 终门</text></svg>')
    return "\n".join(parts)


def export_comparison(comparison, folder, names):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    for index, record in enumerate(comparison.records):
        target = folder/("A" if index == 0 else "B")
        target.mkdir()
        payload = encode_snapshots((record.snapshots, ()))
        (target/"snapshots.bin").write_bytes(payload)
        document = {**record.metadata, "snapshot_sha256": hashlib.sha256(payload).hexdigest(),
                    "controls": [asdict(control) for control in record.controls], "rows": record.rows,
                    "gate_crossings": gate_crossings(record)}
        (target/"trial.json").write_text(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        with (target/"signals.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=record.rows[0].keys() if record.rows else ("tick", "time"))
            writer.writeheader()
            writer.writerows(record.rows)
    rows = comparison_rows(comparison.records)
    summary = {"status": comparison.status, "names": names, "rows": rows,
               "context_mismatches": context_mismatches(comparison.records), "updates_player_progress": False,
               "gate_crossings": [gate_crossings(record) for record in comparison.records]}
    (folder/"comparison.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    def cell(value):
        return "未完成/无有效值" if value is None else f"{value:.3f}"
    table = "".join(f"<tr><td>{row['label']}</td><td>{cell(row['A'])}</td><td>{cell(row['B'])}</td>"
                    f"<td>{cell(row['delta'])}</td><td>{row['unit']}</td></tr>" for row in rows)
    details = "".join(f"<h2>{label} · {html.escape(names[index])}</h2><p>"
        +html.escape(record.metadata["metrics"]["reason"])+"</p><details><summary>完整配置、策略与版本证据</summary><pre>"
        +html.escape(json.dumps(record.metadata, ensure_ascii=False, indent=2))+"</pre></details>"
        for index, (label, record) in enumerate(zip(("A", "B"), comparison.records)))
    conditions = "条件一致，可比较差值。" if not summary["context_mismatches"] else (
        "条件变化，不计算差值："+"、".join(summary["context_mismatches"]))
    gates_table = ""
    for index, (distance, target) in enumerate(GATES):
        cells = []
        for side in range(2):
            gates = summary["gate_crossings"][side] if side < len(comparison.records) else []
            gate = gates[index] if index < len(gates) else None
            cells.append((f"{'通过' if gate['passed'] else '漏门'} / {gate['clearance_m']:+.3f}m / "
                          f"{gate['speed_kph']:.2f}km/h / {gate['control']['steering']:+.3f} → {gate['steering_deg']:+.2f}°")
                         if gate else "未判门 / 无数据")
        gates_table += (f"<tr><td>{index+1} / {distance:g}m / 目标{target:+g}m</td>"
                        f"<td>{cells[0]}</td><td>{cells[1]}</td></tr>")
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>虚拟试车员 A/B</title>
<style>body{{font:16px system-ui;background:#f3efe3;color:#102b3a;max-width:1100px;margin:40px auto;padding:24px}}td,th{{padding:10px;border-bottom:1px solid #bbc9c8}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}svg{{width:100%;margin:15px 0}}</style>
<h1>虚拟试车员 · 连续过门 A/B</h1><p>状态：{comparison.status}。固定60km/h目标、20Hz闭环策略、120Hz完整物理；游戏单机械步/原输入辅助，μ=1.1、种子0、无车流。</p>
<p>同一策略会按各车状态产生不同请求，不是相同命令回放或最优驾驶。只有完成课题者有有效用时；余量/侧偏等指标区间截止各自终点或失败步，失败者更短的采样窗不表示更好。不会更新玩家奖牌或道路进度。</p>
<p>{html.escape(conditions)}</p><table><tr><th>指标</th><th>A</th><th>B</th><th>B−A</th><th>单位</th></tr>{table}</table>
<h2>实际道路轨迹</h2><p>A海蓝 / B橙色 / 灰虚线为目标；横轴为行驶进度，纵轴为左右位置。失败步之后不补轨迹。</p>{path_svg(comparison.records)}
<h2>逐门复盘</h2><p>同位置首次向前过门；车速、朝向与实际转角由相邻完成步插值，转向请求为该步保持值。余量沿用原整车判门结果；缺失处不补数据。不由单项变化推断改装因果。</p>
<table><tr><th>门 / 位置 / 目标左右</th><th>A 状态 / 余量 / 车速 / 请求→转角</th><th>B 状态 / 余量 / 车速 / 请求→转角</th></tr>{gates_table}</table>
<p>每拍完整快照、控制请求、硬件、策略、源码与SDK首末摘要见A/B目录。逐步计算时间与初始化分别记录，不是实时FPS基准；不是实车标定。</p>{details}</html>'''
    (folder/"report.html").write_text(page, encoding="utf-8")
    return folder/"report.html"
