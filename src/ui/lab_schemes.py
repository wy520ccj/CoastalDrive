"""方案命名、同条件比较、恢复分析与同车试驾。"""

from dataclasses import replace

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectEntry, DirectFrame

from ui import theme
from ui.virtual_driver import VirtualDriverPanel
from vehicle_designs import vehicle_design
from vehicle_schemes import compare_schemes, list_schemes, save_scheme, sync_road_progress


class SchemesPanel:
    def __init__(self, app):
        self.app = app
        self.schemes = []
        self.indices = [0, 0]
        self.menus = [None, None]
        self.root = DirectFrame(parent=app.root, frameColor=(.04, .10, .14, .70),
                                frameSize=(-1.78, 1.78, -1, 1), sortOrder=97, state=DGG.NORMAL)
        DirectFrame(parent=self.root, frameColor=theme.PAPER_LIGHT, frameSize=(-1.70, 1.70, -.86, .79))
        app.text("工程方案库", -1.52, .63, .062, parent=self.root, font=app.heading_font)
        app.button("关闭", 1.42, .66, .28, self.hide, parent=self.root)
        app.text("方案名", -1.52, .48, .037, parent=self.root)
        self.name_entry = DirectEntry(parent=self.root, initialText="我的方案", text_font=app.font,
            text_fg=theme.INK, scale=.038, width=1.6/.038, numLines=1, focus=0,
            frameColor=(.94, .95, .92, 1), pos=(-1.24, 0, .48), relief=DGG.FLAT,
            focusInCommand=app.blur_entries)
        app.button("保存当前试验为新方案", .99, .49, 1.10, self.save_current, parent=self.root, accent=True)
        app.text("每次保存建立独立方案；同名保留多个版本。编辑草稿须重新试验。", -1.52, .37, .034,
                 theme.SEA, parent=self.root)
        self.left_text = app.text("", -1.52, .03, .035, parent=self.root)
        self.right_text = app.text("", .13, .03, .035, parent=self.root)
        for target in (self.left_text, self.right_text):
            target.textNode.setWordwrap(37)
        self.comparison = app.text("", -1.52, -.18, .035, parent=self.root)
        self.comparison.textNode.setWordwrap(82)
        self.status = app.text("", -1.52, -.55, .033, theme.SEA, parent=self.root)
        self.status.textNode.setWordwrap(88)
        self.load_button = app.button("载回 B 方案", -1.10, -.73, .76, self.load_right, parent=self.root)
        self.curves_button = app.button("比较 A/B 曲线", -.10, -.73, .84, self.show_curves, parent=self.root)
        self.drive_button = app.button("驾驶 B 方案", 1.00, -.73, .84, self.drive_right, parent=self.root, accent=True)
        for side, x in enumerate((-1.52, .13)):
            app.button("‹", x+.04, .14, .10, lambda s=side: self.move(s, -1), parent=self.root)
            app.button("›", x+1.42, .14, .10, lambda s=side: self.move(s, 1), parent=self.root)
        self.virtual_driver = VirtualDriverPanel(app, self)
        app.button("虚拟试车员 A/B", .63, .65, .92, self.virtual_driver.show, parent=self.root)
        self.root.hide()

    def show(self):
        app = self.app
        app.blur_entries()
        app.design_loop.hide()
        app.workshop.hide()
        for panel in (app.advanced_panel, app.manual_panel, app.details_panel, app.record_menu,
                      app.parameter_help.root, app.engineering_panel.root):
            panel.hide()
        if app.run_state is not None:
            app.run_state.paused = True
        try:
            if app.workspace_vehicle is not None:
                sync_road_progress(app.scheme_root, app.workspace_vehicle)
        except (OSError, ValueError, KeyError, TypeError) as error:
            app.show_error("方案道路进度未同步，仍可查看其他方案", error)
        try:
            self.refresh()
        except (OSError, ValueError, KeyError, TypeError) as error:
            app.show_error("方案列表未能读取，当前试验保留", error)
            return
        self.root.show()

    def hide(self):
        self.virtual_driver.hide()
        self.name_entry["focus"] = 0
        for menu in self.menus:
            if menu is not None:
                menu.hidePopupMenu()
        self.root.hide()

    def escape(self):
        self.virtual_driver.hide() if not self.virtual_driver.root.isHidden() else self.hide()

    def refresh(self, selected=None):
        if selected is None:
            selected = (self.selected(1).id if self.schemes else
                        self.app.workspace_vehicle.scheme_id if self.app.workspace_vehicle is not None else None)
        self.schemes, errors = list_schemes(self.app.scheme_root)
        if selected is not None:
            self.indices[1] = next((i for i, item in enumerate(self.schemes) if item.id == selected), self.indices[1])
        self.indices = [min(index, max(0, len(self.schemes)-1)) for index in self.indices]
        for side in (0, 1):
            self.build_menu(side)
        self.status.setText(f"已保存 {len(self.schemes)} 套方案。" +
                            (f" {len(errors)} 项损坏未载入；首项 {errors[0]}" if errors else ""))
        self.present()

    def build_menu(self, side):
        if self.menus[side] is not None:
            self.menus[side].hidePopupMenu()
            self.menus[side].destroy()
        offset = self.indices[side]//6*6
        items = [f"{'A' if side == 0 else 'B'} · {item.name[:14]} · {item.id[:4]}"
                 for item in self.schemes[offset:offset+6]] or ["暂无方案"]
        menu = self.app.option(items, -1.52 if side == 0 else .13, .24, 1.40,
                               lambda label: self.choose(side, offset), parent=self.root)
        self.menus[side] = menu
        menu.set(self.indices[side]-offset, fCommand=0)
        menu["state"] = DGG.NORMAL if self.schemes else DGG.DISABLED

    def choose(self, side, offset):
        self.indices[side] = offset+self.menus[side].selectedIndex
        self.present()

    def move(self, side, amount):
        if self.schemes:
            self.indices[side] = (self.indices[side]+amount) % len(self.schemes)
            self.build_menu(side)
            self.present()

    def selected(self, side):
        if not self.schemes:
            raise ValueError("请先保存一套已完成试验的方案")
        return self.schemes[self.indices[side]]

    def present(self):
        for button in (self.load_button, self.curves_button, self.drive_button):
            button["state"] = DGG.NORMAL if self.schemes else DGG.DISABLED
        if not self.schemes:
            self.left_text.setText("A · 暂无保存")
            self.right_text.setText("B · 暂无保存")
            self.comparison.setText("完成一次试验后，保存方案；再改另一处、试验并保存，就能比较。")
            return
        for side, target in enumerate((self.left_text, self.right_text)):
            item = self.selected(side)
            receipt = item.vehicle.workshop_result
            award = (f"{receipt['medal']}牌 · "+("道路已完成" if receipt["road_validated"] else "待道路验证")) if receipt else "试验方案 · 未获工坊通过奖牌"
            config = item.vehicle.config
            hardware = (f"前胎 {config.lateral_stiffness/1000:g}k · 防倾 "
                        f"{config.suspension_antiroll_rates[0]/1000:g}/{config.suspension_antiroll_rates[1]/1000:g}k · 重心{config.center_of_mass_height:g}m"
                        if item.challenge is not None and "tire_index" in item.challenge else
                        f"前制动 {config.front_brake_share:.0%} · 质心 {config.center_of_mass_height:g}m")
            target.setText(f"{item.name}\n{vehicle_design(item.vehicle.design_id).name}\n{hardware}\n{award}")
        try:
            result = compare_schemes(self.selected(0), self.selected(1))
            lines = ["同条件指标：A / B / B−A" if result["comparable"] else
                     "条件不同："+"、".join(result["mismatches"])+"；不计算收益"]
            for label, a, b, unit in result["rows"]:
                delta = f" / {b-a:+.3f}" if result["comparable"] else ""
                lines.append(f"{label}  {a:.3f} / {b:.3f}{delta} {unit}")
            lines.append(result["note"] if result["comparable"] else "可分别载回原始试验；保持同条件再比较改装。")
            self.comparison.setText("\n".join(lines))
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.comparison.setText("原始记录不可用："+str(error))
            self.curves_button["state"] = DGG.DISABLED
            try:
                self.selected(1).records()
            except (OSError, ValueError, KeyError, TypeError):
                self.load_button["state"] = self.drive_button["state"] = DGG.DISABLED

    def save_current(self):
        app = self.app
        record = app.active_record()
        if record is None:
            app.show_error("暂无试验，请先完成一次参考试验")
            return
        challenge = app.workshop.result if record is app.workshop.candidate else None
        baseline = app.workshop.baseline if challenge is not None else app.baseline
        try:
            item = save_scheme(app.scheme_root, self.name_entry.get(), record, baseline, challenge)
            self.refresh(item.id)
        except (OSError, ValueError, KeyError, TypeError) as error:
            app.show_error("方案未保存，当前试验与其他方案保留", error)
            return
        self.status.setText(f"已独立保存「{item.name}」及完整试验；可继续改装，或驾驶右侧方案。")

    def restore_right(self):
        item = self.selected(1)
        baseline, record, challenge = item.records()
        if not self.app.import_record(item.folder/"trial"):
            return None
        app = self.app
        app.baseline = baseline
        app.last_report = item.folder/"trial"/"report.html"
        app.workshop.set_topic(0)
        if challenge is not None:
            app.workshop.restore_saved(replace(item.vehicle, workshop_result=challenge))
        app.present_summary(record.metadata["summary"])
        app.refresh_plots()
        return item

    def load_right(self):
        try:
            item = self.restore_right()
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.app.show_error("方案未载入，当前试验保留", error)
            return
        if item is not None:
            self.hide()
            self.app.notice.setText(f"已载回「{item.name}」的配置与完整试验；重新开始试验后编辑生效。")

    def show_curves(self):
        try:
            result = compare_schemes(self.selected(0), self.selected(1))
            if not result["comparable"]:
                raise ValueError("比较曲线须保持同一工况/控制器/版本："+"、".join(result["mismatches"]))
            _, left, _ = self.selected(0).records()
            if self.restore_right() is None:
                return
            self.app.baseline = left
            self.app.present_summary(self.app.record.metadata["summary"])
            self.app.refresh_plots()
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.app.show_error("未建立方案曲线对比，当前试验保留", error)
            return
        self.hide()
        self.app.notice.setText("方案对比：A为左侧方案，B为右侧方案；工坊原始A基线另行保留。")

    def drive_right(self):
        try:
            item = self.restore_right()
            if item is None:
                return
            item.vehicle.save()
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.app.show_error("方案未应用，当前试验与车辆保留", error)
            return
        self.hide()
        self.app.workspace_vehicle = item.vehicle
        self.app.next_drive = True
        self.app.back_to_game()
