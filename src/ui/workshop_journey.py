"""初章三项固定内容的进度与继续入口；不持有物理状态。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode

from ui import theme


class WorkshopJourney:
    def __init__(self, parent, font, textures, action, driving_action=None):
        self.action = action
        self.driving_action = driving_action
        self.data = None
        self.selected = 0
        self.textures = textures
        self.root = DirectFrame(parent=parent, frameColor=theme.PAPER_LIGHT,
            frameSize=(-1.70, 1.70, -.86, .80), sortOrder=100, state=DGG.NORMAL)

        def text(value, x, z, scale=.040, color=theme.INK):
            return OnscreenText(parent=self.root, text=value, font=font, fg=color,
                align=TextNode.ALeft, pos=(x, z), scale=scale, mayChange=True)

        text("海岸工坊 · 初章", -1.52, .62, .080)
        text("设计它 → 验证它 → 驾驶它", -1.52, .49, .043, theme.SEA)
        self.progress = text("", .65, .62, .055, theme.SEA)
        if driving_action is not None:
            DirectButton(parent=self.root, text="驾驶进阶  Tab  ›", text_font=font, text_fg=theme.INK,
                text_scale=.035, text_pos=(0, -.012), frameSize=(-.50, .50, -.045, .045),
                frameTexture=textures, frameColor=(1, 1, 1, 1), pos=(1.03, 0, .47),
                command=driving_action, relief=DGG.FLAT, pressEffect=False)
        self.summary = text("", -1.52, .35, .038)
        self.summary.textNode.setWordwrap(80)
        self.frames, self.details, self.buttons = [], [], []
        for index, (title, description) in enumerate((("01 制动配方", "短一点，更稳一点。"),
                ("02 弯道循迹", "少向弯外推，也留意侧偏。"), ("03 定点刹停", "把工程车准确停在目标线。"))):
            left = -1.52+index*1.04
            frame = DirectFrame(parent=self.root, frameColor=theme.PAPER,
                frameSize=(left, left+.96, -.51, .23))
            self.frames.append(frame)
            text(title, left+.05, .12, .048)
            text(description, left+.05, .02, .031, theme.MUTED)
            detail = text("", left+.05, -.10, .035)
            detail.textNode.setWordwrap(25)
            self.details.append(detail)
            button = DirectButton(parent=self.root, text="开始项目", text_font=font, text_fg=theme.INK,
                text_scale=.039, text_pos=(0, -.013), frameSize=(-.41, .41, -.06, .06),
                frameTexture=textures, frameColor=(1, 1, 1, 1), pos=(left+.48, 0, -.42),
                command=lambda i=index: self.activate(i), relief=DGG.FLAT, pressEffect=False)
            button.bind(DGG.ENTER, lambda event, i=index: self.select(i))
            self.buttons.append(button)
        self.notice = text("", -1.52, -.62, .030, theme.FAILURE)
        self.notice.textNode.setWordwrap(91)
        close = DirectButton(parent=self.root, text="返回主菜单  Esc", text_font=font, text_fg=theme.INK,
            text_scale=.039, text_pos=(0, -.013), frameSize=(-.51, .51, -.06, .06),
            frameTexture=textures, frameColor=(1, 1, 1, 1), pos=(1.02, 0, -.73),
            command=self.hide, relief=DGG.FLAT, pressEffect=False)
        close.bind(DGG.ENTER, lambda event: self.select(3))
        self.buttons.append(close)
        text("↑ ↓ 或 ← → 选择 · Enter 继续 · 自由驾驶/专家实验随时可用", -1.52, -.77, .029, theme.MUTED)
        self.root.hide()

    def show(self, data):
        self.data = data
        completed = data["steps"]
        self.progress.setText(f"初章进度 {completed} / 5")
        if data["next_index"] is None:
            summary = "初章完成 · 你已把两套工程方案带上公路，也完成了当前车的刹停。继续争取金牌或比较新方案。"
        else:
            next_project = data["projects"][data["next_index"]]
            summary = "建议下一步："+next_project["title"]+" · "+next_project["next"]
        self.summary.setText(summary)
        for index, item in enumerate(data["projects"]):
            if index < 2:
                detail = ("试验待完成\n道路待验证" if item["steps"] == 0 else
                          f"工程{item['medal']}牌\n道路"+("已完成" if item["steps"] == 2 else "待验证")+
                          f"\n方案：{item['name'][:18]}")
                label = "开始工坊" if item["steps"] == 0 else "继续道路验证" if item["steps"] == 1 else "查看完成方案"
            else:
                detail = ("当前车辆尚无成功成绩\n先把误差控制在10m内" if item["steps"] == 0 else
                          f"当前车辆{item['medal']}牌\n最佳绝对误差 {item['best_error']:.2f}m")
                label = "开始刹停课题" if item["steps"] == 0 else "挑战更准停车"
            self.details[index].setText(detail)
            self.buttons[index]["text"] = label
            self.frames[index]["frameColor"] = theme.PAPER if item["steps"] < (2 if index < 2 else 1) else (.87, .93, .87, 1)
        self.notice.setText(f"{len(data['errors'])} 项记录未计入：{data['errors'][0][:65]}" if data["errors"] else "")
        self.select(data["next_index"] if data["next_index"] is not None else 0)
        self.root.show()

    def select(self, index):
        self.selected = index % 4
        for i, button in enumerate(self.buttons):
            button["frameTexture"] = ((self.textures[2], self.textures[1], self.textures[2], self.textures[3])
                                       if i == self.selected else self.textures)

    def activate(self, index):
        if index == 3:
            self.hide()
        else:
            self.action(self.data["projects"][index])

    def key(self, key):
        if key in ("arrow_up", "arrow_left", "w", "a"):
            self.select(self.selected-1)
        elif key in ("arrow_down", "arrow_right", "s", "d"):
            self.select(self.selected+1)
        elif key == "enter":
            self.activate(self.selected)
        elif key == "tab" and self.driving_action is not None:
            self.driving_action()
        elif key == "escape":
            self.hide()

    def hide(self):
        self.root.hide()
