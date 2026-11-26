"""生涯的赛事板、简报、车库与领奖画面；不复用工程报告页面。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TextureStage

from career import EVENTS
from career_garage import garage_cars
from ui import theme
from ui.career_events import BOARD_EVENTS, CLUB_EVENTS
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
        self.loader = loader
        self.garage_font = theme.load_font('fonts/SourceHanSansSC-Regular.otf')
        self.garage_values = {}
        self.garage_display_font = theme.load_font(theme.DISPLAY_FONT_FILE)
        self.garage_textures = {}
        self.atelier_btn_tex = {}
        self.garage_topic = 'tires'
        self.garage_aspect = None
        self.layout_aspect = None
        self.page_progress = self.result_data = self.pause_event = None
        self.parent, self.screen_parent = parent, vehicle_view.base.aspect2d
        self.root = DirectFrame(parent=parent, frameSize=(-1.78, 1.78, -1.5, 1.5),
            frameColor=PAPER, sortOrder=300, state=DGG.NORMAL)
        self.content = self.root.attachNewNode('career-content')
        self.labels, self.buttons = [], []
        self.frames = []
        self.accents = set()
        self.flat = set()
        self.photos = {event.id: loader.loadTexture(theme.asset_filename('career/'+event.id+'.png')) for event in EVENTS}
        self.photos.update({key: loader.loadTexture(theme.asset_filename('career/'+event.photo))
                            for key, event in CLUB_EVENTS.items()})
        self.page, self.selected, self.primary, self.back = '', 0, -1, 'board'
        self.event_id = None
        self.board_event, self.board_preview = None, None
        self.challenge_widgets, self.challenge_entries, self.challenge_sliders = [], {}, {}
        self.challenge_readouts, self.challenge_data = {}, None
        self.challenge_updating = False
        self.root.hide()

    def clear(self, page, progress):
        self.challenge_updating = True
        self.board_preview = None
        for widget in self.challenge_widgets:
            widget.destroy()
        self.challenge_widgets.clear()
        self.challenge_entries.clear()
        self.challenge_sliders.clear()
        self.challenge_readouts.clear()
        self.vehicle_view.hide()
        for widget in (*self.labels, *self.buttons, *self.frames):
            widget.destroy()
        self.labels.clear()
        self.garage_values.clear()
        self.buttons.clear()
        self.frames.clear()
        self.atelier_btn_tex.clear()
        self.accents.clear()
        self.flat.clear()
        self.content.removeNode()
        self.content = self.root.attachNewNode('career-content')
        self.page, self.primary = page, -1
        self.page_progress = progress
        self.root.reparentTo(self.screen_parent)
        self.root['frameColor'] = (0, 0, 0, 0)
        self.root.show()

    def label(self, text, x, z, size=.04, color=INK, parent=None, wrap=None, font=None):
        item = OnscreenText(parent=self.content if parent is None else parent, text=text, font=self.font if font is None else font,
            fg=color, align=TextNode.ALeft, pos=(x, z), scale=size, mayChange=True)
        if wrap is not None:
            item.textNode.setWordwrap(wrap/size)
        self.labels.append(item)
        return item

    def button(self, text, x, z, width, height, command, value=None, *, primary=False, enabled=True, accent=False, flat=False, radius=.025):
        node = rounded_panel(self.content, 'button-fill', (-width/2, width/2, -height/2, height/2), WHITE, radius)
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

    def show_board(self, progress, *, chapter=None, event=None):
        from ui.career_layout import board

        self.clear('board', progress)
        self.back = 'exit'
        board(self, progress, chapter=chapter, event=event)

    def show_brief(self, progress, event):
        from ui.career_layout import brief

        self.event_id = event.id
        self.clear('brief', progress)
        self.back = 'board'
        brief(self, progress, event)

    def show_garage(self, progress, vehicle, notice='', *, tab='cars', preview=None, skin_index=None, cars=None):
        from ui.garage_layout import show

        self.clear('garage', progress)
        self.back = 'garage-back'
        show(self, progress, vehicle, notice, tab, preview, skin_index,
             garage_cars(vehicle) if cars is None else cars)

    def part_focus(self, index, topic):
        self.select(index)
        self.vehicle_view.highlight(topic)


    def show_result(self, progress, result, award):
        from ui.career_layout import result as draw_result

        self.event_id = result.event_id
        self.result_data = result, award
        self.clear('result', progress)
        self.back = 'board'
        draw_result(self, progress, result, award)

    def show_pause(self, progress, event):
        from ui.career_layout import pause

        self.pause_event = event
        self.clear('pause', progress)
        self.back = 'resume'
        pause(self, progress, event)

    def select(self, index):
        self.selected = index % len(self.buttons)
        from ui.garage_layout import style

        style(self)
        if self.page != 'garage':
            for i, edge in self.card_edges.items():
                edge.setColor(theme.AMBER if i == self.selected else (1, 1, 1, 0))
        if self.page == 'board' and self.board_preview is not None:
            action, event_id = self.buttons[self.selected]['extraArgs']
            if action == 'brief' and event_id != self.board_event.id:
                self.board_preview(BOARD_EVENTS[event_id])

    def show_challenge(self, progress, spec, draft, tab=0, notice=''):
        from ui.challenge_layout import build_page

        self.clear('challenge', progress)
        self.back = 'challenge-back'
        self.challenge_data = (spec, draft, tab, notice)
        build_page(self, spec, draft, tab, notice)

    def update_challenge(self, draft, notice=''):
        from ui.challenge_layout import update_build

        spec, _, tab, _ = self.challenge_data
        self.challenge_data = spec, draft, tab, notice
        update_build(self, spec, draft, notice)

    def show_challenge_result(self, progress, spec, status):
        from ui.challenge_layout import result_page

        self.clear('challenge-result', progress)
        self.back = 'challenge-back'
        self.challenge_result_data = spec, status
        result_page(self, spec, status)

    def show_sector_chase(self, progress, mode, compatible):
        from ui.sector_chase import selection

        self.clear('sector-chase', progress)
        self.back = 'board'
        self.chase_page = mode, compatible
        selection(self, progress, mode, compatible)

    def show_sector_chase_result(self, progress, mode, status):
        from ui.sector_chase import result

        self.clear('sector-chase-result', progress)
        self.back = 'challenge-back'
        self.chase_page = mode, status
        result(self, progress, mode, status)

    def show_season_cup(self, progress, store, *, picking=False, recap=False, preview=None):
        from ui.season_cup import draw

        self.clear('season-cup', progress)
        self.back = 'cup-menu' if picking and store is not None else 'board'
        self.cup_page = {'store': store, 'picking': picking, 'recap': recap, 'preview': preview}
        draw(self, progress, store, picking=picking, recap=recap, preview=preview)

    def show_challenge_pause(self, progress, spec, draft, status):
        from ui.challenge_layout import pause_page

        self.clear('challenge-pause', progress)
        self.back = 'challenge-resume'
        self.challenge_pause_data = spec, draft, status
        pause_page(self, spec, draft, status)

    def show_reference_result(self, spec, draft, data, notice=''):
        from ui.challenge_layout import reference_result_page

        self.clear('reference-result', None)
        self.back = 'challenge-adjust'
        self.reference_result_data = spec, draft, data, notice
        reference_result_page(self, spec, draft, data, notice)

    def key(self, key):
        entries = tuple(self.challenge_entries.values())
        if any(entry['focus'] for entry in entries):
            if key == 'control-a':
                # DirectEntry不支持文字选择；数值框用此快捷键开始整值替换，Esc仍可还原。
                next(entry for entry in entries if entry['focus']).enterText('')
                return
            if self.page == 'challenge' and key in ('arrow_up', 'arrow_down'):
                name = next(name for name, entry in self.challenge_entries.items() if entry['focus'])
                self.action('challenge-step', (name, 1 if key == 'arrow_up' else -1))
                return
            if key == 'enter' and not self.action('challenge-commit'):
                return
            if key == 'escape':
                self.update_challenge(self.challenge_data[1])
            if key in ('escape', 'enter'):
                for entry in entries:
                    entry['focus'] = 0
            return
        directions = {'arrow_left': (-1, 0), 'a': (-1, 0), 'arrow_right': (1, 0), 'd': (1, 0),
                      'arrow_up': (0, 1), 'w': (0, 1), 'arrow_down': (0, -1), 's': (0, -1)}
        if key in directions:
            vx, vz = directions[key]
            if (vz == 1 and self.garage_roles[self.selected] == 'footer'
                    and self.buttons[self.primary]['state'] != DGG.DISABLED):
                self.select(self.primary)
                return
            if (self.page == 'garage' and vx > 0
                    and self.garage_roles.get(self.selected) in ('category', 'category-active')):
                self.action('garage-orbit', 25)
                return
            current, candidates = self.buttons[self.selected], []
            for index, button in enumerate(self.buttons):
                dx, dz = button.getX()-current.getX(), button.getZ()-current.getZ()
                ahead, across = dx*vx+dz*vz, abs(dx*vz-dz*vx)
                if button['state'] != DGG.DISABLED and ahead > .025:
                    candidates.append((ahead+across*3., index))
            if candidates:
                self.select(min(candidates)[1])
            elif self.page == 'garage' and vx != 0:
                self.action('garage-orbit', 25 * vx)
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
        self.challenge_updating = True
        for entry in self.challenge_entries.values():
            entry['focus'] = 0
        self.root.hide()
        self.vehicle_view.hide()
        self.challenge_updating = False



    def resize(self, aspect):
        if self.root.isHidden():
            return
        if self.page == 'garage' and self.garage_aspect != aspect:
            self.action('garage-redraw', None)
        elif self.page != 'garage' and self.layout_aspect != aspect:
            selected = self.buttons[self.selected]['extraArgs']
            if self.page == 'board':
                self.show_board(self.page_progress, event=self.board_event)
            elif self.page == 'brief':
                self.show_brief(self.page_progress, BOARD_EVENTS[self.event_id])
            elif self.page == 'result':
                self.show_result(self.page_progress, *self.result_data)
            elif self.page == 'pause':
                self.show_pause(self.page_progress, self.pause_event)
            elif self.page == 'challenge':
                pending = {key: entry.get() for key, entry in self.challenge_entries.items()}
                focused = next((key for key, entry in self.challenge_entries.items() if entry['focus']), None)
                self.show_challenge(self.page_progress, *self.challenge_data)
                for key, raw in pending.items():
                    self.challenge_entries[key].enterText(raw)
                if focused is not None:
                    self.challenge_entries[focused]['focus'] = 1
            elif self.page == 'challenge-result':
                self.show_challenge_result(self.page_progress, *self.challenge_result_data)
            elif self.page == 'sector-chase':
                self.show_sector_chase(self.page_progress, *self.chase_page)
            elif self.page == 'sector-chase-result':
                self.show_sector_chase_result(self.page_progress, *self.chase_page)
            elif self.page == 'season-cup':
                self.show_season_cup(self.page_progress, **self.cup_page)
            elif self.page == 'challenge-pause':
                self.show_challenge_pause(self.page_progress, *self.challenge_pause_data)
            elif self.page == 'reference-result':
                self.show_reference_result(*self.reference_result_data)
            for index, button in enumerate(self.buttons):
                if button['extraArgs'] == selected:
                    self.select(index)
                    break

    def destroy(self):
        for widget in self.challenge_widgets:
            widget.destroy()
        for widget in (*self.labels, *self.buttons, *self.frames):
            widget.destroy()
        self.root.destroy()
