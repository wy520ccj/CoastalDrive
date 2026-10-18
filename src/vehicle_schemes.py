"""独立保存工程方案及其原始试验；没有第二份运行中的车辆状态。"""

import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import workshop
import workshop_cornering as cornering
from lab_game_comparison import reference_vehicle
from lab_metrics import engineering_analysis
from lab_records import export_record, load_record
from paths import user_data
from vehicle_parameters import load_vehicle_config
from vehicle_workspace import WorkspaceVehicle


def scheme_library_path():
    return user_data()/"design-loop"/"schemes"


def valid_name(name):
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 24 or any(ord(c) < 32 for c in name):
        raise ValueError("方案名称请填写1–24个字，不含换行")
    return name.strip()


def scheme_folder(root, identity):
    if not isinstance(identity, str) or re.fullmatch(r"[0-9a-f]{32}", identity) is None:
        raise ValueError("方案编号无效")
    return Path(root)/identity


def checked_challenge(receipt, baseline, record):
    if receipt is None:
        return None
    if baseline is None:
        raise ValueError("工坊方案缺少原始A基线")
    if receipt["challenge_id"] == cornering.CHALLENGE_ID:
        actual = cornering.evaluate(baseline, record, receipt["tire_index"],
                                    receipt["balanced_bar"], receipt["lower_cg"])
    elif receipt["challenge_id"] == workshop.CHALLENGE_ID:
        actual = workshop.evaluate(baseline, record, receipt["share_index"], receipt["large_brakes"])
    else:
        raise ValueError("未知工坊方案")
    if actual != {**receipt, "road_validated": False}:
        raise ValueError("工坊成绩与原始A/B不符")
    return actual


@dataclass(frozen=True)
class SavedScheme:
    id: str
    name: str
    created: str
    folder: Path
    vehicle: WorkspaceVehicle
    challenge: dict | None

    def records(self):
        record = load_record(self.folder/"trial")
        baseline = load_record(self.folder/"trial"/"baseline-A") if (self.folder/"trial"/"baseline-A").is_dir() else None
        vehicle = reference_vehicle(record)
        if (vehicle.config != self.vehicle.config or vehicle.design_id != self.vehicle.design_id
                or vehicle.parameter_metadata != self.vehicle.parameter_metadata):
            raise ValueError("方案硬件/来源与试验记录不一致")
        if load_vehicle_config(self.folder/"trial"/"vehicle.json", vehicle.config) != vehicle.config:
            raise ValueError("试验配置文件与原始记录不一致")
        challenge = checked_challenge(self.challenge, baseline, record)
        expected = challenge if challenge is not None and challenge["passed"] else None
        receipt = self.vehicle.workshop_result
        if receipt is not None:
            receipt = {**receipt, "road_validated": False}
        if receipt != expected:
            raise ValueError("方案奖牌与试验不一致")
        return baseline, record, challenge


def load_scheme(root, identity):
    folder = scheme_folder(root, identity)
    document = json.loads((folder/"scheme.json").read_text(encoding="utf-8"))
    if document["schema"] != "coastal-scheme-v1" or document["id"] != identity:
        raise ValueError("未知方案文件格式或编号不一致")
    name = valid_name(document["name"])
    created = document["created"]
    datetime.fromisoformat(created)
    vehicle = WorkspaceVehicle.load(folder/"vehicle.json")
    if vehicle is None or vehicle.scheme_id != identity:
        raise ValueError("方案缺少关联车辆")
    vehicle = replace(vehicle, report_path=str(folder/"trial"/"report.html"))
    return SavedScheme(identity, name, created, folder, vehicle, document["challenge"])


def list_schemes(root):
    root = Path(root)
    if not root.exists():
        return [], []
    schemes, errors = [], []
    for folder in sorted(root.iterdir()):
        if (not folder.is_dir() or re.fullmatch(r"[0-9a-f]{32}", folder.name) is None
                or not (folder/"scheme.json").is_file()):
            continue
        try:
            schemes.append(load_scheme(root, folder.name))
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append(f"{folder.name[:8]}：{error}")
    return sorted(schemes, key=lambda item: (item.created, item.id)), errors


def save_scheme(root, name, record, baseline=None, challenge=None):
    name = valid_name(name)
    vehicle = reference_vehicle(record)
    checked = checked_challenge(challenge, baseline, record)
    identity = uuid4().hex
    folder = scheme_folder(root, identity)
    folder.mkdir(parents=True, exist_ok=False)
    # Windows可能有后台读句柄阻止整目录改名；最后原子提交清单，才出现于方案列表。
    export_record(record, folder/"trial", baseline=baseline)
    vehicle = replace(vehicle, report_path=str(folder/"trial"/"report.html"), scheme_id=identity,
                      workshop_result=checked if checked is not None and checked["passed"] else None)
    vehicle.save(folder/"vehicle.json")
    document = {"schema": "coastal-scheme-v1", "id": identity, "name": name,
                "created": datetime.now(UTC).isoformat(), "challenge": checked}
    temporary = folder/"scheme.json.tmp"
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(folder/"scheme.json")
    return load_scheme(root, identity)


def sync_road_progress(root, vehicle):
    """道路完成仅回写同编号同硬件的方案，不让其他车共享一次通过。"""
    if vehicle.scheme_id is None or vehicle.workshop_result is None or not vehicle.workshop_result["road_validated"]:
        return
    scheme = load_scheme(root, vehicle.scheme_id)
    stored = scheme.vehicle
    if (stored.config != vehicle.config or stored.workshop_result is None
            or {**stored.workshop_result, "road_validated": True} != vehicle.workshop_result):
        raise ValueError("道路成绩与保存方案不匹配")
    if not stored.workshop_result["road_validated"]:
        replace(stored, workshop_result=vehicle.workshop_result).save(scheme.folder/"vehicle.json")


def compare_schemes(left, right):
    """原始试验可比条件与硬件差异分开；不跨工况/控制器/版本生成收益。"""
    _, a, ca = left.records()
    _, b, cb = right.records()
    mismatches = []
    for record in (a, b):
        if (not record.metadata.get("source_start") or not record.metadata.get("runtime_start")
                or record.metadata["source_start"] != record.metadata["source_end"]
                or record.metadata["runtime_start"] != record.metadata["runtime_end"]):
            mismatches.append("版本证据缺失或试验中变化")
            break
    for key, label in (("source_start", "源码"), ("source_end", "末次源码"),
                       ("runtime_start", "运行库"), ("runtime_end", "末次运行库"),
                       ("driver", "驾驶控制器"), ("runtime_profile", "积分方式")):
        if a.metadata.get(key) != b.metadata.get(key):
            mismatches.append(label)
    if a.metadata["summary"]["options"] != b.metadata["summary"]["options"]:
        mismatches.append("试验工况/车型/路面")
    if ca is None or cb is None or ca["challenge_id"] != cb["challenge_id"]:
        analyses = [engineering_analysis(record.samples, record.snapshots,
                    record.metadata["summary"]["options"], record.metadata["summary"]["reason"])
                    for record in (a, b)]
        rows = [(left["label"], left["value"], right["value"], left["unit"])
                for left, right in zip(analyses[0]["metrics"], analyses[1]["metrics"], strict=True)
                if left["key"] == right["key"] and left["value"] is not None and right["value"] is not None][:5]
        return {"comparable": not mismatches, "mismatches": mismatches, "rows": rows,
                "note": "工程指标按原有适用窗计算；缺少有效窗的指标不生成数值。"}
    if ca["challenge_id"] == cornering.CHALLENGE_ID:
        rows = [("循迹误差", ca["candidate_metrics"]["mean_error_m"], cb["candidate_metrics"]["mean_error_m"], "m"),
                ("峰值侧偏", ca["candidate_metrics"]["peak_beta_deg"], cb["candidate_metrics"]["peak_beta_deg"], "°"),
                ("峰值侧倾", ca["candidate_metrics"]["peak_roll_deg"], cb["candidate_metrics"]["peak_roll_deg"], "°"),
                ("速度偏差", ca["candidate_metrics"]["max_speed_error_kph"], cb["candidate_metrics"]["max_speed_error_kph"], "km/h")]
    else:
        rows = [("停车距离", ca["candidate_m"], cb["candidate_m"], "m"),
                ("峰值横摆", ca["peak_yaw_radps"], cb["peak_yaw_radps"], "rad/s")]
    rows.append(("预算", ca["cost"], cb["cost"], "点"))
    return {"comparable": not mismatches, "mismatches": mismatches,
            "rows": rows, "note": "差值为B−A，同时比较副作用与预算。"}
