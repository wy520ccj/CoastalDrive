"""起步大数字：一次短回弹、稳定停留、快速退场；不维护车辆或比赛状态。"""

from direct.gui.DirectGui import OnscreenText
from panda3d.core import TransparencyAttrib

from ui import theme


class Countdown:
    def __init__(self, parent):
        self.root = parent.attachNewNode('start-countdown')
        self.root.setBin('fixed',40)
        self.root.setDepthTest(False)
        self.root.setDepthWrite(False)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.punch = self.root.attachNewNode('countdown-punch')
        self.punch.setZ(.22)
        # 大数字单独生成高分辨率字形，四个提示在加载阶段排版完成。
        self.font = theme.load_font(theme.DISPLAY_FONT_FILE)
        self.font.setPixelsPerUnit(640)
        self.font.setPageSize(1024,1024)
        self.labels = ('3','2','1','GO!')
        self.digits = tuple(OnscreenText(
            parent=self.punch,text=text,font=self.font,
            fg=theme.ORANGE if text=='GO!' else theme.PAPER_LIGHT,
            shadow=theme.INK,shadowOffset=(.012,-.012),
            pos=(0,-.17),scale=.48 if text!='GO!' else .36,mayChange=False,
        ) for text in self.labels)
        for digit in self.digits:
            digit.hide()
        self.waiting = OnscreenText(parent=self.root,text='准备中…',font=theme.load_font(),
                                   fg=theme.PAPER_LIGHT,shadow=theme.INK,pos=(0,.14),scale=.054)
        self.waiting.hide()
        self.was_countdown = False
        self.go_elapsed = None
        self.active = None
        self.root.hide()

    def update(self, phase, ticks, dt):
        if phase == 'countdown':
            self.was_countdown = True
            self.go_elapsed = None
            if ticks>0:
                number = min(3,(ticks+119)//120)
                progress = 1-(ticks-(number-1)*120)/120
                self.waiting.hide()
                self.show(3-number,progress)
            else:
                for digit in self.digits:
                    digit.hide()
                self.active = None
                self.root.show()
                self.waiting.show()
        elif phase == 'driving':
            if self.was_countdown:
                self.go_elapsed = 0.
                self.was_countdown = False
            if self.go_elapsed is None:
                self.root.hide()
                return
            self.go_elapsed += max(0.,dt)
            if self.go_elapsed>.55:
                self.root.hide()
                return
            self.waiting.hide()
            self.show(3,self.go_elapsed)
        else:
            self.root.hide()
            if phase != 'paused':
                self.was_countdown = False
                self.go_elapsed = None

    def show(self, index, progress):
        if index != self.active:
            for number,digit in enumerate(self.digits):
                digit.show() if number==index else digit.hide()
            self.active = index
        self.root.show()
        # 180ms落点只回弹一次，随后稳定；最后120ms退场让下一拍更干净。
        t = min(1.,max(0.,progress/.18))
        u = 1-t
        scale = 1+.23*u*u*u-.065*4*t*(1-t)
        self.punch.setScale(scale)
        self.punch.setZ(.22+.035*u*u)
        end,fade = (.55,.13) if index==3 else (1.,.12)
        self.root.setColorScale(1,1,1,min(1.,max(0.,(end-progress)/fade)))

    def destroy(self):
        for widget in (*self.digits,self.waiting):
            widget.destroy()
        self.root.removeNode()
