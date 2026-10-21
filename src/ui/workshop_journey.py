"""初章三项固定内容的进度与继续入口；不持有物理状态。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode

from ui import theme
from ui.lab_diagrams import course


class WorkshopJourney:
    def __init__(self, parent, font, textures, action, driving_action=None, on_back=None):
        self.action = action
        self.on_back = on_back
        self.driving_action = driving_action
        self.data = None
        self.selected = 0
        self.textures = textures
        self.root = DirectFrame(parent=parent, frameColor=theme.PAPER_LIGHT,
            frameSize=(-1.78, 1.78, -1.5, 1.5), sortOrder=100, state=DGG.NORMAL)

        def text(value, x, z, scale=.040, color=theme.INK):
            return OnscreenText(parent=self.root, text=value, font=font, fg=color,
                align=TextNode.ALeft, pos=(x, z), scale=scale, mayChange=True)

        text("海岸工坊", -1.52, .62, .080)
        text("改装车辆，完成试验后上路验证。", -1.52, .49, .043, theme.SEA)
        self.progress = text("", .65, .62, .055, theme.SEA)
        if driving_action is not None:
            DirectButton(parent=self.root, text="驾驶进阶  Tab  ›", text_font=font, text_fg=theme.INK,
                text_scale=.035, text_pos=(0, -.012), frameSize=(-.50, .50, -.045, .045),
                frameTexture=textures, frameColor=(1, 1, 1, 1), pos=(1.03, 0, .47),
                command=driving_action, relief=DGG.FLAT, pressEffect=False)
        self.summary = text("", -1.52, .35, .038)
        self.summary.textNode.setWordwrap(80)
        self.frames, self.details, self.buttons = [], [], []
        for index, (title, description) in enumerate((("制动改装", "调整刹车，缩短停车距离"),
                ("弯道改装", "调整底盘，减少路线偏差"), ("停车练习", "上路练习，停进目标区域"))):
            left = -1.52+index*1.04
            frame = DirectFrame(parent=self.root, frameColor=theme.PAPER,
                frameSize=(left, left+.96, -.51, .27))
            self.frames.append(frame)
            text(title, left+.05, .16, .054)
            text(description, left+.05, .075, .031, theme.MUTED)
            course(self.root, (left+.10, left+.85, -.19, .015), ("brake", "corner", "stop")[index])
            detail = text("", left+.05, -.28, .032)
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
            command=lambda: self.activate(3), relief=DGG.FLAT, pressEffect=False)
        close.bind(DGG.ENTER, lambda event: self.select(3))
        self.buttons.append(close)
        text("方向键选择 · Enter 进入 · Esc 返回", -1.52, -.77, .029, theme.MUTED)
        self.root.hide()

    def show(self, data):
        self.data = data
        completed = sum(item['steps'] >= (2 if index < 2 else 1)
                        for index, item in enumerate(data['projects']))
        self.progress.setText(f"已完成 {completed} / 3 个项目")
        if data['next_index'] is None:
            summary = '所有项目已完成。'
        else:
            index = data['next_index']
            item = data['projects'][index]
            summary = ('使用当前车辆进行停车练习。' if index == 2 else
                       '试验已通过，尚未完成道路验证。' if item['steps'] else
                       '选择项目开始。已有方案可继续试验或试驾。')
        self.summary.setText(summary)
        for index, item in enumerate(data["projects"]):
            if index < 2:
                detail = ("尚未完成试验" if item["steps"] == 0 else
                          f"试验{item['medal']}牌 · 道路"+("已完成" if item["steps"] == 2 else "待验证")+
                          "")
                label = "开始改装" if item["steps"] == 0 else "继续试驾" if item["steps"] == 1 else "查看方案"
            else:
                detail = ("尚无停车成绩" if item["steps"] == 0 else
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
            self.hide() if self.on_back is None else self.on_back()
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
            self.hide() if self.on_back is None else self.on_back()

    def hide(self):
        self.root.hide()
