"""当前车两项短课题的固定进阶面板；只消费已保存成绩。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode

from driving_journey import MEDALS
from ui import theme


class DrivingJourney:
    def __init__(self, parent, font, textures, action, workshop_action):
        self.action, self.workshop_action = action, workshop_action
        self.textures, self.selected, self.data = textures, 0, None
        self.root = DirectFrame(parent=parent, frameColor=theme.PAPER_LIGHT,
            frameSize=(-1.70, 1.70, -.86, .80), sortOrder=100, state=DGG.NORMAL)

        def text(value, x, z, scale=.039, color=theme.INK):
            return OnscreenText(parent=self.root, text=value, font=font, fg=color,
                align=TextNode.ALeft, pos=(x, z), scale=scale, mayChange=True)

        text("驾驶进阶", -1.52, .62, .080)
        self.progress = text("", .62, .62, .052, theme.SEA)
        self.vehicle = text("", -1.52, .48, .031, theme.MUTED)
        self.vehicle.textNode.setWordwrap(96)
        self.summary = text("", -1.52, .30, .039, theme.SEA)
        self.summary.textNode.setWordwrap(78)
        self.frames, self.details, self.buttons = [], [], []
        for index, (title, subtitle) in enumerate((("01 定点刹停", "入门≥80km/h，控制停车误差"),
                                                ("02 连续过门", "入门≥40km/h，整车通过六道门"))):
            left = -1.52+index*1.60
            self.frames.append(DirectFrame(parent=self.root, frameColor=theme.PAPER,
                frameSize=(left, left+1.48, -.49, .19)))
            text(title, left+.07, .08, .052)
            text(subtitle, left+.07, -.02, .031, theme.MUTED)
            detail = text("", left+.07, -.13, .037)
            detail.textNode.setWordwrap(35)
            self.details.append(detail)
            button = DirectButton(parent=self.root, text="", text_font=font, text_fg=theme.INK,
                text_scale=.040, text_pos=(0, -.013), frameSize=(-.63, .63, -.06, .06),
                frameTexture=textures, frameColor=(1, 1, 1, 1), pos=(left+.74, 0, -.40),
                command=lambda i=index: self.activate(i), relief=DGG.FLAT, pressEffect=False)
            button.bind(DGG.ENTER, lambda event, i=index: self.select(i))
            self.buttons.append(button)
        self.notice = text("", -1.52, -.58, .029, theme.FAILURE)
        self.notice.textNode.setWordwrap(97)
        for index, (label, x) in enumerate((("返回工坊初章  Tab", -.75), ("返回主菜单  Esc", .85)), start=2):
            button = DirectButton(parent=self.root, text=label, text_font=font, text_fg=theme.INK,
                text_scale=.038, text_pos=(0, -.013), frameSize=(-.63, .63, -.06, .06),
                frameTexture=textures, frameColor=(1, 1, 1, 1), pos=(x, 0, -.70),
                command=lambda i=index: self.activate(i), relief=DGG.FLAT, pressEffect=False)
            button.bind(DGG.ENTER, lambda event, i=index: self.select(i))
            self.buttons.append(button)
        text("↑ ↓ 或 ← → 选择 · Enter 继续 · 两项铜 → 两项银 → 双项金", -1.52, -.80, .029, theme.MUTED)
        self.root.hide()

    def show(self, data, vehicle):
        self.data = data
        self.vehicle.setText(vehicle+"\n成绩按当前完整硬件与驾驶输入分组；换车可另开进阶")
        self.progress.setText(f"目标 {data['steps']} / 6 · {data['stage']}")
        if data["next_index"] is None:
            self.summary.setText("双项金牌达成 · 制动准确、转向连贯。可继续刷新最佳，或回工坊比较新方案。")
        else:
            item = data["projects"][data["next_index"]]
            self.summary.setText(f"建议下一步：{item['title']} · {MEDALS[item['level']+1]}牌 ≤{item['target']:g}{item['unit']}")
        for index, item in enumerate(data["projects"]):
            best = "暂无成功成绩" if item["best"] is None else f"最佳{item['best']:.3f}{item['unit']} · {item['medal']}牌"
            tiers = "  ".join(f"{MEDALS[i+1]}≤{target:g}{item['unit']}{' 已达' if i < item['level'] else ''}"
                              for i, target in enumerate(item["targets"]))
            next_goal = ("双项都达这一档，再挑战下一档" if item["gap"] is None else
                         f"距下一档还需改善 {item['gap']:.3f}{item['unit']}") if item["target"] is not None else "本项金牌已达成，可继续刷新最佳"
            self.details[index].setText(best+"\n"+tiers+"\n"+next_goal)
            self.buttons[index]["text"] = (f"挑战{MEDALS[item['level']+1]}牌 · {item['title']}" if item["level"] < 3
                                            else "刷新最佳 · "+item["title"])
            self.frames[index]["frameColor"] = (.87, .93, .87, 1) if item["level"] == 3 else theme.PAPER
        self.notice.setText(data["errors"][0][:96] if data["errors"] else "")
        self.select(data["next_index"] if data["next_index"] is not None else 0)
        self.root.show()

    def select(self, index):
        self.selected = index % len(self.buttons)
        for i, button in enumerate(self.buttons):
            button["frameTexture"] = ((self.textures[2], self.textures[1], self.textures[2], self.textures[3])
                                       if i == self.selected else self.textures)

    def activate(self, index):
        if index == 2:
            self.workshop_action()
        elif index == 3:
            self.hide()
        else:
            self.hide()
            self.action(self.data["projects"][index]["topic"])

    def key(self, key):
        if key in ("arrow_up", "arrow_left", "w", "a"):
            self.select(self.selected-1)
        elif key in ("arrow_down", "arrow_right", "s", "d"):
            self.select(self.selected+1)
        elif key == "enter":
            self.activate(self.selected)
        elif key == "tab":
            self.workshop_action()
        elif key == "escape":
            self.hide()

    def hide(self):
        self.root.hide()
