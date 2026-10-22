"""车库三页的固定构图；坐标直接对应garage-v2设计图。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from career import PARTS
from skins import SKINS
from ui import theme
from ui.lab_widgets import rounded_panel

INK = (.055, .075, .13, 1)
GRAY = (.36, .39, .45, 1)
WHITE = (1, 1, 1, 1)
ORANGE = (1, .31, .12, 1)
LINE = (.79, .81, .84, 1)


def show(panel, progress, vehicle, notice, tab, preview, skin_index, cars):
    aspect = panel.vehicle_view.base.getAspectRatio()
    panel.garage_aspect = aspect
    panel.garage_roles = {}
    height, width = 941., 941.*aspect
    unit = 2/height
    left, top, wide = width*.031, 122., min(462., width*.295)
    inset, inner = 24., wide-48.

    def point(x, y):
        return (x-width/2)*unit, 1-y*unit

    def box(x, y, w, h):
        a, b = point(x, y+h), point(x+w, y)
        return a[0], b[0], a[1], b[1]

    def fill(x, y, w, h, color, radius=4):
        node = rounded_panel(panel.content, 'garage-fill', box(x, y, w, h), color, radius*unit)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def label(text, x, y, size=18, color=INK, bold=False, right=False, wrap=None):
        p = point(x, y)
        item = panel.label(text, *p, size*unit, color, font=panel.font if bold else panel.garage_font)
        if right:
            item.textNode.setAlign(TextNode.ARight)
        if wrap is not None:
            item.textNode.setWordwrap(wrap/size)
        return item

    def image(name, x, y, w, h, color=WHITE):
        if name not in panel.garage_textures:
            panel.garage_textures[name] = panel.loader.loadTexture(theme.asset_filename(name))
        frame = DirectFrame(parent=panel.content, frameSize=box(x, y, w, h),
            frameTexture=panel.garage_textures[name], frameColor=color, state=DGG.DISABLED)
        frame.setTransparency(TransparencyAttrib.MAlpha)
        panel.frames.append(frame)
        return frame

    def button(text, x, y, w, h, command, value=None, *, role='plain', enabled=True, primary=False):
        px, pz = point(x+w/2, y+h/2)
        item = panel.button(text, px, pz, w*unit, h*unit, command, value,
                            enabled=enabled, primary=primary, radius=4*unit)
        item['text_font'] = panel.garage_font
        item['text_scale'] = (24 if role in ('primary', 'tab', 'tab-active') else 21)*unit
        if role in ('primary', 'tab-active'):
            item['text_font'] = panel.font
        item['text_pos'] = (0, -7*unit)
        item.setTransparency(TransparencyAttrib.MAlpha)
        panel.garage_roles[len(panel.buttons)-1] = role
        return item

    image('backgrounds/garage-coastal-v2.png', 0, 0, width, height)
    background = panel.frames[-1]
    texture = panel.garage_textures['backgrounds/garage-coastal-v2.png']
    ratio = aspect/(texture.getXSize()/texture.getYSize())
    background.setTexScale(TextureStage.getDefault(), ratio, 1)
    background.setTexOffset(TextureStage.getDefault(), (1-ratio)/2, 0)
    # 车模只在操作面板右侧取景，背景独立铺满画面。
    preview = vehicle if preview is None or tab != 'cars' else preview
    view_left, view_top = left+wide+18, 267.
    view_right, view_bottom = width-40, 824.
    panel.vehicle_view.show(panel.content, box(view_left, view_top, view_right-view_left, view_bottom-view_top),
                            preview, studio=True, skin_index=skin_index)
    panel.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
    panel.vehicle_view.highlight(None)
    fill(0, 0, width, 74, (.04, .055, .075, .76), 0)
    fill(0, 860, width, 81, (.04, .055, .075, .78), 0)
    brand = label('COASTAL DRIVE', width*.037, 50, 34 if aspect > 1.5 else 28, WHITE, True)
    brand['font'] = panel.garage_display_font
    if aspect > 1.6:
        label('│  海岸车库', width*.185, 49, 20, WHITE)
    nav_width = 145 if aspect > 1.5 else 130
    for i, (key, title) in enumerate((('cars', '我的车辆'), ('upgrade', '升级改装'), ('paint', '车身颜色'))):
        x = width*(.40+i*.098)-nav_width/2
        button(title, x, 12, nav_width, 50, 'garage-tab', key, role='tab-active' if key == tab else 'tab')
        if key == tab:
            fill(x, 59, nav_width, 4, ORANGE, 0)
    if aspect > 1.5:
        label(f'★  {progress.stars} / 18 星', width-350, 49, 23, WHITE)
        label(f'{progress.credits} 积分', width-55, 49, 23, WHITE, right=True)
    else:
        label(f'★ {progress.stars} / 18 星', width-35, 30, 18, WHITE, right=True)
        label(f'{progress.credits} 积分', width-35, 58, 18, WHITE, right=True)
    fill(left, top, wide, 706, (.98, .98, .99, .94))
    titles = {'cars': '我的车辆', 'upgrade': '升级改装', 'paint': '车身颜色'}
    label(titles[tab], left+inset, 189, 43, bold=True)
    car = next(item for item in cars if item.design_id == preview.design_id)
    config = preview.config
    power = max(rpm*torque/9549.3 for rpm, torque in config.torque_curve)
    fill(width-195, 126, 2, 62, (.98, .98, .98, .95), 0)
    label(car.name, width-55, 150, 25, WHITE, True, right=True)
    tuning = '项目调校 · ' if preview.design_id in ('coastal-hatch', 'club-coupe') else ''
    label(f'{tuning}{power:.0f} kW  /  {config.mass:.0f} kg', width-55, 183, 17, WHITE, right=True)
    if tab == 'upgrade':
        label(car.name+' · '+car.category.split('/')[-1].strip(), left+inset, 223, 20, GRAY)
        categories = (('tires', '轮胎', 'wheel'), ('brakes', '制动', 'disc'),
                      ('suspension', '悬架', 'car-suspension'), ('power', '动力', 'engine'))
        for index, (topic, name, icon) in enumerate(categories):
            x, y, w = left+inset+(index % 2)*(inner+12)/2, 248+(index//2)*132, (inner-12)/2
            active = topic == panel.garage_topic
            if active:
                fill(x-2, y-2, w+4, 120, ORANGE)
            button('', x, y, w, 116, 'garage-topic', topic,
                   role='category-active' if active else 'category', enabled=index < 2)
            image('garage-v2/'+icon+'.png', x+w/2-24, y+15, 48, 48,
                  WHITE if index < 2 else (.50, .52, .57, 1))
            label(name, x+w/2-24, y+91, 23, INK if index < 2 else GRAY, True)
            if index >= 2:
                label('即将开放', x+w/2-35, y+113, 17, GRAY)
        fill(left+inset, 522, inner, 1, LINE, 0)
        part = next(part for part in PARTS if part.topic == panel.garage_topic)
        image('garage-v2/'+('tire' if part.topic == 'tires' else 'brake')+'.png', left+inset, 539, 154, 154)
        detail_x = left+inset+175
        label(part.name, detail_x, 569, 24, bold=True)
        label('提升前轮转向响应' if part.topic == 'tires' else '更多制动力分给前轮', detail_x, 599, 17, GRAY, wrap=inner-175)
        label('前轴侧偏刚度' if part.topic == 'tires' else '前轴制动力分配', detail_x, 642, 16, GRAY)
        label('70 kN/rad' if part.topic == 'tires' else '70%', left+wide-inset, 666, 19, GRAY, right=True)
        installed = vehicle.config.lateral_stiffness == 70000. if part.topic == 'tires' else vehicle.config.front_brake_share == .7
        owned, unlocked = part.id in progress.owned, progress.stars >= part.unlock
        affordable = owned or progress.credits >= part.price
        label('已购零件' if owned else f'{part.price} 积分', detail_x, 695, 28, ORANGE, True)
        text = ('已安装' if installed else '安装已购零件' if owned else f'{part.unlock}星解锁' if not unlocked else
                '购买并安装' if affordable else f'还差{part.price-progress.credits}积分')
        button(text, left+inset, 711, inner, 55, 'part', part.id,
               role='primary', primary=True, enabled=not installed and unlocked and affordable)
        fill(left+inset, 777, inner, 1, LINE, 0)
        button('恢复改装前车辆', left+inset, 784, inner, 34, 'restore', role='quiet')
    elif tab == 'cars':
        count = sum(progress.stars >= item.unlock or item.design_id == vehicle.design_id for item in cars)
        label(f'已解锁 {count} / {len(cars)}', left+inset, 223, 20, GRAY)
        selected = next(i for i, item in enumerate(cars) if item.design_id == preview.design_id)
        first = min(max(0, selected-2), max(0, len(cars)-4))
        for index, item in enumerate(cars[first:first+4]):
            x, y = left+inset, 248+index*99
            active = item.design_id == preview.design_id
            if active:
                fill(x-2, y-2, inner+4, 94, ORANGE)
            button('', x, y, inner, 90, 'garage-car', item.design_id, role='category-active' if active else 'category')
            # 工程存档沿用其实际经典双门外观，不用虚构缩略图。
            thumbnail = item.design_id if item.design_id in ('game-tuned', 'coastal-hatch', 'coastal-roadster',
                'gr86-2022-premium-6mt', 'coastal-gt', 'club-coupe') else 'game-tuned'
            image('garage-v2/car-'+thumbnail+'.png', x+5, y+5, 136, 76)
            label(item.name, x+148, y+33, 22, bold=True)
            label('驾驶中' if item.design_id == vehicle.design_id else '已解锁' if progress.stars >= item.unlock else
                  f'{item.unlock}星解锁', x+148, y+62, 16, ORANGE if active else GRAY)
        if len(cars) > 4:
            button('‹', left+inset, 648, 42, 34, 'garage-car', cars[(selected-1) % len(cars)].design_id, role='quiet')
            label(f'{selected+1} / {len(cars)}', left+wide/2-20, 672, 17, GRAY)
            button('›', left+wide-inset-42, 648, 42, 34, 'garage-car', cars[(selected+1) % len(cars)].design_id, role='quiet')
        current = preview.design_id == vehicle.design_id
        unlocked = current or progress.stars >= car.unlock
        button('当前驾驶' if current else '选择驾驶' if unlocked else f'获得{car.unlock}星解锁',
               left+inset, 711, inner, 55, 'garage-select', role='primary', primary=True, enabled=unlocked and not current)
        label('预览不会更换当前车辆', left+inset, 805, 17, GRAY)
    else:
        label(car.name+' · 选择车漆', left+inset, 223, 20, GRAY)
        fill(left+inset, 246, inner, 186, (.91, .92, .94, 1))
        image('garage-v2/paint-'+str(skin_index)+'.png', left+inset+8, 251, 174, 174)
        label(SKINS[skin_index].name, left+inset+190, 333, 27, bold=True)
        label('车身颜色', left+inset+190, 365, 17, GRAY)
        cell = inner/3
        for index, skin in enumerate(SKINS):
            x, y = left+inset+(index % 3)*cell, 449+(index//3)*119
            active = index == skin_index
            button('', x, y, cell-8, 109, 'garage-paint', index,
                   role='category-active' if active else 'category')
            image('garage-v2/paint-'+str(index)+'.png', x+(cell-8)/2-35, y+3, 70, 70)
            label(skin.name, x+(cell-8)/2-30, y+95, 19, ORANGE if active else INK)
        button('应用颜色', left+inset, 711, inner, 55, 'garage-paint-save', role='primary', primary=True)
        button('取消预览', left+inset, 784, inner, 34, 'garage-tab', 'paint', role='quiet')
    # 通知只占面板与底栏之间的一条状态位，不覆盖车辆。
    message = notice or progress.notice
    if message:
        label(message, left+inset, 849, 16, WHITE)
    button('Enter   确认', width*.027, 880, 145, 42, 'garage-confirm', role='footer')
    button('Esc   返回', width*.125, 880, 135, 42, 'garage-back', role='footer')
    button('←', width*.43, 880, 46, 42, 'garage-orbit', -25, role='footer')
    button('→', width*.475, 880, 46, 42, 'garage-orbit', 25, role='footer')
    label('查看车辆', width*.52, 910, 20, WHITE)
    button('返回赛事', width-170, 880, 140, 42, 'garage-back', role='footer')
    panel.select(panel.primary)


def style(panel):
    for index, button in enumerate(panel.buttons):
        role = panel.garage_roles[index]
        disabled, focused = button['state'] == DGG.DISABLED, index == panel.selected
        transparent = role in ('tab', 'tab-active', 'footer', 'quiet', 'event-card')
        color = ((1, .93, .90, 1) if role == 'category-active' else (.97, .97, .98, 1))
        if role == 'primary':
            color = (.78, .80, .83, 1) if disabled else ORANGE
        elif role == 'secondary':
            color = (.18, .22, .28, .95) if focused else (.04, .055, .075, .96)
        elif transparent:
            color = (1, 1, 1, .12) if focused else (0, 0, 0, 0)
        elif focused:
            color = (1, .87, .80, 1)
        button['geom_color'] = color
        button['text_fg'] = (GRAY if disabled else WHITE if role in ('primary', 'secondary', 'tab', 'tab-active', 'footer') else INK)
