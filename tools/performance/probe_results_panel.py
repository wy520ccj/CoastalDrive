"""测量真实结算面板首次创建；完成态夹具不代表实际跑圈或前台性能。"""

import argparse
import cProfile
import io
import json
import pstats
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=ROOT / 'src')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.source.resolve()))
    from panda3d.core import Filename, TextNode

    from application import CoastalDrive
    from race import GameMode
    from session import Phase

    app = CoastalDrive(smoke=True, output=args.output, render_size=(1920, 1080))
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        app.start_game(mode=GameMode.TIME_TRIAL)
        app.session.phase = Phase.DRIVING
        app.refresh_panel()
        # 先执行真实PBR任务以准备相机shader输入；不把初始化当结算开销。
        app.taskMgr.step()
        app.session.race.snapshot = replace(app.session.race.snapshot, finished=True,
                                           last_lap=87.123, best_lap=87.123)
        app.session.tick()
        frozen = app.session.current
        profiler = cProfile.Profile()
        profiler.enable()
        start = time.perf_counter()
        app.refresh_panel()
        panel_ms = (time.perf_counter() - start) * 1000
        profiler.disable()
        output = io.StringIO()
        pstats.Stats(profiler, stream=output).sort_stats('cumulative').print_stats(35)
        (args.output / 'profile.txt').write_text(output.getvalue(), encoding='utf-8')
        frames = []
        for _ in range(4):
            start = time.perf_counter()
            app.graphicsEngine.renderFrame()
            frames.append((time.perf_counter() - start) * 1000)
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(args.output / 'results.png')))
        reference = TextNode('original-line-measure')
        reference.setFont(app.ui_font)

        def original_lines(value, width, scale, maximum):
            lines = []
            for source in value.split('\n'):
                line = ''
                for char in source:
                    reference.setText(line + char)
                    if line and reference.getWidth() * scale > width:
                        lines.append(line)
                        line = char
                    else:
                        line += char
                lines.append(line)
            return '\n'.join(lines if maximum is None else lines[:maximum])

        wrapping_cases = 0
        for text in (app.panel_note.getText(), app.panel_detail.getText(),
                     '成绩保存失败：目录不可写，请检查 C:/CoastalDrive/data。\n重试 123.456 秒',
                     'AVATAR  Enter  TCS/ABS  无碰撞挑战\n\n', ''):
            for width in (.01, .12, .99, 1.36, 1.37):
                for scale in (.041, .058):
                    for maximum in (None, 2):
                        assert app.fit_lines(text, width, scale, maximum) == original_lines(text, width, scale, maximum)
                        wrapping_cases += 1
        report = {
            'kind': 'offscreen completed-race fixture; not a performance gate',
            'source': str(args.source.resolve()), 'panel_ms_with_profile': panel_ms,
            'first_render_frames_ms': frames,
            'title': app.panel_title.getText(), 'note': app.panel_note.getText(),
            'detail': app.panel_detail.getText(),
            'buttons': [button['text'] for button in app.buttons if not button.isHidden()],
            'physics_frozen': frozen == app.session.current,
            'wrapping_identical_cases': wrapping_cases,
        }
        (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        app.close_game()


if __name__ == '__main__':
    main()
