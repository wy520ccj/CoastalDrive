"""方案命名、同条件比较、恢复分析与同车试驾。"""

from dataclasses import replace

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectEntry, DirectFrame
from panda3d.core import TextNode

from ui.lab_diagrams import car, lengths
from ui.lab_widgets import (
    BORDER,
    LAB_ACCENT_A,
    LAB_ACCENT_B,
    LAB_BG,
    LAB_CARD,
    LAB_FIELD,
    LAB_TEXT,
    MUTED,
    rounded_panel,
)
from ui.virtual_driver import VirtualDriverPanel
from vehicle_designs import vehicle_design
from vehicle_schemes import compare_schemes, list_schemes, save_scheme, sync_road_progress


class SchemesPanel:
    def __init__(self, app):
        self.app = app
        self.schemes = []
        self.indices = [0, 0]
        self.menus = [None, None]
        self.root = DirectFrame(parent=app.root, frameColor=LAB_BG,
                                frameSize=(-1.78, 1.78, -1.5, 1.5), sortOrder=97, state=DGG.NORMAL)
        rounded_panel(self.root, "schemes-edge", (-1.704, 1.704, -.934, .814), BORDER, .026)
        rounded_panel(self.root, "schemes-card", (-1.70, 1.70, -.93, .81), LAB_CARD, .024)
        glyphs = TextNode('scheme-button-glyphs')
        glyphs.setFont(app.font)
        glyphs.setText('关闭保存当前试验为新方案载回B方案比较AB曲线驾驶虚拟试车员‹›')
        self.button_geometry = glyphs.generate()
        DirectFrame(parent=self.root, frameColor=LAB_ACCENT_B, frameSize=(-1.55, -1.54, .690, .754))
        app.text("我的方案", -1.50, .704, .060, parent=self.root, font=app.heading_font)
        app.button("关闭", 1.47, .722, .28, self.hide, parent=self.root)
        app.text("选择两套方案进行对比。", -1.50, .575, .036,
                 MUTED, parent=self.root)
        self.save_panel = DirectFrame(parent=self.root, frameColor=LAB_CARD,
            frameSize=(-1.66, 1.66, -.90, .45), sortOrder=100, state=DGG.NORMAL)
        app.text("保存方案", -1.45, .28, .048, parent=self.save_panel)
        self.name_entry = DirectEntry(parent=self.save_panel, initialText="我的方案", text_font=app.font,
            text_fg=LAB_TEXT, scale=.042, width=1.9/.042 - .56, numLines=1, focus=0,
            frameSize=(-.28, 1.9/.042 - .28, -.52, 1.12),
            frameColor=LAB_FIELD, pos=(-1.45 + .28 * .042, 0, -.02), relief=DGG.FLAT,
            focusInCommand=app.blur_entries)
        app.button("保存", 1.04, -.78, .55, self.save_current, parent=self.save_panel, accent=True)
        app.button("取消", .34, -.78, .55, self.close_save, parent=self.save_panel)
        self.save_panel.hide()
        app.button("保存新方案", -1.13, -.83, .70, self.toggle_save, parent=self.root)
        self.details = DirectFrame(parent=self.root, frameColor=LAB_CARD,
            frameSize=(-1.66, 1.66, -.90, .36), sortOrder=99, state=DGG.NORMAL)
        app.text("方案详情", -1.47, .24, .046, parent=self.details)
        self.left_text = app.text("", -1.45, .10, .040, parent=self.details)
        self.right_text = app.text("", .10, .10, .040, parent=self.details)
        for target in (self.left_text, self.right_text):
            target.textNode.setWordwrap(36)
        self.comparison = app.text("", -1.45, -.13, .040, LAB_ACCENT_A, parent=self.details)
        self.metric_headers = []
        for label, x in (('指标', -1.42), ('方案 A', -.22), ('方案 B', .58), ('差值 B−A', 1.38)):
            node = app.text(label, x, -.22, .040, MUTED, parent=self.details)
            if label != '指标':
                node['align'] = TextNode.ARight
            self.metric_headers.append(node)
        self.metric_rows, self.metric_bands = [], []
        for index in range(5):
            z = -.30-index*.065
            row = []
            for x in (-1.42, -.22, .58, 1.38):
                node = app.text('', x, z, .040, LAB_TEXT if x != 1.38 else LAB_ACCENT_A, parent=self.details)
                if x != -1.42:
                    node['align'] = TextNode.ARight
                row.append(node)
            self.metric_rows.append(row)
        self.comparison_note = app.text('', -1.45, -.62, .040, MUTED, parent=self.details)
        self.comparison_note.textNode.setWordwrap(66)
        app.button("收起", 1.23, -.83, .38, self.details.hide, parent=self.details)
        self.details.hide()
        self.empty_guide = [app.text(label, x, -.24, .038, MUTED, parent=self.root)
                           for x, label in ((-1.42, '1  完成试验'), (-.38, '2  保存方案'), (.62, '3  改装再试'))]
        self.status = app.text("", -1.50, -.71, .036, LAB_ACCENT_A, parent=self.root)
        self.status.textNode.setWordwrap(85)
        self.hero = self.root.attachNewNode('scheme-hero')
        self.hero_title = app.text('', -1.42, -.06, .046, parent=self.root)
        self.hero_values = [app.text('', x, -.28, .050, color, parent=self.root)
                            for x, color in ((-1.42, LAB_ACCENT_A), (.15, LAB_ACCENT_B))]
        self.hero_note = app.text('', -1.42, -.59, .038, MUTED, parent=self.root)
        app.button('车辆与数据 ›', -.34, -.83, .78, self.toggle_details, parent=self.root)
        self.load_button = app.button("载入方案二", .43, -.83, .68, self.load_right, parent=self.root)
        self.curves_button = app.button("比较曲线", .18, -.83, .84, self.show_curves, parent=self.details)
        self.drive_button = app.button("试驾方案二", 1.19, -.83, .76, self.drive_right, parent=self.root, accent=True)
        for side, x in enumerate((-1.50, .07)):
            app.text('方案一' if side == 0 else '方案二', x, .42, .036, MUTED, parent=self.root)
            app.button("‹", x+.065, .32, .11, lambda s=side: self.move(s, -1), parent=self.root)
            app.button("›", x+1.365, .32, .11, lambda s=side: self.move(s, 1), parent=self.root)
        self.virtual_driver = VirtualDriverPanel(app, self)
        app.button("试车对比", .83, .722, .82, self.virtual_driver.show, parent=self.root)
        self.root.hide()

    def close_save(self):
        self.name_entry["focus"] = 0
        self.save_panel.hide()

    def toggle_save(self):
        self.details.hide()
        self.save_panel.show() if self.save_panel.isHidden() else self.close_save()

    def toggle_details(self):
        self.close_save()
        self.details.show() if self.details.isHidden() else self.details.hide()

    def draw_summary(self, comparison=None):
        self.hero.removeNode()
        self.hero = self.root.attachNewNode('scheme-hero')
        for node in self.hero_values:
            node.setText('')
        self.hero_title.setText('')
        self.hero_note.setText('')
        if not self.schemes:
            return
        for x, color in ((-.79, LAB_ACCENT_A), (.79, LAB_ACCENT_B)):
            car(self.hero, x, -.06, .94, color)
        if comparison is not None and comparison['rows']:
            label, a, b, unit = comparison['rows'][0]
            self.hero_title.setText(label)
            for node, caption, value in zip(self.hero_values, ('方案一', '方案二'), (a, b), strict=True):
                node.setText(f'{caption}  {value:.2f} {unit}')
            lengths(self.hero, a, b, left=-1.40, right=1.35, top=-.39, gap=.10, vehicles=False)
            self.hero_note.setText('相同条件下的试验结果' if comparison['comparable'] else '条件不同，仅并列查看；不计算收益')
        else:
            self.hero_title.setText('暂无可对比数据')
            self.hero_note.setText('车辆改动和试验记录见“车辆与数据”。')

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
        self.details.hide()
        self.save_panel.hide()
        self.virtual_driver.hide()
        self.name_entry["focus"] = 0
        for menu in self.menus:
            if menu is not None:
                menu.hidePopupMenu()
        self.root.hide()

    def escape(self):
        if not self.virtual_driver.root.isHidden():
            self.virtual_driver.escape()
        elif not self.details.isHidden():
            self.details.hide()
        elif not self.save_panel.isHidden():
            self.name_entry["focus"] = 0
            self.save_panel.hide()
        else:
            self.hide()

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
        items = [f"{item.name[:19]}"
                 for item in self.schemes[offset:offset+6]] or ["暂无方案"]
        menu = self.app.option(items, -1.35 if side == 0 else .22, .32, 1.13,
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
        self.draw_summary()
        for button in (self.load_button, self.curves_button, self.drive_button):
            button["state"] = DGG.NORMAL if self.schemes else DGG.DISABLED
        for row in self.metric_rows:
            for node in row:
                node.setText('')
        for band in self.metric_bands:
            band.hide()
        for node in self.metric_headers:
            node.show() if self.schemes else node.hide()
        for node in self.empty_guide:
            node.hide() if self.schemes else node.show()
        if not self.schemes:
            self.left_text.setText("A · 暂无保存")
            self.right_text.setText("B · 暂无保存")
            self.comparison.setText("还没有保存的方案")
            self.hero_title.setText("还没有保存的方案")
            self.comparison_note.setText("完成一次试验并命名保存，再改另一处、试验并保存，就能比较。")
            return
        for side, target in enumerate((self.left_text, self.right_text)):
            item = self.selected(side)
            receipt = item.vehicle.workshop_result
            award = (f"{receipt['medal']}牌 · "+("道路已完成" if receipt["road_validated"] else "待道路验证")) if receipt else "试验方案 · 未获工坊通过奖牌"
            config = item.vehicle.config
            hardware = (f"前胎 {config.lateral_stiffness/1000:g}k · 防倾 "
                        f"{config.suspension_antiroll_rates[0]/1000:g}/{config.suspension_antiroll_rates[1]/1000:g}k · 重心{config.center_of_mass_height:g}m"
                        if item.challenge is not None and ("tire_index" in item.challenge
                            or item.challenge['challenge_id'] == 'reference-cornering-budget-v1') else
                        f"前制动 {config.front_brake_share:.0%} · 质心 {config.center_of_mass_height:g}m")
            target.setText(f"{vehicle_design(item.vehicle.design_id).name}\n{hardware}\n{award}")
        try:
            result = compare_schemes(self.selected(0), self.selected(1))
            self.draw_summary(result)
            self.comparison.setText("同条件指标 · 差值 B−A" if result["comparable"] else "条件不同 · 仅并列查看")
            self.comparison_note.setText(result["note"] if result["comparable"] else
                "、".join(result["mismatches"])+"；不计算收益，可载回B试验后统一条件。")
            self.curves_button['state'] = DGG.NORMAL if result['comparable'] else DGG.DISABLED
            for index, (label, a, b, unit) in enumerate(result["rows"]):
                values = (f'{label} ({unit})', f'{a:.3f}', f'{b:.3f}', f'{b-a:+.3f}' if result['comparable'] else '—')
                for node, value in zip(self.metric_rows[index], values, strict=True):
                    node.setText(value)
            if not result['rows']:
                self.comparison_note.setText(self.comparison_note.getText()+" 当前试验窗没有可比较的有效指标。")
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.comparison.setText("原始记录不可用")
            self.comparison_note.setText(str(error))
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
            self.close_save()
        except (OSError, ValueError, KeyError, TypeError) as error:
            app.show_error("方案未保存，当前试验与其他方案保留", error)
            return
        self.status.setText(f"已独立保存「{item.name}」及完整试验；可载入方案二，或试驾方案二。")

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
            item.vehicle.save(self.app.workspace_path)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.app.show_error("方案未应用，当前试验与车辆保留", error)
            return
        self.hide()
        self.app.workspace_vehicle = item.vehicle
        self.app.next_drive = True
        self.app.back_to_game()
