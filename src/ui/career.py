"""生涯的赛事板、简报、车库与领奖画面；不复用工程报告页面。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TextureStage

from career import EVENTS
from career_garage import garage_cars
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
        self.loader = loader
        self.garage_font = theme.load_font('fonts/SourceHanSansSC-Regular.otf')
        self.garage_display_font = theme.load_font(theme.DISPLAY_FONT_FILE)
        self.garage_textures = {}
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

    def show_board(self, progress):
        from ui.career_layout import board

        self.clear('board', progress)
        self.back = 'exit'
        board(self, progress)

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
                edge.setColor((1, .31, .12, 1) if i == self.selected else (1, 1, 1, 0))

    def key(self, key):
        directions = {'arrow_left': (-1, 0), 'a': (-1, 0), 'arrow_right': (1, 0), 'd': (1, 0),
                      'arrow_up': (0, 1), 'w': (0, 1), 'arrow_down': (0, -1), 's': (0, -1)}
        if key in directions:
            vx, vz = directions[key]
            if (vz == 1 and self.garage_roles[self.selected] == 'footer'
                    and self.buttons[self.primary]['state'] != DGG.DISABLED):
                self.select(self.primary)
                return
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

    def resize(self, aspect):
        if self.root.isHidden():
            return
        if self.page == 'garage' and self.garage_aspect != aspect:
            self.action('garage-redraw', None)
        elif self.page != 'garage' and self.layout_aspect != aspect:
            selected = self.buttons[self.selected]['extraArgs']
            if self.page == 'board':
                self.show_board(self.page_progress)
            elif self.page == 'brief':
                self.show_brief(self.page_progress, next(event for event in EVENTS if event.id == self.event_id))
            elif self.page == 'result':
                self.show_result(self.page_progress, *self.result_data)
            elif self.page == 'pause':
                self.show_pause(self.page_progress, self.pause_event)
            for index, button in enumerate(self.buttons):
                if button['extraArgs'] == selected:
                    self.select(index)
                    break

    def destroy(self):
        for widget in (*self.labels, *self.buttons, *self.frames):
            widget.destroy()
        self.root.destroy()
