"""预算巡回总览与只读历史；构图对应challenge-tour-v2两张设计图。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from challenge_build import BuildDraft
from challenge_catalog import ROAD_CHALLENGES
from driving_tour import LEGS, TITLES, points, read_entries
from tour_budget import tour_is_ranked, tour_medal, tour_points
from ui import theme
from ui.garage_layout import ORANGE, WHITE
from ui.lab_widgets import rounded_panel
from vehicle_workspace import WorkspaceVehicle

DESCRIPTIONS = ('1.0公里 · 下谷控速再爬坡', '1.8公里 · 连贯通过四门', '2.4公里 · 安全超越3辆')
FILTERS = ('最近完整', '最快', '最省油', '最低费用', '旧规则')


class DrivingTourPanel:
    def __init__(self, parent, font, vehicle_view, start, back, practice):
        self.start, self.back, self.font, self.vehicle_view = start, back, font, vehicle_view
        self.practice = practice
        self.base = vehicle_view.base
        self.regular = theme.load_font('fonts/SourceHanSansSC-Regular.otf')
        self.root = DirectFrame(parent=parent, frameColor=(0, 0, 0, 0), frameSize=(-2.5, 2.5, -1, 1),
                                sortOrder=310, state=DGG.NORMAL)
        self.root.hide()
        self.content, self.aspect = None, None
        self.widgets, self.buttons, self.labels = [], [], []
        self.page, self.history, self.selected = 0, 0, 0

    def point(self, x, y):
        return (x-self.width/2)*2/941, 1-y*2/941

    def box(self, x, y, width, height):
        a, b = self.point(x, y+height), self.point(x+width, y)
        return a[0], b[0], a[1], b[1]

    def fill(self, x, y, width, height, color, radius=4):
        node = rounded_panel(self.content, 'tour-surface', self.box(x, y, width, height), color, radius*2/941)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def text(self, value, x, y, size=22, color=theme.TEXT_LIGHT, *, bold=False, right=False, wrap=None):
        item = OnscreenText(parent=self.content, text=value, font=self.font if bold else self.regular,
            fg=color, align=TextNode.ARight if right else TextNode.ALeft, pos=self.point(x, y),
            scale=size*2/941, mayChange=True)
        if wrap:
            item.textNode.setWordwrap(wrap/size)
        self.widgets.append(item)
        self.labels.append(item)
        return item

    def button(self, index, value, x, y, width, height, *, role='plain', enabled=True):
        unit, pxz = 2/941, self.point(x+width/2, y+height/2)
        if role in ('secondary', 'practice'):
            self.fill(x-1, y-1, width+2, height+2, theme.SLATE_BORDER, 6)
        button = DirectButton(parent=self.content, text=value, text_font=self.regular,
            text_fg=theme.TEXT_LIGHT,
            text_scale=(23 if height > 50 else 19)*unit, text_pos=(0, -7*unit),
            pos=(pxz[0], 0, pxz[1]), frameSize=(-width*unit/2, width*unit/2, -height*unit/2, height*unit/2),
            relief=DGG.FLAT, pressEffect=False, command=self.activate, extraArgs=[index],
            state=DGG.NORMAL if enabled else DGG.DISABLED)
        button.bind(DGG.ENTER, lambda event, i=index: self.select(i))
        self.widgets.append(button)
        self.buttons[index] = button
        self.roles[index] = role
        return button

    def show(self, store, legacy, *, keep_view=False):
        self.store, self.legacy = store, legacy
        rounds = [read_entries(group['best'] or group['current']) for group in legacy.groups.values()]
        self.legacy_rows = max(rounds, key=lambda rows: (len(rows) == 3, points(rows), -sum(row.seconds for row in rows)), default=())
        if not keep_view:
            self.page, self.history = 0, 0
        self.draw()
        self.root.show()

    def rows(self):
        if self.page == 0:
            return self.store.current
        if self.history == 0:
            return self.store.latest
        if self.history == 4:
            return self.legacy_rows
        return self.store.bests.get(('fastest', 'economy', 'cheapest')[self.history-1], ())

    def draw(self):
        self.vehicle_view.hide()
        for widget in self.widgets:
            widget.destroy()
        self.widgets, self.labels = [], []
        if self.content is not None:
            self.content.removeNode()
        self.content = self.root.attachNewNode('tour-content')
        self.aspect, self.width = self.base.getAspectRatio(), 941*self.base.getAspectRatio()
        self.left, self.wide = self.width*.029, min(886., self.width*.66)
        self.buttons, self.roles = [None]*(11+len(LEGS)), {}
        texture = self.base.loader.loadTexture(theme.asset_filename('backgrounds/garage-coastal-v2.png'))
        background = DirectFrame(parent=self.content, frameSize=self.box(0, 0, self.width, 941),
                                 frameTexture=texture, frameColor=WHITE)
        self.widgets.append(background)
        ratio = self.aspect/(texture.getXSize()/texture.getYSize())
        background.setTexScale(TextureStage.getDefault(), ratio, 1)
        background.setTexOffset(TextureStage.getDefault(), (1-ratio)/2, 0)
        spec = ROAD_CHALLENGES[LEGS[0]]
        self.vehicle_view.show(self.content, self.box(self.left+self.wide+18, 220,
            self.width-2*self.left-self.wide-18, 450), WorkspaceVehicle(spec.design_id, spec.configuration(BuildDraft())), studio=True)
        self.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        self.fill(0, 0, self.width, 110, theme.SLATE_BAR, 0)
        self.fill(0, 110, self.width, 1.5, theme.SLATE_BORDER, 0)
        self.fill(0, 846, self.width, 95, theme.SLATE_BAR, 0)
        self.fill(0, 845, self.width, 1.5, theme.SLATE_BORDER, 0)
        self.fill(self.left, 24, 4, 62, ORANGE, 2)
        self.text('海岸巡回', self.left+18, 58, 36, theme.TEXT_LIGHT, bold=True)
        self.text('三站独立预算', self.left+18, 92, 20, theme.TEXT_SUB)
        self.progress = self.text('历史记录' if self.page else f'已完成 {len(self.store.current)} / 3 站',
                                  self.width-self.left, 56, 28, theme.TEXT_LIGHT, bold=True, right=True)
        legacy = self.page == 1 and self.history == 4
        shown = self.rows()
        medal = tour_medal(shown)
        ranked = tour_is_ranked()
        round_kind = ('旧规则 · 仅圈速' if legacy else
                      medal+'牌 · '+str(tour_points(shown))+'/9分' if medal else
                      '暂无完整记录' if self.page and not shown else '计分轮次' if ranked else '试跑轮次')
        self.text(round_kind, self.width-self.left, 92, 19, theme.GOLD if medal else theme.TEXT_SUB, right=True)
        self.fill(self.left-1, 125, self.wide+2, 697, theme.SLATE_BORDER, 13)
        self.fill(self.left, 126, self.wide, 695, theme.SLATE_GLASS, 12)
        tab_w = min(250., self.wide*.28)
        for index, title in enumerate(('本轮巡回', '历史轮次')):
            x = self.left+22+index*tab_w
            self.button(4+index, title, x, 148, tab_w-6, 56, role='active' if index == self.page else 'plain')
            if index == self.page:
                self.fill(x+14, 204, tab_w-34, 3, ORANGE, 1.5)
        if self.page == 0:
            self.text('全程  5.2 公里', self.left+self.wide-30, 188, 22, theme.TEXT_SUB, right=True)
        else:
            filter_w = (self.wide-44)/5
            for index, title in enumerate(FILTERS):
                x = self.left+22+index*filter_w
                self.button(6+index, title, x, 228, filter_w-4, 46, role='filter-active' if index == self.history else 'plain')
                if index == self.history:
                    self.fill(x+6, 274, filter_w-16, 3, ORANGE, 1.5)
        header = 326 if self.page else 270
        columns = (self.left+self.wide*.50, self.left+self.wide*.63,
                   self.left+self.wide*.77, self.left+self.wide-.025*self.wide)
        self.text('站点', self.left+40, header, 19, theme.TEXT_SUB)
        for title, x in zip(('预算', '用时 / s', 'L/100km', '评价'), columns, strict=True):
            self.text(title, x, header, 18, theme.TEXT_SUB, right=True)
        rows = self.rows()
        self.details, self.frames = [], []
        for index, mode in enumerate(LEGS):
            spec = ROAD_CHALLENGES[mode]
            top = (348+index*128) if self.page else (294+index*146)
            current = self.page == 0 and index == len(self.store.current)
            if current:
                self.fill(self.left+14, top, self.wide-28, 138, (.22, .15, .14, .92), 8)
                self.fill(self.left+14, top, 5, 138, ORANGE, 2)
            self.text(f'{index+1:02d}', self.left+37, top+53, 33, ORANGE if current else theme.TEXT_SUB, bold=True)
            self.text(TITLES[index], self.left+115, top+47, 25 if self.wide > 850 else 22, theme.TEXT_LIGHT, bold=True)
            self.text(DESCRIPTIONS[index], self.left+115, top+80, 17 if self.wide > 850 else 15, theme.TEXT_SUB)
            if index == 0:
                self.text('250米≥60km/h · 400—650米35—50km/h', self.left+115, top+110, 15, theme.TEXT_SUB)
            elif spec.provisional and not self.page:
                self.text('过站需试行铜牌', self.left+115, top+110, 15, theme.TEXT_SUB)
            entry = rows[index] if index < len(rows) else None
            budget = '—' if legacy else str(spec.budget)
            time = '—' if entry is None else f'{entry.seconds:.1f}'
            oil = '—' if entry is None or legacy else f'{entry.litres*100_000/spec.distance_m:.1f}'
            medal_prefix = '试行' if spec.provisional and not legacy else ''
            status = ('无记录' if self.page else '待发车' if current else '等待上一站') if entry is None else (
                      medal_prefix+entry.medal+'牌' if entry.medal else '试跑完成')
            for value, x in zip((budget, time, oil), columns[:3], strict=True):
                self.text(value, x, top+64, 24, theme.TEXT_LIGHT if value != '—' else theme.TEXT_SUB, right=True)
            self.details.append(self.text(status, columns[3], top+64, 19,
                                          ORANGE if current else theme.GOLD if entry and entry.medal == '金' else theme.TEXT_LIGHT,
                                          right=True))
            if not self.page or entry is not None and not legacy:
                self.button(11+index, '单站练习', columns[3]-104, top+83, 104, 33, role='practice')
            self.fill(self.left+22, top+(122 if self.page else 140), self.wide-44, 1, theme.SLATE_BORDER, 0)
        note = (self.legacy.notice or '旧规则整轮最佳 · 不补油耗，不换算新奖牌' if legacy else self.store.notice or
                '单站练习独立计成绩 · 巡回进度保留')
        self.notice = self.text(note, self.left+30, 797, 17, ORANGE if self.store.notice and not legacy else theme.TEXT_SUB, wrap=self.wide-60)
        right = self.left+self.wide+22
        span = self.width-self.left-right
        self.fill(right-1, 125, span+2, 62, theme.SLATE_BORDER, 11)
        self.fill(right, 126, span, 60, theme.SLATE_GLASS, 10)
        self.text('固定原车 · 游戏调校 RWD', self.width-self.left-16, 164, 19, theme.TEXT_LIGHT, right=True)
        self.fill(right-1, 677, span+2, 145, theme.SLATE_BORDER, 11)
        self.fill(right, 678, span, 143, theme.SLATE_GLASS, 10)
        metric = self.page and self.history in (1, 2, 3)
        self.text('旧规则记录' if legacy else FILTERS[self.history]+'整轮纪录' if metric else '联合评价',
                  right+22, 714, 25, theme.TEXT_LIGHT, bold=True)
        self.text('保留原轮次的时间与奖牌' if legacy else
                  ('同积分比较全轮'+('用时', '耗油量', '改装费')[self.history-1]) if metric else
                  '每站用时与油耗同次达铜牌' if ranked else '试跑记录用时与赛段油耗',
                  right+22, 754, 19, theme.TEXT_LIGHT, wrap=span-44)
        self.text('与预算巡回分别保存' if legacy else
                  '铜1 / 银2 / 金3分\n总分 3铜 / 6银 / 8金' if ranked else '整轮目标标定中，暂不授奖',
                  right+22, 783 if ranked and not legacy else 800, 16, theme.TEXT_SUB, wrap=span-44)
        self.button(2, '‹  返回路线', self.left, 862, 230, 58, role='footer')
        self.button(1, '重开三站', self.left+260, 862, 200, 58, role='secondary', enabled=bool(self.store.current))
        self.button(3, '重试保存', self.left+480, 862, 200, 58, role='secondary', enabled=self.store.unsaved)
        self.button(0, '返回本轮' if self.page else '本轮已完成' if len(self.store.current) == 3 else
                    f'配置第{len(self.store.current)+1}站', self.width-self.left-284, 862, 284, 58,
                    role='primary', enabled=self.page == 1 or len(self.store.current) < 3)
        self.select(0 if self.buttons[0]['state'] != DGG.DISABLED else 11)

    def select(self, index):
        self.selected = index
        for i, button in enumerate(self.buttons):
            if button is None:
                continue
            role, disabled = self.roles[i], button['state'] == DGG.DISABLED
            focused = i == index
            if role == 'primary':
                color = (.22, .27, .34, 1) if disabled else (theme.ORANGE_BRIGHT if focused else ORANGE)
            elif role in ('secondary', 'active', 'practice', 'filter-active'):
                color = theme.SLATE_CARD_HI if focused else theme.SLATE_CARD
            elif role == 'footer':
                color = (1, 1, 1, .12) if focused else (0, 0, 0, 0)
            else:
                color = theme.SLATE_CARD if focused else (.07, .10, .14, .78)
            button['frameColor'] = (.18, .22, .28, .8) if disabled else color
            button['text_fg'] = (theme.TEXT_LOCKED if disabled else ORANGE if role == 'filter-active'
                                 else theme.TEXT_SUB if role == 'plain' and not focused else theme.TEXT_LIGHT)
            button.clearColorScale()

    def activate(self, index):
        if self.buttons[index] is None or self.buttons[index]['state'] == DGG.DISABLED:
            return
        if index in (4, 5) or index == 0 and self.page:
            self.page = 0 if index == 0 else index-4
            self.draw()
        elif index >= 11:
            leg = index-11
            rows = self.rows()
            self.hide()
            self.practice(LEGS[leg], rows[leg].build if leg < len(rows) else None)
        elif index >= 6:
            self.history = index-6
            self.draw()
        elif index == 3:
            self.store.save()
            self.draw()
        else:
            self.hide()
            self.back() if index == 2 else self.start(index == 1)

    def key(self, key):
        if key in ('arrow_up', 'arrow_left', 'w', 'a', 'arrow_down', 'arrow_right', 's', 'd', 'tab'):
            direction = -1 if key in ('arrow_up', 'arrow_left', 'w', 'a') else 1
            for offset in range(1, len(self.buttons)+1):
                index = (self.selected+offset*direction) % len(self.buttons)
                if self.buttons[index] is not None and self.buttons[index]['state'] != DGG.DISABLED:
                    self.select(index)
                    break
        elif key == 'enter':
            self.activate(self.selected)
        elif key == 'escape':
            self.hide()
            self.back()

    def resize(self, aspect):
        if not self.root.isHidden() and self.aspect != aspect:
            self.draw()

    def hide(self):
        if not self.root.isHidden():
            self.vehicle_view.hide()
        self.root.hide()
