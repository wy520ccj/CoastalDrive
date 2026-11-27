"""落日黑曜石与琥珀金风格预算巡回总览与只读历史。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from challenge_build import BuildDraft
from challenge_catalog import ROAD_CHALLENGES
from driving_tour import LEGS, TITLES, points, read_entries
from tour_budget import tour_is_ranked, tour_medal, tour_points
from ui import atelier, theme
from ui.garage_layout import WHITE
from ui.lab_widgets import gradient_panel, rounded_panel
from vehicle_workspace import WorkspaceVehicle

DESCRIPTIONS = ('1.0公里 · 下谷控速再爬坡', '1.8公里 · 连贯通过四门', '2.4公里 · 安全超越3辆')
FILTERS = ('最近完整', '最快', '最省油', '最低费用', '旧规则')


class DrivingTourPanel:
    def __init__(self, parent, font, vehicle_view, start, back, practice):
        self.start, self.back, self.font, self.vehicle_view = start, back, font, vehicle_view
        self.practice = practice
        self.base = vehicle_view.base
        self.regular = theme.load_font('fonts/SourceHanSansSC-Regular.otf')
        self.display_font = theme.load_font(theme.DISPLAY_FONT_FILE)
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

    def fill(self, x, y, width, height, color, radius=6):
        node = rounded_panel(self.content, 'tour-surface', self.box(x, y, width, height), color, radius*2/941)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def text(self, value, x, y, size=22, color=WHITE, *, bold=False, right=False, wrap=None, display=False):
        item = OnscreenText(parent=self.content, text=value,
            font=self.display_font if display else self.font if bold else self.regular,
            fg=color, align=TextNode.ARight if right else TextNode.ALeft, pos=self.point(x, y),
            scale=size*2/941, mayChange=True)
        if wrap:
            item.textNode.setWordwrap(wrap/size)
        self.widgets.append(item)
        self.labels.append(item)
        return item

    def button(self, index, value, x, y, width, height, *, role='plain', enabled=True):
        unit, pxz = 2/941, self.point(x+width/2, y+height/2)
        button = DirectButton(parent=self.content, text=value, text_font=self.font if role == 'primary' else self.regular,
            text_fg=theme.INK if role == 'primary' else WHITE,
            text_scale=(21 if height > 50 else 18)*unit, text_pos=(0, -7*unit),
            pos=(pxz[0], 0, pxz[1]), frameSize=(-width*unit/2, width*unit/2, -height*unit/2, height*unit/2),
            relief=DGG.FLAT, pressEffect=False, command=self.activate, extraArgs=[index],
            state=DGG.NORMAL if enabled else DGG.DISABLED)
        button.setTransparency(TransparencyAttrib.MAlpha)
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
        self.left, self.wide = self.width*.028, min(890., self.width*.655)
        self.buttons, self.roles = [None]*(11+len(LEGS)), {}
        texture = atelier.tex(self.base.loader, atelier.SUNSET_GARAGE_BG)
        background = DirectFrame(parent=self.content, frameSize=self.box(0, 0, self.width, 941),
                                 frameTexture=texture, frameColor=WHITE)
        self.widgets.append(background)
        ratio = self.aspect/(texture.getXSize()/texture.getYSize())
        background.setTexScale(TextureStage.getDefault(), ratio, 1)
        background.setTexOffset(TextureStage.getDefault(), (1-ratio)/2, 0)
        gradient_panel(self.content, 'tour-scrim', self.box(0, 0, self.width*0.72, 941),
                       (0.040, 0.050, 0.072, 0.78), (0.040, 0.050, 0.072, 0.0), horizontal=True)
        gradient_panel(self.content, 'tour-top-scrim', self.box(0, 0, self.width, 128),
                       (0.03, 0.04, 0.06, 0.0), (0.03, 0.04, 0.06, 0.74))
        gradient_panel(self.content, 'tour-bot-scrim', self.box(0, 720, self.width, 221),
                       (0.03, 0.04, 0.06, 0.78), (0.03, 0.04, 0.06, 0.0))
        stage_x = self.left+self.wide+18
        stage_w = self.width-2*self.left-self.wide-18
        self.widgets.append(atelier.picture(
            self.content, self.base.loader, 'atelier/floor-warm-bounce.png',
            self.box(stage_x-20, 480, stage_w+40, 220),
            color=(1, 0.90, 0.74, 0.80), sort_order=-2))
        spec = ROAD_CHALLENGES[LEGS[0]]
        self.vehicle_view.show(self.content, self.box(stage_x, 220, stage_w, 450),
                               WorkspaceVehicle(spec.design_id, spec.configuration(BuildDraft())), studio=True)
        self.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)

        # 顶栏与底栏拉丝黑曜石通栏。
        self.widgets.append(atelier.picture(self.content, self.base.loader, 'atelier/bar-top.png',
                                            self.box(0, 0, self.width, 108)))
        self.widgets.append(atelier.picture(self.content, self.base.loader, 'atelier/footer-surface.png',
                                            self.box(0, 848, self.width, 93)))
        self.fill(self.left, 26, 4.5, 56, theme.AMBER, 2)
        self.text('海岸巡回', self.left+18, 56, 34, WHITE, bold=True)
        self.text('三站独立预算', self.left+18, 88, 17, theme.DARK_SUB)
        self.progress = self.text('历史记录' if self.page else f'已完成 {len(self.store.current)} / 3 站',
                                  self.width-self.left, 54, 26, WHITE, bold=True, right=True)
        legacy = self.page == 1 and self.history == 4
        shown = self.rows()
        medal = tour_medal(shown)
        ranked = tour_is_ranked()
        round_kind = ('旧规则 · 仅圈速' if legacy else
                      medal+'牌 · '+str(tour_points(shown))+'/9分' if medal else
                      '暂无完整记录' if self.page and not shown else '计分轮次' if ranked else '试跑轮次')
        self.text(round_kind, self.width-self.left, 88, 17, theme.AMBER if medal else theme.DARK_SUB, right=True)

        self.widgets.append(atelier.picture(self.content, self.base.loader, 'atelier/panel-obsidian.png',
                                            self.box(self.left-12, 116, self.wide+24, 718)))
        tab_w = min(230., self.wide*.27)
        for index, title in enumerate(('本轮巡回', '历史轮次')):
            x = self.left+22+index*(tab_w+10)
            self.button(4+index, title, x, 146, tab_w, 48, role='active' if index == self.page else 'plain')
        if self.page == 0:
            self.text('全程  5.2 公里', self.left+self.wide-28, 180, 19, theme.STEEL_TEXT, bold=True, right=True)
        else:
            filter_w = (self.wide-44-24)/5
            for index, title in enumerate(FILTERS):
                x = self.left+22+index*(filter_w+6)
                self.button(6+index, title, x, 218, filter_w, 42, role='filter-active' if index == self.history else 'plain')
        header = 314 if self.page else 260
        columns = (self.left+self.wide*.50, self.left+self.wide*.63,
                   self.left+self.wide*.76, self.left+self.wide-40)
        self.fill(self.left+18, header-24, self.wide-36, 34, (0.055, 0.070, 0.098, 0.85), 6)
        self.text('站点', self.left+38, header, 16, theme.DARK_SUB)
        for title, x in zip(('预算', '用时 / s', 'L/100km', '评价'), columns, strict=True):
            self.text(title, x, header, 16, theme.DARK_SUB, right=True)
        rows = self.rows()
        self.details, self.frames = [], []
        for index, mode in enumerate(LEGS):
            spec = ROAD_CHALLENGES[mode]
            top = (338+index*130) if self.page else (284+index*148)
            current = self.page == 0 and index == len(self.store.current)
            row_h = 118 if self.page else 136
            self.widgets.append(atelier.picture(
                self.content, self.base.loader,
                'atelier/card-active.png' if current else 'atelier/card-idle.png',
                self.box(self.left+10, top-6, self.wide-20, row_h+12)))
            if current:
                self.fill(self.left+22, top+18, 4, row_h-36, theme.AMBER, 2)
            self.text(f'{index+1:02d}', self.left+38, top+52, 30,
                      theme.AMBER if current else theme.DARK_SUB, bold=True, display=True)
            self.text(TITLES[index], self.left+112, top+46, 23 if self.wide > 850 else 21, WHITE, bold=True)
            self.text(DESCRIPTIONS[index], self.left+112, top+78, 16 if self.wide > 850 else 15, theme.DARK_SUB)
            if index == 0:
                self.text('250米≥60km/h · 400—650米35—50km/h', self.left+112, top+106, 14, theme.DARK_SUB)
            elif spec.provisional and not self.page:
                self.text('过站需试行铜牌', self.left+112, top+106, 14, theme.DARK_SUB)
            entry = rows[index] if index < len(rows) else None
            budget = '—' if legacy else str(spec.budget)
            time = '—' if entry is None else f'{entry.seconds:.1f}'
            oil = '—' if entry is None or legacy else f'{entry.litres*100_000/spec.distance_m:.1f}'
            medal_prefix = '试行' if spec.provisional and not legacy else ''
            status = ('无记录' if self.page else '待发车' if current else '等待上一站') if entry is None else (
                      medal_prefix+entry.medal+'牌' if entry.medal else '试跑完成')
            for value, x in zip((budget, time, oil), columns[:3], strict=True):
                self.text(value, x, top+60, 22, WHITE if value != '—' else theme.DARK_SUB, right=True,
                          display=value != '—')
            self.details.append(self.text(status, columns[3], top+60, 18,
                                          theme.AMBER if (current or (entry and entry.medal == '金')) else theme.STEEL_TEXT,
                                          bold=current or entry is not None, right=True))
            if not self.page or entry is not None and not legacy:
                self.button(11+index, '单站练习', columns[3]-104, top+78, 104, 32, role='practice')
        note = (self.legacy.notice or '旧版赛制整轮最佳（仅统计用时，不含油耗）' if legacy else self.store.notice or
                '单站练习独立计成绩 · 巡回进度保留')
        self.notice = self.text(note, self.left+28, 800, 16,
                                theme.AMBER if self.store.notice and not legacy else theme.DARK_SUB, wrap=self.wide-56)

        right = self.left+self.wide+22
        span = self.width-self.left-right
        self.widgets.append(atelier.picture(self.content, self.base.loader, 'atelier/card-idle.png',
                                            self.box(right-8, 118, span+16, 76)))
        self.fill(right+8, 138, 3.5, 36, theme.AMBER, 2)
        self.text('固定原车  |  游戏调校 RWD', self.width-self.left-18, 164, 17, WHITE, bold=True, right=True)

        self.widgets.append(atelier.picture(self.content, self.base.loader, 'atelier/panel-obsidian.png',
                                            self.box(right-10, 670, span+20, 162)))
        self.fill(right+10, 694, 4, 40, theme.AMBER, 2)
        metric = self.page and self.history in (1, 2, 3)
        self.text('旧规则记录' if legacy else FILTERS[self.history]+'整轮纪录' if metric else '联合评价',
                  right+26, 714, 23, WHITE, bold=True)
        self.text('保留原轮次的时间与奖牌' if legacy else
                  ('同积分比较全轮'+('用时', '耗油量', '改装费')[self.history-1]) if metric else
                  '每站用时与油耗同次达铜牌' if ranked else '试跑记录用时与赛段油耗',
                  right+26, 754, 17, WHITE, wrap=span-48)
        self.text('与预算巡回分别保存' if legacy else
                  '铜1 / 银2 / 金3分\n总分 3铜 / 6银 / 8金' if ranked else '整轮目标标定中，暂不授奖',
                  right+26, 783 if ranked and not legacy else 800, 15, theme.DARK_SUB, wrap=span-48)
        self.button(2, '‹  返回路线', self.left, 866, 230, 54, role='footer')
        self.button(1, '重开三站', self.left+260, 866, 200, 54, role='secondary', enabled=bool(self.store.current))
        self.button(3, '重试保存', self.left+480, 866, 200, 54, role='secondary', enabled=self.store.unsaved)
        go_enabled = self.page == 1 or len(self.store.current) < 3
        go_btn = self.button(0, '返回本轮' if self.page else '本轮已完成' if len(self.store.current) == 3 else
                             f'配置第{len(self.store.current)+1}站', self.width-self.left-284, 866, 284, 54,
                             role='primary', enabled=go_enabled)
        unit = 2/941
        go_btn['text_pos'] = (16*unit, -7*unit)
        self.widgets.append(atelier.picture(
            go_btn, self.base.loader, 'atelier/icon-steering.png',
            (-86*unit, -60*unit, -13*unit, 13*unit),
            color=theme.INK if go_enabled else theme.DARK_LOCKED))
        self.select(0 if self.buttons[0]['state'] != DGG.DISABLED else 11)

    def select(self, index):
        self.selected = index
        for i, button in enumerate(self.buttons):
            if button is None:
                continue
            role, disabled = self.roles[i], button['state'] == DGG.DISABLED
            focused = i == index
            loader = self.base.loader
            if role == 'primary':
                tex_name = 'atelier/btn-primary-hover.png' if (focused and not disabled) else 'atelier/btn-primary.png'
            elif role in ('active', 'filter-active'):
                tex_name = 'atelier/card-active.png'
            else:
                tex_name = 'atelier/btn-ghost-hover.png' if (focused and not disabled) else 'atelier/btn-ghost.png'
            button['frameTexture'] = atelier.tex(loader, tex_name)
            button['frameColor'] = (0.55, 0.58, 0.64, 0.72) if disabled else (1, 1, 1, 1)
            if disabled:
                fg = theme.DARK_LOCKED
            elif role == 'primary':
                fg = theme.INK
            elif role in ('active', 'filter-active') or (focused and role in ('secondary', 'practice', 'footer')):
                fg = theme.AMBER
            elif role == 'plain' and not focused:
                fg = theme.DARK_SUB
            else:
                fg = WHITE
            button['text_fg'] = fg
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
