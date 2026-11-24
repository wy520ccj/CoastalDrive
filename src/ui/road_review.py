"""方案道路记录的二维复盘；拖动与按门只读取完成步。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectSlider
from panda3d.core import LineSegs

from road_review import focus_position, gate_crossings, sample_at
from slalom_lesson import GATES
from ui.lab_widgets import LAB_ACCENT_A, LAB_ACCENT_B, LAB_CARD, LAB_TEXT, LAB_TRACK
from virtual_test_driver import target_x


class RoadReviewPanel:
    def __init__(self, app, owner):
        self.app, self.owner = app, owner
        self.records, self.gates = (), []
        self.root = DirectFrame(parent=owner.root, frameColor=LAB_CARD,
            frameSize=(-1.70, 1.70, -.86, .79), sortOrder=103, state=DGG.NORMAL)
        app.text("道路复盘 · 同位置对照", -1.52, .64, .055, parent=self.root, font=app.heading_font)
        app.button("返回结果", 1.30, .65, .49, self.hide, parent=self.root)
        self.names = app.text("", -1.52, .56, .029, parent=self.root)
        app.text("A海蓝 / B橙色 / 灰线目标 · 按首次向前到达位置插值；未到达处留空\n"
                 "只读完成步，不推进物理；横轴道路进度、纵轴左右位置，两轴比例不同。",
                 -1.52, .49, .031, LAB_ACCENT_A, parent=self.root)
        self.gate_buttons = []
        for index, (_, x) in enumerate(GATES):
            button = app.button(f"{index+1} {'左' if x < 0 else '右' if x > 0 else '中'}", -1.27+index*.50,
                .34, .43, lambda i=index: self.select_gate(i), parent=self.root)
            self.gate_buttons.append(button)
        self.lines = self.root.attachNewNode("recorded-paths")
        self.cursor = self.root.attachNewNode("review-position")
        self.readout = app.text("", -1.52, -.19, .035, parent=self.root)
        self.details = [app.text("", x, -.27, .032, parent=self.root) for x in (-1.52, .15)]
        self.slider = DirectSlider(parent=self.root, range=(0., 320.), value=0., pageSize=5.,
            frameSize=(-1.40, 1.40, -.030, .030), frameVisibleScale=(1., .12),
            frameColor=LAB_TRACK, thumb_frameColor=LAB_ACCENT_B,
            thumb_frameSize=(-.018, .018, -.025, .025), thumb_relief=DGG.FLAT,
            relief=DGG.FLAT, borderWidth=(0, 0), pos=(0., 0., -.51), command=self.seek)
        app.text("拖动比较同位置。请求−1…1为该步保持比例，响应为前轮等效转角；t从起步计。",
                 -1.52, -.61, .029, LAB_ACCENT_A, parent=self.root)
        self.load_button = app.button("载回 B 继续试验", 1.12, -.73, 1., owner.load_right,
                   parent=self.root, accent=True)
        self.drive_button = app.button("驾驶 B 过门", 0., -.73, .96, owner.drive_slalom, parent=self.root)
        app.button("返回对比结果", -1.12, -.73, 1., self.hide, parent=self.root)
        self.root.hide()

    @staticmethod
    def point(distance, lateral):
        return (-1.50+distance/320*3., 0., .035+lateral/6*.155)

    def show(self):
        comparison = self.owner.comparison
        if comparison is None or not comparison.done or not comparison.records:
            return
        self.records = tuple(comparison.records)
        self.names.setText(f"A：{self.owner.names[0][:18]} / B：{self.owner.names[1][:18]}")
        self.load_button["state"] = self.drive_button["state"] = self.owner.drive_button["state"]
        try:
            self.gates = [gate_crossings(record) for record in self.records]
            focus = max(0., min(320., focus_position(self.records)))
        except ValueError as error:
            self.app.show_error("道路复盘记录不完整，原结果保留", error)
            return
        self.draw_paths()
        for index, button in enumerate(self.gate_buttons):
            button["state"] = DGG.NORMAL if any(len(gates) > index for gates in self.gates) else DGG.DISABLED
        self.slider["value"] = focus
        self.seek()
        self.root.show()

    def draw_paths(self):
        self.lines.removeNode()
        self.lines = self.root.attachNewNode("recorded-paths")
        grid = LineSegs()
        grid.setColor(.72, .79, .77, 1.)
        for lateral in (-6., 0., 6.):
            grid.moveTo(*self.point(0., lateral))
            grid.drawTo(*self.point(320., lateral))
        for distance, target in GATES:
            grid.moveTo(*self.point(distance, target-2.))
            grid.drawTo(*self.point(distance, target+2.))
        self.lines.attachNewNode(grid.create())
        target = LineSegs()
        target.setColor(.60, .65, .63, 1.)
        for distance in range(0, 321, 2):
            target.drawTo(*self.point(distance, target_x(distance))) if distance else target.moveTo(*self.point(0., 0.))
        self.lines.attachNewNode(target.create())
        for record, color in zip(self.records, (LAB_ACCENT_A, LAB_ACCENT_B)):
            path = LineSegs()
            path.setColor(*color)
            path.setThickness(2.)
            path.moveTo(*self.point(0., record.snapshots[0].player.position[0]))
            for row in record.rows:
                path.drawTo(*self.point(row["position"], row["x"]))
            self.lines.attachNewNode(path.create())

    def select_gate(self, index):
        self.slider["value"] = GATES[index][0]
        self.seek()

    def seek(self):
        distance = self.slider["value"]
        self.cursor.removeNode()
        self.cursor = self.root.attachNewNode("review-position")
        mark = LineSegs()
        mark.setColor(*LAB_TEXT)
        mark.moveTo(*self.point(distance, -6.))
        mark.drawTo(*self.point(distance, 6.))
        self.cursor.attachNewNode(mark.create())
        gate_index = next((i for i, (position, _) in enumerate(GATES) if abs(position-distance) < .001), None)
        self.readout.setText(f"道路位置 {distance:.1f} m"+(f" · 第{gate_index+1}门" if gate_index is not None else " · 拖动或选门查看"))
        for index, detail in enumerate(self.details):
            if index >= len(self.records):
                detail.setText("B · 尚无记录")
                continue
            sample = sample_at(self.records[index], distance)
            if sample is None:
                detail.setText(f"{'AB'[index]} · 未到达此处；终点之后不补数据")
                continue
            dot = LineSegs()
            dot.setColor(*(LAB_ACCENT_A if index == 0 else LAB_ACCENT_B))
            dot.setThickness(3.)
            x, _, z = self.point(distance, sample["x"])
            dot.moveTo(x-.012, 0., z)
            dot.drawTo(x+.012, 0., z)
            dot.moveTo(x, 0., z-.012)
            dot.drawTo(x, 0., z+.012)
            self.cursor.attachNewNode(dot.create())
            gate = self.gates[index][gate_index] if gate_index is not None and gate_index < len(self.gates[index]) else None
            passage = (f"{'通过' if gate['passed'] else '漏门'} · 整车余量 {gate['clearance_m']:+.3f} m" if gate else "该位置无判门结果")
            control = sample["control"]
            request = f"请求 {control['steering']:+.3f} → 实际转角 {sample['steering_deg']:+.2f}°" if control else "尚无控制请求"
            detail.setText(f"{'AB'[index]} · {sample['speed_kph']:.2f} km/h · t={sample['time']:.3f}s\n"
                f"{passage}\n{request}\n侧偏 {sample['beta_deg']:+.3f}° · 朝向 {sample['heading_deg']:+.2f}°")

    def hide(self):
        self.root.hide()
