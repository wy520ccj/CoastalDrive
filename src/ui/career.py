"""生涯的赛事板、简报、车库与领奖画面；不复用工程报告页面。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TextureStage

from career import EVENTS, PARTS
from career_garage import garage_cars
from skins import SKINS
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
        self.flat = set()
        self.photos = {event.id: loader.loadTexture(theme.asset_filename('career/'+event.id+'.png')) for event in EVENTS}
        self.page, self.selected, self.primary, self.back = '', 0, -1, 'board'
        self.event_id = None
        self.root.hide()

    def clear(self, page, progress):
        self.vehicle_view.hide()
        for widget in (*self.labels, *self.buttons, *self.frames):
            widget.destroy()
        self.labels.clear()
        self.buttons.clear()
        self.frames.clear()
        self.accents.clear()
        self.flat.clear()
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

    def button(self, text, x, z, width, height, command, value=None, *, primary=False, enabled=True, accent=False, flat=False):
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
        if flat:
            self.flat.add(index)
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
        self.event_id = event.id
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

    def show_garage(self, progress, vehicle, notice='', *, tab='cars', preview=None, skin_index=None, cars=None):
        self.clear('garage', progress)
        self.back = 'garage-back'
        preview = vehicle if preview is None or tab != 'cars' else preview
        self.button('‹  赛事', -1.28, .62, .54, .10, 'board', flat=True)
        for index, (key, title) in enumerate((('cars', '我的车辆'), ('upgrade', '升级改装'), ('paint', '车身颜色'))):
            x = -.48+index*.72
            self.button(title, x, .62, .64, .10, 'garage-tab', key, accent=key == tab, flat=True)
            if key == tab:
                rounded_panel(self.content, 'active-tab', (x-.24, x+.24, .548, .557), BLUE, .004)
        layer = self.content.attachNewNode('garage-vehicle')
        self.vehicle_view.show(layer, (-1.56, .42, -.30, .47), preview, studio=True, skin_index=skin_index)
        self.vehicle_view.highlight(None)
        self.label('查看车身', -1.55, -.40, .032, MUTED)
        self.button('‹', .02, -.39, .15, .09, 'garage-orbit', -25, flat=True)
        self.button('›', .29, -.39, .15, .09, 'garage-orbit', 25, flat=True)
        cars = garage_cars(vehicle) if cars is None else cars
        car = next(item for item in cars if item.design_id == preview.design_id)
        config = preview.config
        self.label(car.name, .62, .37, .075)
        self.label(car.category, .62, .25, .034, MUTED)
        if tab == 'cars':
            self.label(car.description, .62, .08, .038, MUTED, wrap=.88)
            power = max(rpm*torque/9549.3 for rpm, torque in config.torque_curve)
            self.label(f'{power:.0f}', .62, -.16, .070)
            self.label('kW', .82, -.16, .033, MUTED)
            self.label(f'{config.mass:.0f}', 1.07, -.16, .070)
            self.label('kg', 1.39, -.16, .033, MUTED)
            current = preview.design_id == vehicle.design_id
            unlocked = current or progress.stars >= car.unlock
            self.button('当前驾驶' if current else '选择驾驶' if unlocked else f'获得{car.unlock}星解锁',
                1.10, -.36, .96, .14, 'garage-select', primary=unlocked and not current,
                enabled=unlocked and not current)
            count = sum(progress.stars >= item.unlock or item.design_id == vehicle.design_id for item in cars)
            self.label(f'我的车辆  /  已解锁 {count} / {len(cars)}', -1.55, -.54, .035, MUTED)
            width = 1.98/len(cars)
            for index, item in enumerate(cars):
                unlocked = progress.stars >= item.unlock or item.design_id == vehicle.design_id
                title = item.name+'\n'+('驾驶中' if item.design_id == vehicle.design_id else
                    '已解锁' if unlocked else f'{item.unlock}星解锁')
                button = self.button(title, -1.56+width*(index+.5), -.67, width-.025, .18,
                    'garage-car', item.design_id, accent=item.design_id == preview.design_id)
                button['text_scale'] = .030 if len(cars) > 5 else .033
                button['text_pos'] = (0, .008)
        elif tab == 'upgrade':
            for index, part in enumerate(PARTS):
                z = .10-index*.36
                self.label(part.name, .62, z, .045)
                self.label('转向响应更利落' if part.topic == 'tires' else '更多制动力分给前轮',
                           .62, z-.08, .032, MUTED)
                installed = (vehicle.config.lateral_stiffness == 70000. if part.topic == 'tires' else
                             vehicle.config.front_brake_share == .7)
                owned, unlocked = part.id in progress.owned, progress.stars >= part.unlock
                affordable = owned or progress.credits >= part.price
                text = ('已安装' if installed else '安装已购零件' if owned else f'{part.unlock}星解锁' if not unlocked else
                        f'购买并安装  {part.price}' if affordable else f'还差{part.price-progress.credits}积分')
                button = self.button(text, 1.10, z-.18, .96, .10, 'part', part.id,
                    accent=True, enabled=not installed and unlocked and affordable)
                button_index = len(self.buttons)-1
                button.bind(DGG.ENTER, lambda event, i=button_index, topic=part.topic: self.part_focus(i, topic))
                button.bind(DGG.EXIT, lambda event: self.vehicle_view.highlight(None))
            self.label('当前车辆配置', -1.55, -.54, .035, MUTED)
            self.label(f'前轮 {config.lateral_stiffness/1000:g} kN/rad   /   前轴制动 {config.front_brake_share:.0%}',
                       -1.55, -.65, .036)
            self.button('恢复改装前车辆', -.88, -.75, 1.34, .09, 'restore', flat=True)
        else:
            self.label('车身颜色', .62, .10, .045)
            for index, skin in enumerate(SKINS):
                z = -.015-index*.105
                self.button(skin.name, 1.10, z, .96, .085, 'garage-paint', index, accent=index == skin_index)
                rounded_panel(self.content, 'paint-chip', (.67, .75, z-.022, z+.022), (*skin.color, 1), .012)
            self.button('应用颜色', 1.10, -.65, .96, .13, 'garage-paint-save', primary=True)
            self.label('预览颜色', -1.55, -.54, .035, MUTED)
            self.label('点击“应用颜色”后为这辆车保存。', -1.55, -.65, .036)
        rounded_panel(self.content, 'footer-line', (-1.56, 1.58, -.81, -.808), (.80, .84, .84, 1), 0.)
        self.label(notice or progress.notice or '换车保留各自改装；Esc 返回赛事。',
                   -1.55, -.90, .030, MUTED, wrap=2.10)
        self.button('返回赛事', 1.10, -.89, .96, .12, 'garage-back', primary=self.primary < 0)
        self.select(self.primary)

    def part_focus(self, index, topic):
        self.select(index)
        self.vehicle_view.highlight(topic)


    def show_result(self, progress, result, award):
        self.event_id = result.event_id
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
            if i in self.flat:
                button['geom_color'] = (0, 0, 0, 0)
            button['text_fg'] = (MUTED if disabled else WHITE if i == self.primary else
                                 BLUE if i in self.accents or i == self.selected and i in self.flat else INK)

    def key(self, key):
        directions = {'arrow_left': (-1, 0), 'a': (-1, 0), 'arrow_right': (1, 0), 'd': (1, 0),
                      'arrow_up': (0, 1), 'w': (0, 1), 'arrow_down': (0, -1), 's': (0, -1)}
        if self.page == 'garage' and key in directions:
            vx, vz = directions[key]
            current, candidates = self.buttons[self.selected], []
            for index, button in enumerate(self.buttons):
                dx, dz = button.getX()-current.getX(), button.getZ()-current.getZ()
                ahead, across = dx*vx+dz*vz, abs(dx*vz-dz*vx)
                if button['state'] != DGG.DISABLED and ahead > .025:
                    candidates.append((ahead+across*3., index))
            if candidates:
                self.select(min(candidates)[1])
            return
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
