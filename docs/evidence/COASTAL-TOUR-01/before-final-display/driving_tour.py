"""固定三站巡回总览；只显示规则与已保存的完整轮次。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode

from driving_tour import TITLES, overall_medal, points
from ui import theme


class DrivingTourPanel:
    def __init__(self, parent, font, textures, start, back):
        self.start, self.back = start, back
        self.selected = 0
        self.textures = textures
        self.root = DirectFrame(parent=parent, frameColor=theme.PAPER_LIGHT,
            frameSize=(-1.70, 1.70, -.86, .80), sortOrder=110, state=DGG.NORMAL)

        def text(value, x, z, scale=.038, color=theme.INK):
            return OnscreenText(parent=self.root, text=value, font=font, fg=color,
                align=TextNode.ALeft, pos=(x, z), scale=scale, mayChange=True)

        text('海岸巡回', -1.52, .62, .078)
        self.progress = text('', .62, .62, .048, theme.SEA)
        self.vehicle = text('', -1.52, .49, .031, theme.MUTED)
        self.vehicle.textNode.setWordwrap(96)
        text('同一配方跨三站 · 每站至少铜牌 · 铜1 / 银2 / 金3分', -1.52, .31, .039, theme.SEA)
        text('全程3分铜 / 6分银 / 8分金；同分比较有效三站合计，综合最佳保留完整一轮。', -1.52, .23, .031)
        self.details, self.frames = [], []
        for index, subtitle in enumerate(('下谷控速，再加速出谷', '提前松油，连贯通过四门', '安全超3辆并跑完2.4公里')):
            left = -1.52+index*1.05
            self.frames.append(DirectFrame(parent=self.root, frameColor=theme.PAPER,
                frameSize=(left, left+.97, -.35, .13)))
            text(f'{index+1:02d} '+TITLES[index], left+.05, .03, .044)
            text(subtitle, left+.05, -.05, .026, theme.MUTED)
            self.details.append(text('', left+.05, -.16, .034))
        self.best = text('', -1.52, -.45, .034, theme.SEA)
        self.notice = text('', -1.52, -.55, .026, theme.MUTED)
        self.notice.textNode.setWordwrap(115)
        self.buttons = []
        for index, (label, x) in enumerate((('继续巡回', -1.05), ('重开三站', 0.), ('返回短途赛事', 1.05))):
            self.buttons.append(DirectButton(parent=self.root, text=label, text_font=font, text_scale=.042,
                frameTexture=textures, frameSize=(-.47, .47, -.055, .055), pos=(x, 0, -.73),
                command=self.activate, extraArgs=[index]))
        text('失败只重试当前站；暂离后从本页继续。同配方/输入共享进度，换配方另开一组。', -1.52, -.83, .025, theme.MUTED)
        self.root.hide()

    def show(self, store, vehicle):
        self.vehicle.setText(vehicle)
        self.progress.setText(f'已过 {len(store.current)}/3站 · {points(store.current)}/9分')
        for index, detail in enumerate(self.details):
            if index < len(store.current):
                entry = store.current[index]
                detail.setText(f'{entry.medal}牌 · {entry.seconds:.3f}s\n已通过')
                self.frames[index]['frameColor'] = (.87, .93, .87, 1)
            else:
                detail.setText('当前站 · 至少铜牌' if index == len(store.current) else '通过上一站后继续')
                self.frames[index]['frameColor'] = theme.PAPER
        self.best.setText(f'综合最佳 · {overall_medal(store.best)}牌 / {points(store.best)}分 / 有效合计{sum(row.seconds for row in store.best):.3f}s'
                          if store.best else '综合最佳 · 完成同一轮三站后建立')
        self.notice.setText(store.notice)
        self.buttons[0]['text'] = ('三站已完成' if len(store.current) == 3 else
                                  f'继续第{len(store.current)+1}站' if store.current else '从第一站开始')
        self.buttons[0]['state'] = DGG.DISABLED if len(store.current) == 3 else DGG.NORMAL
        self.buttons[1]['text'] = '再跑一轮' if len(store.current) == 3 else '重开三站'
        self.buttons[1]['state'] = DGG.NORMAL if store.current else DGG.DISABLED
        self.select(1 if len(store.current) == 3 else 0)
        self.root.show()

    def select(self, index):
        self.selected = index % 3
        for i, button in enumerate(self.buttons):
            button['frameTexture'] = ((self.textures[2], self.textures[1], self.textures[2], self.textures[3])
                                      if i == self.selected else self.textures)

    def activate(self, index):
        if self.buttons[index]['state'] == DGG.DISABLED:
            return
        self.hide()
        self.back() if index == 2 else self.start(index == 1)

    def key(self, key):
        if key in ('arrow_up', 'arrow_left', 'w', 'a'):
            self.select(self.selected-1)
        elif key in ('arrow_down', 'arrow_right', 's', 'd'):
            self.select(self.selected+1)
        elif key == 'enter':
            self.activate(self.selected)
        elif key == 'escape':
            self.hide()
            self.back()

    def hide(self):
        self.root.hide()
