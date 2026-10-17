"""离开实验台时保留编辑与分析状态；只携带数据，不保留物理世界。"""

from dataclasses import dataclass
from pathlib import Path

from lab_experiment import MANEUVERS, LabOptions
from lab_records import LabRecord
from vehicle_config import VehicleConfig
from vehicle_designs import DESIGN_VEHICLES, vehicle_design
from vehicle_parameters import config_from_document


@dataclass(frozen=True)
class LabWorkspace:
    vehicle_id: str
    maneuver: str
    fields: dict
    manual_fields: dict
    abs_index: int
    esc_index: int
    plot_index: int
    config: VehicleConfig | None
    parameter_metadata: dict | None
    record: LabRecord | None
    baseline: LabRecord | None
    view_index: int
    camera_mode: int
    play_speed: float
    last_report: Path | None

    @classmethod
    def capture(cls, app):
        return cls(DESIGN_VEHICLES[app.vehicle_menu.selectedIndex].id,
                   tuple(MANEUVERS)[app.maneuver_menu.selectedIndex],
                   {key: entry.get() for key, entry in app.entries.items()},
                   {key: entry.get() for key, entry in app.manual_entries.items()},
                   app.abs_menu.selectedIndex, app.esc_menu.selectedIndex, app.plot_menu.selectedIndex,
                   app.engineered_config, app.parameter_metadata, app.active_record(), app.baseline,
                   app.view_index, app.scene.camera_mode, app.play_speed, app.last_report)

    def restore(self, app):
        app.set_options(LabOptions(vehicle_id=self.vehicle_id, maneuver=self.maneuver))
        app.engineered_config = self.config
        app.engineered_vehicle_id = self.vehicle_id if self.config is not None else None
        app.parameter_metadata = self.parameter_metadata
        for key, text in self.fields.items():
            app.entries[key].enterText(text)
        for key, text in self.manual_fields.items():
            app.manual_entries[key].enterText(text)
        app.abs_menu.set(self.abs_index)
        app.esc_menu.set(self.esc_index)
        app.refresh_configuration_note()
        app.record, app.baseline = self.record, self.baseline
        app.last_report = self.last_report
        app.scene.camera_mode, app.play_speed = self.camera_mode, self.play_speed
        if self.record is not None:
            options = LabOptions(**self.record.metadata["summary"]["options"])
            design = vehicle_design(options.vehicle_id)
            config = config_from_document(self.record.metadata["vehicle_config"], design.config)
            app.scene.set_vehicle(design, config)
            app.scene.set_trial(options, self.record.snapshots[0].player)
            app.model_note.setText(f"{self.record.metadata['vehicle_name']} · 已恢复试验记录")
            app.status.setText("试验已恢复")
            app.present_summary(self.record.metadata["summary"])
        else:
            app.scene.set_vehicle(vehicle_design(self.vehicle_id), self.config)
        app.plot_menu.set(self.plot_index)
        app.refresh_plots()
        app.show_sample(self.view_index)
        app.playhead = app.view_index/120
        app.notice.setText("已返回原实验台：工况、输入、A/B结果与时间游标已恢复；编辑值重新试验后生效。")
