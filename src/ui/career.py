"""生涯的赛事板、简报、车库与领奖画面；不复用工程报告页面。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TextureStage

from career import EVENTS, PARTS
from ui import theme
from ui.lab_widgets import rounded_panel

PAPER = (.96, .965, .95, 1)
WHITE = (1., 1., 1., 1)
INK = (.055, .13, .22, 1)
MUTED = (.32, .40, .47, 1)
BLUE = (.04, .35, .72, 1)
PALE = (.84, .92, .98, 1)
ORANGE = (.92, .25, .12, 1)
GOLD = (.78, .49, .05, 1)


class CareerPanel:
    def __init__(self, parent, font, vehicle_view, action, loader):
        self.font, self.vehicle_view, self.action = font, vehicle_view, action
        self.root = DirectFrame(parent=parent, frameSize=(-1.78, 1.78, -1.5, 1.5),
            frameColor=PAPER, sortOrder=300, state=DGG.NORMAL)
        self.content = self.root.attachNewNode('career-content')
        self.labels, self.buttons = [], []
        self.frames = []
        self.accents = set()
        self.photos = {event.id: loader.loadTexture(theme.asset_filename('career/'+event.id+'.png')) for event in EVENTS}
        self.page, self.selected, self.primary, self.back = '', 0, -1, 'board'
        self.root.hide()

    def clear(self, page, progress):
        self.vehicle_view.hide()
        for widget in (*self.labels, *self.buttons, *self.frames):
            widget.destroy()
        self.labels.clear()
        self.buttons.clear()
        self.frames.clear()
        self.accents.clear()
        self.content.removeNode()
        self.content = self.root.attachNewNode('career-content')
        self.page, self.primary = page, -1
        self.label('COASTAL / 生涯', -1.55, .84, .065)
        self.label('海岸杯车手' if progress.stars >= 9 else '俱乐部车手' if progress.stars >= 5 else
                   '新手车手', -.22, .85, .038, MUTED)
        self.label(f'{progress.stars} / 18 星', .66, .85, .045, BLUE)
        self.label(f'{progress.credits} 积分', 1.20, .85, .045)
        rounded_panel(self.content, 'header-line', (-1.58, 1.58, .75, .754), (.75, .80, .82, 1), 0.)
        self.root.show()

    def label(self, text, x, z, size=.04, color=INK, parent=None, wrap=None):
        item = OnscreenText(parent=self.content if parent is None else parent, text=text, font=self.font,
            fg=color, align=TextNode.ALeft, pos=(x, z), scale=size, mayChange=True)
        if wrap is not None:
            item.textNode.setWordwrap(wrap/size)
        self.labels.append(item)
        return item

    def button(self, text, x, z, width, height, command, value=None, *, primary=False, enabled=True, accent=False):
        node = rounded_panel(self.content, 'button-fill', (-width/2, width/2, -height/2, height/2), WHITE)
        node.detachNode()
        index = len(self.buttons)
        item = DirectButton(parent=self.content, text=text, text_font=self.font,
            text_scale=.044, text_fg=INK, text_pos=(0, -.016), frameColor=(0, 0, 0, 0),
            frameSize=(-width/2, width/2, -height/2, height/2), pos=(x, 0, z), geom=node,
            relief=DGG.FLAT, pressEffect=False, state=DGG.NORMAL if enabled else DGG.DISABLED,
            command=self.action, extraArgs=[command, value])
        item.bind(DGG.ENTER, lambda event, i=index: self.select(i))
        self.buttons.append(item)
        if primary:
            self.primary = index
        if accent:
            self.accents.add(index)
        return item

    def photo(self, event, parent, box, *, unlocked=True):
        texture = self.photos[event.id]
        frame = DirectFrame(parent=parent, frameSize=box, frameTexture=texture,
                            frameColor=WHITE if unlocked else (.60, .67, .73, 1), state=DGG.DISABLED)
        aspect = (box[1]-box[0])/(box[3]-box[2])
        scale_v = (texture.getXSize()/texture.getYSize())/aspect
        frame.setTexScale(TextureStage.getDefault(), 1., scale_v)
        frame.setTexOffset(TextureStage.getDefault(), 0., (1.-scale_v)*.5)
        self.frames.append(frame)

    def show_board(self, progress):
        self.clear('board', progress)
        self.back = 'exit'
        self.label('赛事', -1.55, .60, .052, BLUE)
        self.button('车库改装', -.82, .62, .60, .10, 'garage')
        self.button('主菜单', 1.27, .62, .60, .10, 'exit')
        self.label('01  初次上路', -1.55, .45, .040)
        self.label('02  俱乐部挑战 · 5星解锁', -1.55, -.13, .035)
        self.label('03  海岸杯 · 9星解锁', .61, -.13, .035)
        for index, event in enumerate(EVENTS):
            x, z = (-1.06, 0., 1.06)[index % 3], .16 if index < 3 else -.43
            unlocked = progress.available(event)
            card = self.button('', x, z, 1.0, .46, 'brief', event.id)
            self.label(event.name, -.42, .135, .052, INK if unlocked else MUTED, parent=card)
            self.photo(event, card, (-.46, .46, -.09, .075), unlocked=unlocked)
            stars = progress.records.get(event.id, {'stars': 0})['stars']
            self.label('★'*stars+'☆'*(3-stars) if unlocked else f'还需{event.unlock-progress.stars}星',
                       -.41, -.16, .038, GOLD if unlocked else MUTED, parent=card)
            self.label(f'{event.distance:g}米', .24, -.16, .031, MUTED, parent=card)
        next_event = progress.recommended()
        self.button('继续：'+next_event.name, .85, -.84, 1.35, .14, 'brief', next_event.id, primary=True)
        self.label(progress.notice or '提高星级可获得积分，解锁赛事和车库零件。', -1.55, -.82, .030, MUTED, wrap=1.55)
        self.select(self.primary)

    def show_brief(self, progress, event):
        self.clear('brief', progress)
        self.back = 'board'
        self.button('‹  赛事', -1.28, .62, .54, .10, 'board')
        self.label(event.name, -1.50, .36, .090)
        self.label(event.goal, -1.50, .19, .048, BLUE)
        self.photo(event, self.content, (-1.50, .20, -.39, .12))
        self.label(f'静止起步  /  {event.distance:g}米  /  时限{event.limit:g}秒', -1.50, -.49, .035, MUTED)
        self.label(event.tip, -1.50, -.61, .040, MUTED, wrap=1.65)
        for index, target in enumerate(event.targets):
            z = .32-index*.22
            self.label('★'*(index+1), .48, z, .052, GOLD)
            self.label(target, .48, z-.09, .042)
        self.label(f'每提高1星奖励 {event.reward} 积分', .48, -.43, .035, BLUE)
        self.label('碰撞、复位或驶离赛道\n会结束本场。', .48, -.58, .029, MUTED)
        self.button('车库', -.95, -.82, 1.1, .14, 'garage')
        available = progress.available(event)
        self.button('开始比赛' if available else f'需要{event.unlock}星', .91, -.82, 1.3, .14,
                    'start', event.id, primary=True, enabled=available)
        self.select(self.primary if available else 0)

    def show_garage(self, progress, vehicle, notice=''):
        from vehicle_designs import vehicle_design

        self.clear('garage', progress)
        self.back = 'board'
        self.button('‹  赛事', -1.28, .62, .54, .10, 'board')
        layer = self.content.attachNewNode('garage-vehicle')
        self.label('车库', -.56, .61, .05, BLUE)
        self.vehicle_view.show(layer, (-1.60, .30, -.36, .44), vehicle)
        self.vehicle_view.highlight(None)
        self.label(vehicle_design(vehicle.design_id).name, -1.55, .50, .045)
        self.label(f'前轮 {vehicle.config.lateral_stiffness/1000:g} kN/rad  /  前轴制动 {vehicle.config.front_brake_share:.0%}',
                   -1.55, -.46, .035, MUTED)
        for index, part in enumerate(PARTS):
            z = .20-index*.51
            rounded_panel(self.content, 'part-card', (.43, 1.61, z-.23, z+.23), WHITE)
            self.label(part.name, .50, z+.15, .049)
            self.label(part.description, .50, z+.055, .030, MUTED, wrap=1.04)
            self.label(part.hardware, .50, z-.02, .026, MUTED)
            installed = (vehicle.config.lateral_stiffness == 70000. if part.topic == 'tires' else
                         vehicle.config.front_brake_share == .7)
            owned, unlocked = part.id in progress.owned, progress.stars >= part.unlock
            affordable = owned or progress.credits >= part.price
            text = ('已安装' if installed else '安装' if owned else f'{part.unlock}星解锁' if not unlocked else
                    f'购买并安装 · {part.price}' if affordable else f'还差{part.price-progress.credits}积分')
            self.button(text, 1.02, z-.15, 1.0, .11, 'part', part.id,
                        accent=True, enabled=not installed and unlocked and affordable)
        self.label(notice or progress.notice or '赢取赛事积分，购买零件；已拥有的零件可反复安装。',
                   -1.55, -.65, .033, MUTED, wrap=1.8)
        self.button('恢复改装前车辆', -.89, -.83, 1.3, .14, 'restore')
        self.button('返回赛事', 1.02, -.83, 1.15, .14, 'board', primary=True)
        self.select(len(self.buttons)-1)

    def show_result(self, progress, result, award):
        self.clear('result', progress)
        self.back = 'board'
        event = next(event for event in EVENTS if event.id == result.event_id)
        self.label(event.name, -1.48, .61, .048, MUTED)
        self.label('赛事完成' if result.succeeded else '再试一次', -1.48, .35, .105)
        self.label('★'*result.stars+'☆'*(3-result.stars), -1.48, .08, .15, GOLD)
        detail = f'用时 {result.elapsed:.2f} 秒'
        if event.kind == 'parking' and result.parking_error is not None:
            detail += f'  /  距中心 {result.parking_error:.1f} 米'
        if event.kind == 'slalom':
            detail += f'  /  通过 {sum(result.passed)} / 5 门'
        self.label(detail, -1.48, -.12, .044)
        self.label(result.reason, -1.48, -.29, .040, MUTED, wrap=1.65)
        rounded_panel(self.content, 'reward-card', (.48, 1.57, -.43, .46), WHITE)
        self.label('本场奖励', .59, .31, .042, MUTED)
        self.label(f'+{award["credits"]}', .59, .08, .12, BLUE)
        self.label('积分', 1.22, .09, .04, MUTED)
        self.label('解锁：'+ '、'.join(award['unlocked']) if award['unlocked'] else
                   '提高个人星级后领取差额奖励。', .59, -.13, .034, MUTED, wrap=.85)
        if not award['saved']:
            self.label(progress.notice, -1.48, -.52, .033, ORANGE, wrap=2.9)
            self.button('重试保存奖励', 1.03, -.35, .9, .10, 'save')
        self.button('重试本场', -1.01, -.81, 1.0, .15, 'start', event.id)
        self.button('车库', .06, -.81, .85, .15, 'garage')
        self.button('继续赛事', 1.09, -.81, 1.0, .15, 'board', primary=True)
        self.select(self.primary)

    def show_pause(self, progress):
        self.clear('pause', progress)
        self.back = 'resume'
        self.label('比赛已暂停', -1.15, .30, .10)
        self.button('继续驾驶', 0, -.02, 1.5, .18, 'resume', primary=True)
        self.button('重新开始', 0, -.30, 1.5, .15, 'retry')
        self.button('退出本场', 0, -.56, 1.5, .15, 'board')
        self.select(self.primary)

    def select(self, index):
        self.selected = index % len(self.buttons)
        for i, button in enumerate(self.buttons):
            disabled = button['state'] == DGG.DISABLED
            button['geom_color'] = (WHITE if disabled else ORANGE if i == self.primary else
                                   PALE if i == self.selected or i in self.accents else WHITE)
            button['text_fg'] = MUTED if disabled else WHITE if i == self.primary else BLUE if i in self.accents else INK

    def key(self, key):
        if key in ('arrow_left', 'arrow_up', 'a', 'w'):
            self.select(self.selected-1)
        elif key in ('arrow_right', 'arrow_down', 'd', 's'):
            self.select(self.selected+1)
        elif key == 'enter' and self.buttons[self.selected]['state'] != DGG.DISABLED:
            self.buttons[self.selected]['command'](*self.buttons[self.selected]['extraArgs'])
        elif key == 'escape':
            self.action(self.back, None)

    def hide(self):
        self.root.hide()
        self.vehicle_view.hide()

    def destroy(self):
        for widget in (*self.labels, *self.buttons, *self.frames):
            widget.destroy()
        self.root.destroy()
