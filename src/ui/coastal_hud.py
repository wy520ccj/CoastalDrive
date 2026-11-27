"""滨海巡游与计时遥测 HUD（设计 40 轻透浮动布局 + 落日琥珀金点缀）；只消费权威快照，零逐帧分配。"""

from direct.gui.DirectGui import DirectFrame, OnscreenText
from panda3d.core import TextNode

from audio.music import STATIONS
from coastal_medals import driving_goal
from driving_modes import DrivingMode
from race import GameMode
from ui import theme
from ui.lab_widgets import rounded_panel
from ui.race_feedback import energy_segment, energy_segment_delta, sector_times

UNIT = 2 / 941
WHITE = theme.WHITE
SOFT = (0.78, 0.83, 0.88, 1)
DARK = (0.045, 0.062, 0.088, 0.58)
ORANGE = theme.AMBER
GREEN = theme.PINE
GOLD = theme.AMBER
WARNING = (1, .48, .34, 1)


class CoastalDrivingHUD:
    def __init__(self, parent, body_font, number_font, regular_font):
        self.root = parent.attachNewNode('coastal-driving-hud')
        self.root.setScale(UNIT)
        self.body_font, self.number_font = body_font, number_font
        self.regular = regular_font
        self.widgets = []

        # ── 左上角轻透黑曜石赛事卡（沿用设计 40 通透质感，无厚重框线）──
        self.status = self.panel(360, 276)
        self.bar(self.status, 6, 12, 4, 32, ORANGE)
        self.title = self.label(self.status, '', 22, 38, 26, bold=True)
        self.timer = self.label(self.status, '', 22, 100, 54, number=True)
        self.checkpoints = self.label(self.status, '', 22, 134, 20, SOFT)
        self.progress = [self.bar(self.status, 22+i*82, 155, 70, 7, SOFT) for i in range(4)]
        self.progress_insets = [self.bar(segment, 2, 2, 66, 3, (*DARK[:3], 1)) for segment in self.progress]
        self.chase_bars = [self.bar(self.status, 22+i*65, 155, 57, 7, SOFT) for i in range(5)]
        for bar in self.chase_bars:
            bar.hide()
        self.sector = self.label(self.status, '', 22, 194, 20)
        self.cumulative = self.label(self.status, '', 22, 222, 20)
        self.goal = self.label(self.status, '', 22, 260, 21, GOLD)
        self.timed_widgets = (self.timer, self.checkpoints, self.sector, self.cumulative,
                              self.goal, *self.progress)

        self.notice_frame = self.panel(450, 70, color=(0.045, 0.062, 0.088, 0.66))
        self.bar(self.notice_frame, 6, 10, 4, 28, ORANGE)
        self.notice = self.label(self.notice_frame, '', 20, 28, 19)
        self.notice.textNode.setWordwrap(416/19)

        # ── 左下角轻透键位与电台条 ──
        self.help_frame = self.panel(510, 104, color=(0.045, 0.062, 0.088, 0.28))
        self.primary_keys = self.label(self.help_frame, '', 16, 28, 19)
        self.secondary_keys = self.label(self.help_frame, '', 16, 56, 18, SOFT)
        self.radio = [self.label(self.help_frame, name, 16, 86, 17, theme.STEEL_TEXT, mutable=False)
                      for name in STATIONS]

        # ── 右下角无底盒悬浮数字遥测（回归设计 40 通透质感，绝不遮挡路面）──
        self.instruments = self.panel(315, 160, color=(0, 0, 0, 0))
        self.speed = self.label(self.instruments, '000', 10, 91, 78, number=True)
        self.speed_unit_label = self.label(self.instruments, 'km/h', 183, 87, 21, SOFT, mutable=True)
        rounded_panel(self.instruments, 'gear-pill', (252, 310, -81, -38), ORANGE, 5)
        self.gear = OnscreenText(parent=self.instruments, text='', font=self.number_font,
                                 fg=theme.INK, pos=(281, -70), scale=27,
                                 align=TextNode.ACenter, mayChange=True)
        self.widgets.append(self.gear)
        self.rpm = self.label(self.instruments, '', 309, 111, 16, SOFT, number=True, right=True)
        self.segments = [self.bar(self.instruments, 12+i*13.5, 122, 11, 9, SOFT) for i in range(22)]
        self.assists = [self.label(self.instruments, text, 14+i*72, 153, 17, SOFT, bold=True)
                        for i, text in enumerate(('ABS', 'TCS', 'ESC'))]
        self.assist_lights = [self.bar(self.instruments, 14+i*72, 158, 28, 2.5, SOFT) for i in range(3)]

        self._timed = self._notice_text = None
        self._station = -1
        self._rpm_active = self._assists = self._progress = None
        self._feedback_colors = self._notice_color = None
        self._challenge_active = self._chase_active = False
        self._speed_unit = 'kmh'
        self._show_key_hints = True
        self._key_bindings = None
        self.root.hide()

    def configure(self, *, speed_unit=None, show_key_hints=None, key_bindings=None):
        if speed_unit is not None:
            self._speed_unit = speed_unit
            self.text(self.speed_unit_label, 'mph' if speed_unit == 'mph' else 'km/h')
        if show_key_hints is not None:
            self._show_key_hints = bool(show_key_hints)
            self.help_frame.show() if self._show_key_hints else self.help_frame.hide()
        if key_bindings is not None:
            self._key_bindings = dict(key_bindings)

    def panel(self, width, height, *, color=DARK):
        item = DirectFrame(parent=self.root, frameSize=(0, width, -height, 0), frameColor=color)
        self.widgets.append(item)
        return item

    def label(self, parent, text, x, y, size, color=WHITE, *, number=False, bold=False,
              right=False, mutable=True):
        item = OnscreenText(parent=parent, text=text,
            font=self.number_font if number else self.body_font if bold else self.regular,
            fg=color, pos=(x, -y), scale=size,
            align=TextNode.ARight if right else TextNode.ALeft, mayChange=mutable,
            shadow=(0, 0, 0, .72), shadowOffset=(.03, .03))
        self.widgets.append(item)
        return item

    def bar(self, parent, x, y, width, height, color):
        item = DirectFrame(parent=parent, frameSize=(0, width, -height, 0),
                           pos=(x, 0, -y), frameColor=color)
        self.widgets.append(item)
        return item

    @staticmethod
    def text(widget, value):
        if widget.getText() != value:
            widget.setText(value)

    def resize(self, aspect):
        left, right = -aspect/UNIT+36, aspect/UNIT-36
        self.status.setPos(left, 0, 941/2-40)
        self.notice_frame.setPos(left, 0, self.status.getZ()-(249 if self._chase_active else
                                  312 if self._challenge_active else 288 if self._timed else 60))
        self.help_frame.setPos(left, 0, -941/2+36+(80 if self._station is None else 104))
        self.instruments.setPos(right-315, 0, -941/2+36+160)

    def update(self, player, race, *, countdown, notice, driving_mode, station):
        if self._challenge_active:
            self._challenge_active, self._timed = False, None
            self._chase_active = False
            for bar in self.chase_bars:
                bar.hide()
            self.sector.setScale(20)
            self.cumulative.setScale(20)
            self.goal.setScale(21)
            self._feedback_colors = None
            self.notice.textNode.setWordwrap(416/19)
            self._notice_text = None
        timed = race.mode == GameMode.TIME_TRIAL
        if timed != self._timed:
            self._timed = timed
            self.status['frameSize'] = (0, 360, -276 if timed else -48, 0)
            for widget in self.timed_widgets:
                widget.show() if timed else widget.hide()
            self.notice_frame.setZ(self.status.getZ()-(288 if timed else 60))
        self.text(self.title, '滨海计时' if timed else '滨海 · 自由驾驶')
        if timed:
            centiseconds = int(race.elapsed*100)
            minutes, seconds = divmod(centiseconds, 6000)
            self.text(self.timer, f'{minutes:02}:{seconds/100:05.2f}')
            target = '终点' if race.checkpoints == 4 else f'下一处 {race.next_checkpoint}'
            self.text(self.checkpoints, f'检查点 {race.checkpoints} / 4 · {target}')
            if race.checkpoints != self._progress:
                for index, segment in enumerate(self.progress):
                    segment['frameColor'] = ORANGE if index < race.checkpoints else WHITE if index == race.checkpoints else (0.45, 0.50, 0.58, 0.55)
                    self.progress_insets[index].show() if index == race.checkpoints else self.progress_insets[index].hide()
                self._progress = race.checkpoints
            if not race.splits:
                sector = '分段 —'
                cumulative = '不参与最佳比较' if race.invalidated else '通过首个检查点后显示'
                colors = (SOFT, WARNING if race.invalidated else SOFT)
            else:
                seconds = sector_times(race.splits)[-1]
                sector = f'第{len(race.splits)}段 {seconds:.3f} s'
                cumulative = '不参与最佳比较' if race.invalidated else '暂无同配置最佳分段'
                colors = (WHITE, WARNING if race.invalidated else SOFT)
                if race.reference_splits and not race.invalidated:
                    index = len(race.splits)-1
                    delta = seconds-sector_times(race.reference_splits)[index]
                    total = race.splits[-1]-race.reference_splits[index]
                    sector, cumulative = f'本段 Δ {delta:+.3f} s', f'累计差 {total:+.3f} s'
                    colors = tuple(GREEN if value < 0 else GOLD if value > 0 else WHITE for value in (delta, total))
            self.text(self.sector, sector)
            self.text(self.cumulative, cumulative)
            self.text(self.goal, f'圈速无效：{race.invalid_reason}' if race.invalidated else driving_goal(race).splitlines()[-1])
            feedback_colors = (*colors, WARNING if race.invalidated else GOLD)
            if feedback_colors != self._feedback_colors:
                for widget, color in zip((self.sector, self.cumulative, self.goal), feedback_colors):
                    widget.setFg(color)
                self._feedback_colors = feedback_colors
        messages = (countdown, notice,
                    race.score_notice if timed else '', race.ghost_notice if timed else '')
        message = ' · '.join(value for value in messages if value)
        if message != self._notice_text:
            self._notice_text = message
            self.text(self.notice, message)
            lines = self.notice.textNode.getWordwrappedText().count('\n')+1
            self.notice_frame['frameSize'] = (0, 450, -max(48, 24*lines+22), 0)
            self.notice_frame.show() if message else self.notice_frame.hide()
        notice_color = WARNING if timed and race.invalidated else WHITE
        if notice_color != self._notice_color:
            self.notice.setFg(notice_color)
            self._notice_color = notice_color
        self.update_instruments(player, driving_mode, station)

    def update_challenge(self, player, status, *, countdown, notice, driving_mode, station, warning=False,
                         split_label='道路门', invalid_reason='', automatic=False, automatic_splits=()):
        chase = status.chase is not None
        if not self._challenge_active or chase != self._chase_active:
            self._challenge_active, self._timed = True, True
            self._chase_active = chase
            self.status['frameSize'] = (0, 360, -238 if chase else -300, 0)
            for widget in self.timed_widgets:
                widget.show()
            for widget in (self.goal, *self.progress):
                widget.hide() if chase else widget.show()
            for bar in self.chase_bars:
                bar.hide()
            self.sector.setScale(23)
            self.cumulative.setScale(17)
            self.goal.setScale(18)
            self.notice_frame.setZ(self.status.getZ()-(249 if chase else 312))
            self.notice.textNode.setWordwrap(326/19)
            self._progress = self._feedback_colors = None
            self._notice_text = None
        self.text(self.title, status.name)
        practice = status.practice_sector
        elapsed = status.seconds
        timed = practice is None or len(status.splits) >= practice
        if timed and practice:
            elapsed -= status.splits[practice-1].seconds
        minutes, seconds = divmod(int(elapsed*100), 6000)
        self.text(self.timer, f'{minutes:02}:{seconds/100:05.2f}' if timed else '—')
        if chase:
            self.update_chase_times(status)
            message = ' · '.join(value for value in (countdown, notice, invalid_reason) if value)
            if message != self._notice_text:
                self._notice_text = message
                self.text(self.notice, message)
                lines = self.notice.textNode.getWordwrappedText().count('\n')+1
                self.notice_frame['frameSize'] = (0, 360, -max(48, 24*lines+22), 0)
                self.notice_frame.show() if message else self.notice_frame.hide()
            self.notice.setFg(WARNING if warning or invalid_reason else WHITE)
            self._notice_color = WARNING if warning or invalid_reason else WHITE
            self.update_instruments(player, driving_mode, station, automatic=automatic)
            return
        self.text(self.checkpoints, f'{status.progress_m:.0f} / {status.distance_m:.0f} m'
                  f' · {split_label} {len(status.splits)} / {status.gate_count}')
        progress = int(len(status.splits)*len(self.progress)/status.gate_count)
        if progress != self._progress:
            for index, segment in enumerate(self.progress):
                segment['frameColor'] = ORANGE if index < progress else (0.45, 0.50, 0.58, 0.55)
                self.progress_insets[index].hide()
            self._progress = progress
        average = '—' if status.consumption is None else f'{status.consumption:.1f}'
        self.text(self.sector, f'赛段油耗  {average} L/100km')
        target = None
        if invalid_reason:
            goal, detail = '本圈无效', invalid_reason
        elif automatic:
            goal, detail = '自动试车 · 不计成绩', '继续采集用时与油耗'
        elif status.litres is None:
            goal, detail = '燃油观测缺失', '本次不计正式成绩'
        elif status.cost > status.budget:
            goal, detail = f'试验 · 超出预算 {status.cost-status.budget}', '本次不计正式成绩'
        elif not status.targets:
            goal, detail = '联合目标标定中', '当前为试验驾驶，暂不授奖'
        else:
            # 已花掉的时间和油量不能收回，显示仍可争取的最高档。
            target = next((item for item in reversed(status.targets) if status.seconds <= item.seconds
                           and status.litres <= item.consumption*status.distance_m/100_000), None)
            if target is None:
                goal, detail = '已超出铜牌目标', '继续驶向终点'
            else:
                title = '试行'+target.medal+'牌' if status.provisional else target.medal+'牌目标'
                goal = f'{title}  ≤{target.seconds:.1f}s · ≤{target.consumption:.1f} L/100km'
                allowance = target.consumption*status.distance_m/100_000-status.litres
                detail = f'余时 {target.seconds-status.seconds:.1f}s · 油量额度 {allowance:.3f}L'
        self.text(self.cumulative, goal)
        self.text(self.goal, detail)
        oil_color = (WARNING if target is not None and status.consumption is not None
                     and status.consumption > target.consumption else WHITE)
        colors = (oil_color, WARNING, WARNING) if invalid_reason else (oil_color, SOFT, GOLD)
        if colors != self._feedback_colors:
            for widget, color in zip((self.sector, self.cumulative, self.goal), colors):
                widget.setFg(color)
            self._feedback_colors = colors
        feedback = ''
        index = len(status.splits)-1
        reference = automatic_splits if automatic else status.reference_splits
        if not invalid_reason and 0 <= index < len(reference):
            delta = energy_segment_delta(energy_segment(status.splits, index), reference, index)
            if delta is not None:
                name = '本段较对照' if automatic else '本段'
                feedback = f'{name} {delta[0]:+.1f}s · 油耗 {delta[1]:+.1f} L/100km'
        message = ' · '.join(value for value in (countdown, notice, feedback) if value)
        if message != self._notice_text:
            self._notice_text = message
            self.text(self.notice, message)
            lines = self.notice.textNode.getWordwrappedText().count('\n')+1
            self.notice_frame['frameSize'] = (0, 360, -max(48, 24*lines+22), 0)
            self.notice_frame.show() if message else self.notice_frame.hide()
        notice_color = WARNING if warning else WHITE
        if notice_color != self._notice_color:
            self.notice.setFg(notice_color)
            self._notice_color = notice_color
        self.update_instruments(player, driving_mode, station, automatic=automatic)

    def update_chase_times(self, status):
        passed, count = len(status.splits), status.gate_count
        practice = status.practice_sector
        self.text(self.checkpoints, f'计时门 {passed} / {count}' if practice is None
                  else f'单段练习 · {status.chase.labels[practice]}')
        if (passed, count) != self._progress:
            for index, bar in enumerate(self.chase_bars):
                if index < count:
                    spacing = 326/count
                    bar.setX(22+index*spacing)
                    bar['frameSize'] = (0, spacing-7, -7, 0)
                    bar['frameColor'] = ORANGE if index < passed else (0.45, 0.50, 0.58, 0.55)
                    bar.show()
                else:
                    bar.hide()
            self._progress = passed, count
        if practice is not None:
            text = '本段计时中' if passed >= practice else '前往练习段起点'
            color = WHITE
        elif passed:
            delta = status.splits[-1].seconds-status.reference_splits[passed-1].seconds
            text = ('与参考持平' if abs(delta) < .005 else
                    f'累计落后 {delta:+.2f} s' if delta > 0 else f'累计领先 {abs(delta):.2f} s')
            color = WHITE if abs(delta) < .005 else WARNING if delta > 0 else GREEN
        else:
            text = f'全程参考 {status.reference_splits[-1].seconds:.3f} s'
            color = WHITE
        self.text(self.sector, text)
        self.sector.setFg(color)
        next_gate = status.reference_splits[passed].distance_m if passed < count else status.distance_m
        self.text(self.cumulative, f'下一门 · {max(0., next_gate-status.progress_m):.0f} m' if passed < count else '全部计时门已通过')
        self.cumulative.setFg(WHITE)

    def update_instruments(self, player, driving_mode, station, *, automatic=False):
        from settings import KEY_PRESETS, key_label

        simulation = driving_mode == DrivingMode.SIMULATION
        keys = KEY_PRESETS['wasd'] if self._key_bindings is None else self._key_bindings
        t, b = key_label(keys['throttle']), key_label(keys['brake'])
        l, r = key_label(keys['steer_left']), key_label(keys['steer_right'])
        cam, rst = key_label(keys['camera']), key_label(keys['reset'])
        rad, mute = key_label(keys['radio_next']), key_label(keys['radio_mute'])
        primary_keys = (f'{cam} 视角   Esc 暂停' if automatic else f'{t} 油门   {b} 刹车   {l}/{r} 转向' if simulation else
                        f'{t} 油门   {b} 刹车·倒车   {l}/{r} 转向')
        secondary_keys = (f'{rst} 复位  {rad} 电台  {mute} 静音' if automatic else
                          ('Q 倒挡  E 前进  ' if simulation else '') + f'{cam} 视角  {rst} 复位  {rad} 电台  {mute} 静音  Esc 暂停')
        self.text(self.primary_keys, primary_keys)
        self.text(self.secondary_keys, secondary_keys)
        if station != self._station:
            self._station = station
            for index, label in enumerate(self.radio):
                label.show() if index == station else label.hide()
            height = 80 if station is None else 104
            self.help_frame['frameSize'] = (0, 620, -height, 0)
            self.help_frame.setZ(-941/2+36+height)
        factor = 2.23693629 if self._speed_unit == 'mph' else 3.6
        self.text(self.speed, f'{abs(player.speed)*factor:03.0f}')
        self.text(self.gear, 'R' if player.gear < 0 else 'N' if player.gear == 0 else f'D{player.gear}')
        self.text(self.rpm, f'{player.rpm:.0f} rpm')
        active = round(max(0., min(1., player.rpm/7000))*len(self.segments))
        if active != self._rpm_active:
            for index, segment in enumerate(self.segments):
                if index < active:
                    seg_col = (0.94, 0.36, 0.28, 1) if index >= 19 else ORANGE if index >= 12 else WHITE
                else:
                    seg_col = (0.12, 0.16, 0.22, 0.50)
                segment['frameColor'] = seg_col
            self._rpm_active = active
        assists = ((player.abs_enabled, any(brake.abs_active for brake in player.brake_states)),
                   (player.tcs_enabled, player.traction_state.active),
                   (player.esc_enabled, player.stability_state.active))
        if assists != self._assists:
            for label, light, (enabled, intervening) in zip(self.assists, self.assist_lights, assists):
                color = GREEN if intervening else SOFT if enabled else (0.36, 0.42, 0.50, 0.72)
                label.setFg(color)
                light['frameColor'] = color
            self._assists = assists

    def destroy(self):
        for widget in reversed(self.widgets):
            widget.destroy()
        self.root.removeNode()
