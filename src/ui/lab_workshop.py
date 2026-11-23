"""固定参考工坊复用预算参数页与A/B结果页，不再安装离散配方。"""

import json
from dataclasses import asdict, replace
from datetime import UTC, datetime

from direct.gui import DirectGuiGlobals as DGG

from challenge_build import ADJUSTMENTS, BuildDraft
from challenge_plans import ChallengePlans
from lab_records import export_record
from paths import user_data
from ui.career import CareerPanel
from ui.challenge_layout import ENTRY_ACTIONS, read_build, read_value, step_value
from ui.lab_feedback import error_text
from ui.workshop_vehicle import WorkshopVehicle
from vehicle_schemes import checked_challenge
from vehicle_workspace import WorkspaceVehicle
from workshop_budget import REFERENCE_BY_ID, REFERENCE_CHALLENGES, describe, evaluate
from workshop_cornering import CHALLENGE_ID as LEGACY_CORNERING


class WorkshopPanel:
    def __init__(self, app):
        self.app = app
        self.topic, self.tab, self.phase = 0, 1, None
        self.baseline = self.candidate = self.result = None
        self.measured_build = None
        self.historical = None
        self.plans = ChallengePlans(user_data()/'challenge-plans.json')
        self.drafts, self.plan_notices = [], []
        for spec in REFERENCE_CHALLENGES:
            self.drafts.append(self.plans.load(spec))
            self.plan_notices.append(self.plans.notice)
        self.vehicle_view = WorkshopVehicle(app.engine) if app.owns_window else app.engine.workshop_vehicle
        self.editor = CareerPanel(app.root, app.font, self.vehicle_view, self.action, app.engine.loader)
        self.root = self.editor.root

    @property
    def spec(self):
        return REFERENCE_CHALLENGES[self.topic]

    @property
    def draft(self):
        return self.drafts[self.topic]

    def selected_config(self):
        return self.spec.configuration(self.draft)

    def selected_cost(self):
        return self.draft.cost

    def show_editor(self, notice=''):
        self.editor.show_challenge(None, self.spec, self.draft, self.tab, notice or self.plan_notices[self.topic])

    def show(self):
        app = self.app
        app.blur_entries()
        app.design_loop.hide()
        for panel in (app.advanced_panel, app.manual_panel, app.details_panel, app.record_menu,
                      app.parameter_help.root, app.engineering_panel.root):
            panel.hide()
        if app.run_state is not None and self.phase is None:
            app.run_state.paused = True
        if self.result is not None:
            self.present_result()
        else:
            self.show_editor('历史报告已恢复；预算改装需重新完成A/B。' if self.historical is not None else '')

    def hide(self):
        if self.phase is not None:
            self.cancel()
        self.editor.hide()
        self.vehicle_view.hide()

    def escape(self):
        self.cancel() if self.phase is not None else self.editor.key('escape')

    def key(self, key):
        if not self.root.isHidden():
            self.editor.key(key)

    def set_topic(self, topic):
        if type(topic) is not int or topic not in (0, 1):
            raise ValueError('未知工坊题目')
        if self.phase is not None:
            self.cancel()
        self.topic, self.tab = topic, 1
        self.result = self.measured_build = self.historical = None
        if not self.root.isHidden():
            self.show_editor()

    def action(self, action, value=None):
        if self.phase is not None:
            if action == 'challenge-back':
                self.cancel()
            return
        if self.editor.page == 'challenge' and action in ENTRY_ACTIONS:
            try:
                changed = read_build(self.editor, value if action == 'challenge-value' else None)
            except (ValueError, TypeError, OverflowError) as error:
                self.editor.challenge_readouts['notice'].setText(str(error))
                return False
            if changed != self.draft:
                self.drafts[self.topic] = changed
                self.result = self.historical = None
                self.editor.update_challenge(changed, self.plan_notices[self.topic])
        if action == 'challenge-commit':
            return True
        if action == 'reference-topic':
            self.set_topic(value)
        elif action == 'challenge-tab':
            self.tab = value
            self.show_editor()
        elif action in ('challenge-value', 'challenge-step'):
            key, raw = value
            try:
                number = (step_value(self.spec, self.draft, key, raw) if action == 'challenge-step'
                          else read_value(self.spec, self.draft, key, raw))
                changed = replace(self.draft, **{key: number})
                self.spec.configuration(changed)
            except (ValueError, TypeError, OverflowError) as error:
                self.editor.challenge_readouts['notice'].setText(str(error))
                return
            if changed != self.draft:
                self.drafts[self.topic] = changed
                self.result = self.historical = None
                self.editor.update_challenge(changed, self.plan_notices[self.topic])
        elif action == 'challenge-reset':
            self.drafts[self.topic] = (BuildDraft() if value is None else replace(self.draft,
                **{value: None if value in ADJUSTMENTS else 1.}))
            self.result = self.historical = None
            self.editor.update_challenge(self.draft)
        elif action == 'challenge-save':
            self.plans.save(self.spec, self.draft)
            self.plan_notices[self.topic] = self.plans.notice
            self.editor.update_challenge(self.draft, self.plans.notice)
        elif action == 'challenge-start':
            self.start()
        elif action == 'challenge-adjust':
            self.show_editor()
        elif action in ('challenge-back', 'challenge-lab'):
            self.hide()
        elif action == 'reference-export':
            self.export_interpretation()
        elif action == 'reference-drive':
            self.drive()

    def set_running(self, running):
        for widget in (*self.editor.challenge_entries.values(), *self.editor.challenge_sliders.values()):
            widget['state'] = DGG.DISABLED if running else DGG.NORMAL
        for button in self.editor.buttons:
            button['state'] = (DGG.NORMAL if not running or button['extraArgs'][0] == 'challenge-back'
                               else DGG.DISABLED)
            if button['extraArgs'][0] == 'challenge-back':
                button['text'] = '停止试验' if running else 'Esc 返回实验台'

    def begin_trial(self, config):
        app = self.app
        app.set_options(self.spec.options)
        app.engineered_config, app.engineered_vehicle_id = config, self.spec.design_id
        app.parameter_metadata = {'basis': self.spec.name+' · 固定原车A/B · 参考积分条件'}
        app.refresh_configuration_note()
        app.start_experiment()
        if app.run_state is None:
            raise RuntimeError('工坊试验初始化失败')

    def start(self):
        self.app.design_loop.hide()
        self.result = self.baseline = self.candidate = self.historical = None
        self.measured_build = self.draft
        self.show_editor()
        self.phase = 'A'
        self.set_running(True)
        try:
            self.begin_trial(self.spec.base_config)
        except (OSError, ArithmeticError, ValueError, RuntimeError) as error:
            self.cancel()
            self.show_error('挑战未开始', error)

    def show_error(self, action, error):
        self.app.show_error(action, error)
        self.app.notice.dismiss()
        message = action+'：'+error_text(error)
        self.present_result(message) if self.result is not None else self.show_editor(message)

    def cancel(self):
        if self.app.run_state is not None:
            self.app.run_state.paused = True
        self.phase = None
        self.result = None
        self.show_editor('已停止，原始曲线保留。')

    def evaluate_records(self):
        return evaluate(self.topic, self.baseline, self.candidate, self.measured_build)

    def update(self):
        self.editor.resize(self.app.engine.getAspectRatio())
        if self.phase is None:
            return
        self.set_running(True)
        run = self.app.run_state
        self.editor.challenge_readouts['notice'].setText(f'{self.phase} · {run.elapsed:.1f} / {self.spec.options.duration:g} s')
        if not run.done:
            return
        try:
            if run.reason != ('stopped' if self.topic == 0 else 'time_limit'):
                raise ValueError('试验未正常完成，本次不评价')
            if self.phase == 'A':
                self.baseline = self.app.active_record()
                self.app.baseline = self.baseline
                self.phase = 'B'
                self.begin_trial(self.spec.configuration(self.measured_build))
                return
            self.candidate = self.app.active_record()
            self.result = self.evaluate_records()
        except (OSError, ArithmeticError, ValueError, RuntimeError) as error:
            self.cancel()
            self.show_error('挑战未完成，记录保留', error)
            return
        self.phase = None
        self.present_result()

    def present_result(self, notice=''):
        data = describe(self.topic, self.baseline, self.candidate, self.measured_build)
        self.editor.show_reference_result(self.spec, self.measured_build, data, notice)

    def export_interpretation(self):
        if self.result is None or self.phase is not None:
            return None
        try:
            result = self.evaluate_records()
            folder = self.app.output/(datetime.now(UTC).strftime('%Y%m%d-%H%M%S-%f')+'-workshop-budget')
            report = export_record(self.candidate, folder, baseline=self.baseline)
            (folder/'challenge.json').write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                                           allow_nan=False), encoding='utf-8')
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.show_error('工坊报告未导出，原始记录保留', error)
            return None
        self.app.last_report = report
        self.present_result('报告已导出：'+folder.name)
        return report

    def drive(self):
        if self.result is None or not self.result['passed'] or self.phase is not None:
            return
        report = self.export_interpretation()
        if report is None:
            return
        try:
            result = self.evaluate_records()
            vehicle = WorkspaceVehicle(self.spec.design_id, self.spec.configuration(self.measured_build),
                self.candidate.metadata['parameter_metadata'], str(report), result)
            vehicle.save(self.app.workspace_path)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.show_error('挑战车辆未保存，结果保留', error)
            return
        self.app.workspace_vehicle = vehicle
        self.app.next_drive = True
        self.app.back_to_game()

    def capture(self):
        return {'version': 2, 'topic': self.topic, 'drafts': [asdict(draft) for draft in self.drafts],
                'tab': self.tab, 'baseline': self.baseline, 'candidate': self.candidate,
                'result': self.result, 'measured_build': self.measured_build, 'historical': self.historical,
                'visible': not self.root.isHidden(), 'page': self.editor.page}

    def restore(self, state):
        self.topic, self.tab = state['topic'], state.get('tab', 1)
        self.baseline, self.candidate = state['baseline'], state['candidate']
        self.result = self.measured_build = self.historical = None
        if state.get('version') == 2:
            self.drafts = [BuildDraft(**row) for row in state['drafts']]
            self.result, self.measured_build, self.historical = state['result'], state['measured_build'], state['historical']
        else:
            self.historical = state['result']
        if state.get('visible', False):
            self.show()

    def restore_saved(self, vehicle):
        receipt = vehicle.workshop_result
        if receipt is None or self.app.record is None or self.app.baseline is None:
            return
        try:
            actual = checked_challenge(receipt, self.app.baseline, self.app.record)
        except (ValueError, KeyError, TypeError) as error:
            self.show_error('工坊成绩与原始A/B不符，请重新试验', error)
            return
        self.baseline, self.candidate = self.app.baseline, self.app.record
        if receipt['challenge_id'] in REFERENCE_BY_ID:
            self.topic = REFERENCE_CHALLENGES.index(REFERENCE_BY_ID[receipt['challenge_id']])
            self.measured_build = BuildDraft(**receipt['build'])
            self.drafts[self.topic] = self.measured_build
            self.result, self.historical = actual, None
        else:
            self.topic = int(receipt['challenge_id'] == LEGACY_CORNERING)
            self.historical = actual
            self.result = self.measured_build = None

    def close(self):
        self.hide()
        self.editor.destroy()
        if self.app.owns_window:
            self.vehicle_view.close()
