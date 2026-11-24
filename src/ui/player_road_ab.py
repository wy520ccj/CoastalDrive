"""完整亲驾A/B并排，失败无有效总时间，条件变化不生成差值。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from player_road_ab import mismatches
from ui import atelier, theme
from ui.garage_layout import GRAY, INK, ORANGE, WHITE
from ui.lab_widgets import gradient_panel, rounded_panel
from ui.player_road_diagram import RoadDiagram


class PlayerRoadPanel:
    def __init__(self, parent, font, textures, retest, *, on_back=None, vehicle_view):
        self.on_back, self.retest = on_back, retest
        self.font, self.textures, self.vehicle_view = font, textures, vehicle_view
        self.regular = theme.load_font('fonts/SourceHanSansSC-Regular.otf')
        self.base = vehicle_view.base
        self.root = DirectFrame(parent=parent, frameColor=(0, 0, 0, 0),
                                frameSize=(-2.5, 2.5, -1, 1), sortOrder=315, state=DGG.NORMAL)
        self.content, self.aspect, self.store = None, None, None
        self.widgets = []
        self.root.hide()

    def point(self, x, y):
        return (x-self.width/2)*2/941, 1-y*2/941

    def box(self, x, y, width, height):
        a, b = self.point(x, y+height), self.point(x+width, y)
        return a[0], b[0], a[1], b[1]

    def fill(self, x, y, width, height, color, *, parent=None, radius=4):
        node = rounded_panel(self.content if parent is None else parent, 'ab-surface',
                             self.box(x, y, width, height), color, radius*2/941)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def text(self, value, x, y, size=22, color=WHITE, *, parent=None, bold=False, wrap=None):
        item = OnscreenText(parent=self.content if parent is None else parent, text=value,
            font=self.font if bold else self.regular, fg=color, align=TextNode.ALeft,
            pos=self.point(x, y), scale=size*2/941, mayChange=True)
        if wrap:
            item.textNode.setWordwrap(wrap/size)
        if parent is None:
            self.widgets.append(item)
        return item

    def button(self, value, x, y, width, height, command, *, args=(), dark=False, primary=False):
        unit = 2/941
        px, pz = self.point(x+width/2, y+height/2)
        tex_name = 'atelier/btn-primary.png' if primary else 'atelier/btn-ghost.png'
        node = DirectButton(parent=self.content, text=value, text_font=self.font if primary else self.regular,
            text_fg=INK if primary else WHITE, text_scale=(22 if height > 50 else 19)*unit,
            text_pos=(0, -7*unit), frameTexture=atelier.tex(self.base.loader, tex_name),
            frameColor=(1, 1, 1, 1), relief=DGG.FLAT,
            frameSize=(-width*unit/2, width*unit/2, -height*unit/2, height*unit/2),
            pos=(px, 0, pz), pressEffect=False, command=command, extraArgs=list(args))
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.bind(DGG.ENTER, lambda event: node.setColorScale(1.06, 1.04, 1.0, 1))
        node.bind(DGG.EXIT, lambda event: node.clearColorScale())
        self.widgets.append(node)
        return node

    def layout(self):
        if self.content is not None:
            self.vehicle_view.hide()
            self.diagram.destroy()
            for widget in self.widgets:
                widget.destroy()
            self.widgets.clear()
            self.content.removeNode()
        self.content = self.root.attachNewNode('road-ab-content')
        self.aspect = self.base.getAspectRatio()
        self.width, self.left = 941*self.aspect, 941*self.aspect*.029
        self.wide = min(1326., self.width-2*self.left)
        texture = atelier.tex(self.base.loader, atelier.SUNSET_GARAGE_BG)
        background = DirectFrame(parent=self.content, frameSize=self.box(0, 0, self.width, 941),
                                 frameTexture=texture, frameColor=(0.28, 0.26, 0.30, 1))
        self.widgets.append(background)
        ratio = self.aspect/(texture.getXSize()/texture.getYSize())
        background.setTexScale(TextureStage.getDefault(), ratio, 1)
        background.setTexOffset(TextureStage.getDefault(), (1-ratio)/2, 0)
        gradient_panel(self.content, 'ab-scrim', self.box(0, 0, self.width, 941),
                       (0.045, 0.055, 0.078, 0.88), (0.045, 0.055, 0.078, 0.68))
        # 展示车只是车库布景；道路成绩与参数始终从两份冻结记录读取。
        if self.aspect > 1.5:
            self.widgets.append(atelier.picture(
                self.content, self.base.loader, 'atelier/floor-warm-bounce.png',
                self.box(self.width*.52, 495, self.width*.46, 220),
                color=(1, 0.90, 0.74, 0.72), sort_order=-2))
            self.vehicle_view.show(self.content, self.box(self.width*.53, 250, self.width*.44, 445),
                                   self.base.workspace_vehicle, studio=True)
            self.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        self.widgets.append(atelier.picture(self.content, self.base.loader, 'atelier/bar-top.png',
                                            self.box(0, 0, self.width, 110)))
        self.widgets.append(atelier.picture(self.content, self.base.loader, 'atelier/footer-surface.png',
                                            self.box(0, 846, self.width, 95)))
        self.fill(self.left, 26, 4.5, 56, theme.AMBER, radius=2)
        self.text('道路 A/B 对照', self.left+18, 58, 34, WHITE, bold=True)
        self.status = self.text('', self.left+18, 94, 18, GRAY, wrap=self.width*.60)
        self.text('整次记录 · 不参与授奖', self.width-280, 82, 18, GRAY)
        self.widgets.append(atelier.picture(self.content, self.base.loader, 'atelier/panel-obsidian.png',
                                            self.box(self.left-12, 116, self.wide+24, 716)))
        x, span = self.left+36, self.wide-72
        self.tabs = []
        tab_w = min(270., span*.215)
        for index, title in enumerate(('过门图解', '数值表', '车辆参数')):
            self.tabs.append(self.button(title, x+index*(tab_w+8), 146, tab_w, 50, self.set_view, args=(index,)))
        self.active_tab = self.fill(x, 196, tab_w, 3, ORANGE, radius=1.5)
        self.text('A 固定 / B 最近一次', self.left+self.wide-278, 180, 18, GRAY)
        self.fill(self.left+self.wide*.515, 238, 1.2, 144, (0.24, 0.29, 0.38, 0.85), radius=0)
        self.cards, self.badges, self.reasons = [], [], []
        for index, title in enumerate(('A · 调整前', 'B · 调整后')):
            xx = x+index*span*.54
            self.fill(xx+12, 254, 3.5, 30, theme.STEEL_TEXT if index == 0 else theme.AMBER, radius=2)
            self.text(title, xx+26, 278, 28, WHITE, bold=True)
            self.cards.append(self.text('', xx+26, 316, 21, WHITE, wrap=span*.43))
            self.reasons.append(self.text('', xx+26, 378, 17, GRAY, wrap=span*.43))
            self.fill(xx+span*.37-18, 249, 120, 40, theme.STEEL_BG if index == 0 else theme.AMBER_WASH, radius=5)
            badge = self.text('', xx+span*.37+42, 276, 18, theme.STEEL_TEXT if index == 0 else theme.AMBER, bold=True)
            badge.textNode.setAlign(TextNode.ACenter)
            self.badges.append(badge)
        self.fill(x, 402, span, 1.2, (0.24, 0.29, 0.38, 0.85), radius=0)
        self.columns = [self.text('', xx, 445, 22, WHITE) for xx in (x+26, x+span*.47, x+span*.76)]
        self.parameters = [self.text('', xx, 431, 17, WHITE) for xx in (x+26, x+span*.47, x+span*.76)]
        self.metadata = self.text('', x+26, 765, 15, GRAY, wrap=span-52)
        self.diagram = RoadDiagram(self)
        self.view_button = self.tabs[1]
        self.delta = self.text('', x, 748, 20, theme.AMBER, bold=True, wrap=span)
        self.notice = self.text('', x, 806, 15, GRAY, wrap=span)
        self.back = self.button('‹  返回课题', self.left, 862, 230, 58, self.close, dark=True)
        self.text('Esc 返回', self.left+250, 898, 17, GRAY)
        self.info_button = self.button('查看记录信息', self.width-self.left-655, 862, 260, 58,
                                       self.show_record_info, dark=True)
        self.retest_button = self.button('实验台复测 A/B', self.width-self.left-370, 862, 370, 58,
                                         self.run_retest, primary=True)
        unit = 2/941
        self.retest_button['text_pos'] = (16*unit, -7*unit)
        self.widgets.append(atelier.picture(
            self.retest_button, self.base.loader, 'atelier/icon-flask.png',
            (-112*unit, -86*unit, -13*unit, 13*unit), color=INK))
        self.text('Enter 复测', self.width-self.left-115, 938, 14, GRAY)
        self.tab_width = tab_w+8

    def run_retest(self):
        if self.retest_button['state'] != DGG.DISABLED:
            self.retest()

    def resize(self, aspect):
        if not self.root.isHidden() and self.aspect != aspect:
            view, selected = self.view, self.diagram.selected
            self.show(self.store)
            self.set_view(view)
            if not self.store.brakes:
                self.diagram.select(selected)

    def show(self, store):
        self.store = store
        if self.aspect != self.base.getAspectRatio():
            self.layout()
        for badge, item in zip(self.badges, (store.a, store.b), strict=True):
            badge.setText('暂无记录' if item is None else '完成' if item['result']['succeeded'] else '未完成')
        for reason, item in zip(self.reasons, (store.a, store.b), strict=True):
            reason.setText('' if item is None else item['result']['reason'][:26])
        self.tabs[0]['text'] = '制动图解' if store.brakes else '过门图解'
        self.prepare_parameters(store)
        enabled = store.a is not None and store.b is not None
        self.retest_button['state'] = DGG.NORMAL if enabled else DGG.DISABLED
        self.retest_button['frameColor'] = (1, 1, 1, 1) if enabled else (0.55, 0.58, 0.64, 0.72)
        self.retest_button['text_fg'] = INK if enabled else theme.DARK_LOCKED
        self.diagram.show(store)
        self.set_view(0)
        self.back['text'] = '‹  返回制动课题' if store.brakes else '‹  返回过门课题'
        if store.brakes:
            self.show_braking(store)
            self.root.show()
            return
        a, b = store.a, store.b
        self.status.setText('同题改装前后 · 最近完整记录' if a is None else
            ('高速验车' if a['context']['mode'] == 'fast_slalom' else '连续过门')+' · 最近完整记录')
        for side, item, label in zip(self.cards, (a, b), ('A · 调整前这一次', 'B · 新方案最近一次'), strict=True):
            if item is None:
                side.setText('暂无记录\n完成或结束同题后建立')
                continue
            result = item['result']
            elapsed = f"有效{result['run_seconds']:.3f}s" if result['succeeded'] else '未通过 · 无有效总时间'
            side.setText(f"前轮 {item['config']['lateral_stiffness']/1000:g} kN/rad\n"
                         f"{result['gates']}/6门 · {elapsed}")
        rows = [['门'], ['A余量m'], ['B余量m']]
        for index in range(6):
            rows[0].append(str(index+1))
            for column, item in zip(rows[1:], (a, b), strict=True):
                margins = item['result']['clearances'] if item else ()
                column.append(f'{margins[index]:+.3f}' if index < len(margins) else '未到达')
        for column, row in zip(self.columns, rows, strict=True):
            column.setText('\n'.join(row))
        differences = mismatches(a, b) if a is not None and b is not None else []
        if differences:
            self.delta.setText('条件不同，不计算差值。')
        elif a is not None and b is not None and a['result']['succeeded'] and b['result']['succeeded']:
            self.delta.setText(f"有效用时 B−A {b['result']['run_seconds']-a['result']['run_seconds']:+.3f}s；负值表示本次B更快")
        else:
            self.delta.setText('双方都有效完成后才比较总用时；漏门记录只看已到达的门。')
        note = store.notice or '；'.join(differences) or (
            ('A记录于'+a['created_at'][:19]+'；' if a else '')+
            '换方案出发时固定A；B取同目标硬件最近整次记录，不拼接单门。')
        self.notice.setText(note[:150])
        self.root.show()

    def show_braking(self, store):
        a, b = store.a, store.b
        short = a is None or a['result']['short']
        self.status.setText('同题制动改装前后 · 最近完整记录' if a is None else
            ('短距制动验车' if short else '定点刹停')+' · 最近完整记录')
        for side, item, label in zip(self.cards, (a, b), ('A · 安装前这一次', 'B · 安装后最近一次'), strict=True):
            if item is None:
                side.setText('暂无记录\n完成或结束同题后建立')
                continue
            result = item['result']
            outcome = result['medal']+'牌' if result['succeeded'] else '未通过 · 无有效成绩'
            side.setText(f"前制动{item['config']['front_brake_share']:.0%}\n{outcome}")
        rows = [['指标', '入门km/h', '最大前进m' if short else '停车误差m', '停稳s'], ['A'], ['B']]
        for column, item in zip(rows[1:], (a, b), strict=True):
            result = item['result'] if item else None
            values = ([result['entry_kph'], result['stopping_m'] if short else result['error_m'], result['hold_seconds']]
                      if result else [None]*3)
            column.extend('未建立' if value is None else f'{value:.3f}' for value in values)
        for column, row in zip(self.columns, rows, strict=True):
            column.setText('\n'.join(row))
        differences = mismatches(a, b) if a is not None and b is not None else []
        if differences:
            self.delta.setText('条件不同，不计算差值。')
        elif a is not None and b is not None and a['result']['succeeded'] and b['result']['succeeded']:
            old, new = a['result'], b['result']
            delta = new['stopping_m']-old['stopping_m'] if short else abs(new['error_m'])-abs(old['error_m'])
            self.delta.setText(f"{'最大前进' if short else '绝对误差'} B−A {delta:+.3f}m；负值表示本次B更好\n"
                               f"入门速度 B−A {new['entry_kph']-old['entry_kph']:+.3f}km/h；含驾驶时机差异")
        else:
            self.delta.setText('双方有效完成后才比较成绩；失败时的已走距离不算成功成绩。')
        self.notice.setText((store.notice or '；'.join(differences) or
            (('A记录于'+a['created_at'][:19]+'；' if a else '')+'A在下次制动结算改装时替换，B取同题目标硬件最近整次记录。'))[:150])

    def prepare_parameters(self, store):
        fields = (('质量 / kg', 'mass', 1.), ('前侧偏刚度 / kN/rad', 'lateral_stiffness', .001),
                  ('后侧偏刚度 / kN/rad', 'rear_lateral_stiffness', .001),
                  ('制动扭矩 / N·m', 'brake_torque', 1.), ('前制动份额 / %', 'front_brake_share', 100.),
                  ('终传比', 'final_drive', 1.), ('CdA / m²', 'cda', 1.),
                  ('路面附着', 'road_friction', 1.), ('弹簧均值 / kN/m', 'suspension_spring_rates', .001),
                  ('压缩阻尼均值 / kN·s/m', 'suspension_compression_damping', .001),
                  ('伸张阻尼均值 / kN·s/m', 'suspension_extension_damping', .001),
                  ('前防倾份额 / %', 'antiroll_share', 100.))
        rows = [['记录参数'], ['A'], ['B']]
        for title, key, scale in fields:
            rows[0].append(title)
            for values, item in zip(rows[1:], (store.a, store.b), strict=True):
                if item is None:
                    values.append('—')
                    continue
                config = item['config']
                if key == 'cda':
                    value = config['drag_coefficient']*config['frontal_area']
                elif key == 'antiroll_share':
                    rates = config['suspension_antiroll_rates']
                    value = rates[0]/sum(rates) if sum(rates) else 0.
                elif key.startswith('suspension_'):
                    value = sum(config[key])/len(config[key])
                else:
                    value = config[key]
                values.append(f'{value*scale:.3f}')
        for column, values in zip(self.parameters, rows, strict=True):
            column.setText('\n'.join(values))
        context = []
        for side, item in zip('AB', (store.a, store.b), strict=True):
            mode = ('短距制动' if item and item['result']['short'] else '定点刹停') if store.brakes else (
                '高速验车' if item and item['result']['fast'] else '连续过门')
            context.append(side+' 暂无记录' if item is None else
                f"{side} {item['created_at'][:19]} UTC · {mode} · "+
                ('游戏驾驶' if item['context']['driving_mode'] == 'game' else '工程驾驶'))
        self.metadata.setText('\n'.join(context))

    def key(self, key):
        if key == 'escape':
            self.close()
        elif key == 'enter':
            self.run_retest()
        elif key == 'space':
            self.toggle_view()
        elif key == 'tab':
            self.set_view((self.view+1) % 3)
        elif self.graph:
            self.diagram.key(key)

    def set_view(self, index):
        self.view, self.graph = index, index == 0
        self.refresh_view()

    def show_record_info(self):
        self.set_view(2)

    def refresh_view(self):
        self.diagram.root.show() if self.graph else self.diagram.root.hide()
        for column in self.columns:
            column.show() if self.view == 1 else column.hide()
        for column in self.parameters:
            column.show() if self.view == 2 else column.hide()
        self.metadata.show() if self.view == 2 else self.metadata.hide()
        self.delta.hide() if self.view == 2 else self.delta.show()
        for index, tab in enumerate(self.tabs):
            active = index == self.view
            tab['frameTexture'] = atelier.tex(self.base.loader, 'atelier/card-active.png' if active else 'atelier/btn-ghost.png')
            tab['frameColor'] = (1, 1, 1, 1)
            tab['text_fg'] = theme.AMBER if active else GRAY
        self.active_tab.setX(self.view*self.tab_width*2/941)

    def toggle_view(self):
        self.set_view(1 if self.view == 0 else 0)

    def hide(self):
        if not self.root.isHidden():
            self.vehicle_view.hide()
        self.root.hide()

    def close(self):
        self.hide()
        if self.on_back is not None:
            self.on_back()
