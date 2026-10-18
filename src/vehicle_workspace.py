"""游戏与实验室交接同一份工程车辆；文件保存完整参考配置。"""

import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from paths import user_data
from vehicle_config import VehicleConfig
from vehicle_designs import vehicle_design
from vehicle_parameters import config_from_document
from workshop import validate_receipt


def workspace_vehicle_path():
    return user_data()/"design-loop"/"vehicle.json"


@dataclass(frozen=True)
class WorkspaceVehicle:
    design_id: str
    config: VehicleConfig
    parameter_metadata: dict | None = None
    report_path: str | None = None
    workshop_result: dict | None = None
    scheme_id: str | None = None

    def with_electronics(self, config):
        """带回游戏实际开关；保留原工程配置的机械子步数。"""
        updated = replace(self.config, braking=config.braking,
                          traction=config.traction, stability=config.stability)
        return replace(self, config=updated,
                       workshop_result=self.workshop_result if updated == self.config else None,
                       scheme_id=self.scheme_id if updated == self.config else None)

    def save(self, path=None):
        path = workspace_vehicle_path() if path is None else Path(path)
        validate_receipt(self.workshop_result, self.config)
        if self.scheme_id is not None and (not isinstance(self.scheme_id, str)
                or re.fullmatch(r"[0-9a-f]{32}", self.scheme_id) is None):
            raise ValueError("车辆方案编号无效")
        document = {"schema": "coastal-workspace-vehicle-v1", "design_id": self.design_id,
                    "vehicle_config": asdict(self.config), "parameter_metadata": self.parameter_metadata,
                    "report_path": self.report_path, "workshop_result": self.workshop_result,
                    "scheme_id": self.scheme_id}
        payload = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(payload+"\n", encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path=None):
        path = workspace_vehicle_path() if path is None else Path(path)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        if not isinstance(document, dict) or document["schema"] != "coastal-workspace-vehicle-v1":
            raise ValueError("未知车辆工作区文件格式")
        design = vehicle_design(document["design_id"])
        metadata = document["parameter_metadata"]
        if metadata is not None and not isinstance(metadata, dict):
            raise TypeError("车辆参数来源须为对象")
        report = document["report_path"]
        if report is not None and not isinstance(report, str):
            raise TypeError("车辆试验报告路径须为字符串")
        config = config_from_document(document["vehicle_config"], design.config)
        receipt = document.get("workshop_result")
        validate_receipt(receipt, config)
        scheme_id = document.get("scheme_id")
        if scheme_id is not None and (not isinstance(scheme_id, str)
                or re.fullmatch(r"[0-9a-f]{32}", scheme_id) is None):
            raise ValueError("车辆方案编号无效")
        return cls(design.id, config, metadata, report, receipt, scheme_id)
