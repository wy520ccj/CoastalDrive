"""海岸主菜单：素材、排版与选择状态；动作由应用传入。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TransparencyAttrib

from ui import theme


class MainMenu:
    def __init__(self, parent, loader, body_font, display_font, actions, *, driving_mode_action=None):
        self.root = parent.attachNewNode("main-menu")
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.background = DirectFrame(
            parent=self.root, frameColor=(1, 1, 1, 1),
            frameTexture=loader.loadTexture(theme.asset_filename("backgrounds/coastal-menu.png")),
            frameSize=(-16 / 9, 16 / 9, -1, 1), sortOrder=-10,
        )
        self.content = self.root.attachNewNode("menu-content")
        self.wordmark = DirectFrame(
            parent=self.content, frameColor=(1, 1, 1, 1),
            frameTexture=loader.loadTexture(theme.asset_filename("wordmark.png")),
            frameSize=(-1.66, -0.28, 0.48, 1.00),
        )
        OnscreenText(parent=self.content, text="\u6d77 \u5cb8 \u9a7e \u9a76", font=body_font,
                     fg=theme.INK, align=TextNode.ARight, pos=(-0.40, 0.59), scale=0.058)
        labels = ("计时挑战", "滨海自由驾驶", "无限高速", "车库", "声音设置", "退出")
        icons = ("stopwatch", "palm", "highway", "garage", "speaker", "exit")
        self.textures = tuple(loader.loadTexture(theme.asset_filename(f"components/button-{state}.png"))
                              for state in ("normal", "pressed", "hover", "disabled"))
        self.buttons = []
        self.actions = actions
        self.selected = 0
        for index, (label, icon, action) in enumerate(zip(labels, icons, actions)):
            primary = index < 3
            z = 0.405 - index * 0.26 if primary else -0.40 - (index - 3) * 0.16
            width, height = (1.04, 0.22) if primary else (0.66, 0.13)
            button = DirectButton(
                parent=self.content, text=label, text_font=body_font, text_fg=theme.INK,
                text_align=TextNode.ALeft, text_scale=0.063 if primary else 0.051,
                text_pos=(-0.205 if primary else -0.10, -0.020),
                frameSize=(-width / 2, width / 2, -height / 2, height / 2),
                frameTexture=self.textures, frameColor=(1, 1, 1, 1),
                pos=(-1.08, 0, z), relief=DGG.FLAT, command=action, pressEffect=False,
            )
            size = 0.067 if primary else 0.040
            DirectFrame(parent=button, frameColor=(1, 1, 1, 1),
                        frameTexture=loader.loadTexture(theme.asset_filename(f"components/icon-{icon}.png")),
                        frameSize=(-size, size, -size, size),
                        pos=(-0.36 if primary else -0.21, 0, 0))
            if primary:
                DirectFrame(parent=button, frameColor=theme.ORANGE,
                            frameSize=(-0.266, -0.261, -0.055, 0.055))
                OnscreenText(parent=button, text="›", font=body_font, fg=theme.INK,
                             pos=(0.433, -0.030), scale=0.085)
            button.bind(DGG.ENTER, lambda event, i=index: self.select(i))
            self.buttons.append(button)
        DirectFrame(parent=self.content, frameColor=(0.4, 0.46, 0.48, 0.35),
                    frameSize=(-1.58, -0.58, -0.292, -0.289))
        DirectFrame(parent=self.content, frameColor=(*theme.PAPER[:3], 0.9),
                    frameSize=(-1.47, -0.69, -0.909, -0.851))
        self.hint = OnscreenText(parent=self.content, text="↑ ↓ 选择    Enter 确认", font=body_font,
                                fg=theme.INK, pos=(-1.08, -0.89), scale=0.032)
        self.notice = OnscreenText(parent=self.content, text="", font=body_font, fg=theme.FAILURE,
                                  pos=(-1.08, -0.95), scale=0.028, mayChange=True)
        self.driving_mode_button = DirectButton(
            parent=self.content, text="驾驶模式：正常游戏  F2", text_font=body_font,
            text_fg=theme.INK, text_scale=0.040, text_pos=(0, -0.013),
            frameSize=(-.38, .38, -.045, .045), frameTexture=self.textures,
            frameColor=(1, 1, 1, 1), pos=(1.25, 0, -.88), relief=DGG.FLAT,
            command=driving_mode_action, pressEffect=False,
        )
        self.select(0)
        self.root.hide()

    def set_driving_mode(self, mode):
        self.driving_mode_button["text"] = f"驾驶模式：{mode.label}  F2"

    def select(self, index):
        self.selected = index % len(self.buttons)
        for i, button in enumerate(self.buttons):
            button["frameTexture"] = (
                (self.textures[2], self.textures[1], self.textures[2], self.textures[3])
                if i == self.selected else self.textures
            )

    def move(self, direction):
        self.select(self.selected + direction)

    def activate(self):
        self.actions[self.selected]()

    def resize(self, aspect):
        self.content.setScale(min(1, aspect / (16 / 9)))
        self.background["frameSize"] = (-aspect, aspect, -1, 1)

    def destroy(self):
        for button in self.buttons:
            button.destroy()
        self.driving_mode_button.destroy()
        self.background.destroy()
        self.root.removeNode()
