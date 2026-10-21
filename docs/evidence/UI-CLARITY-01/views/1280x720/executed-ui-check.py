"""复用真实归档记录采集改版页面；不新开物理试验，不改用户数据。"""

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]

from panda3d.core import Filename
from road_review_check import archived_records

from lab_application import VehicleLab
from lab_records import load_record
from road_comparison import RoadResults


def check(output, size, expert_only=False):
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, output/'executed-tool.py')
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    inputs = {}

    def restore(source, destination):
        for path in source.rglob('*'):
            if not path.is_file():
                continue
            inputs[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        shutil.copytree(source, destination)
        for archive in destination.rglob('*.gz'):
            archive.with_suffix('').write_bytes(gzip.decompress(archive.read_bytes()))
        # 旧证据省略了冗余车辆文件，按其完整原配置在隔离副本中恢复。
        for experiment in destination.rglob('experiment.json'):
            vehicle = experiment.with_name('vehicle.json')
            if not vehicle.exists():
                document = json.loads(experiment.read_text(encoding='utf-8'))
                vehicle.write_text(json.dumps(document['vehicle_config']), encoding='utf-8')

    restore(ROOT/'docs/evidence/DESIGN-SCHEMES-01/normal/schemes', output/'schemes')
    restore(ROOT/'docs/evidence/WORKSHOP-INSIGHTS-01/normal/reports', output/'records')
    restore(ROOT/'docs/evidence/WORKSHOP-INSIGHTS-01/normal/raw', output/'raw')
    app = VehicleLab(offscreen=True, render_size=tuple(size), output=output/'exports', scheme_root=output/'schemes')
    app.engine.taskMgr.remove('lab-update')
    images = []

    def capture(name):
        app.resize()
        for _ in range(5):
            app.engine.taskMgr.step()
        app.engine.graphicsEngine.syncFrame()
        assert app.engine.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        images.append(name)
        assert app.run_state is None

    try:
        capture('01-expert-ready')
        if not expert_only:
            panel = app.workshop
            for topic, name in ((0, 'brake'), (1, 'corner')):
                panel.set_topic(topic)
                panel.show()
                capture('02-'+name+'-ready')
                panel.toggle_details()
                capture('03-'+name+'-rules')
                app.escape()
                assert not panel.root.isHidden() and panel.details.isHidden()
            for name in ('brake-gold', 'brake-over', 'corner-gold', 'corner-sharp'):
                folder = output/'records'/name
                data = json.loads((folder/'insights.json').read_text(encoding='utf-8'))
                panel.set_topic(data['topic'])
                panel.share.set(data['selection'][0], fCommand=0)
                panel.brakes.set(int(data['selection'][1]), fCommand=0)
                if data['topic']:
                    panel.lower_cg.set(int(data['selection'][2]), fCommand=0)
                baseline = folder/'baseline-A' if name.endswith('gold') else output/'raw'/('corner-base' if data['topic'] else 'brake-base')
                candidate = folder if name.endswith('gold') else output/'raw'/name
                panel.baseline = load_record(baseline)
                panel.candidate = load_record(candidate)
                panel.result = panel.evaluate_records()
                panel.refresh_budget()
                panel.present_result()
                capture('04-'+name+'-result')
                panel.show_insights()
                capture('05-'+name+'-insight')
                if name == 'brake-gold':
                    panel.insights.toggle_details()
                    capture('06-result-details')
                    app.escape()
                    assert not panel.insights.root.isHidden()
                panel.insights.hide()
            panel.hide()
            app.schemes.show()
            app.schemes.move(1, 1)
            capture('07-schemes')
            app.schemes.toggle_save()
            capture('08-save-name')
            app.escape()
            app.schemes.toggle_details()
            capture('09-scheme-details')
            app.escape()
            virtual = app.schemes.virtual_driver
            virtual.show()
            virtual.comparison = RoadResults(archived_records('normal'), 'complete')
            virtual.present()
            capture('10-road-result')
            virtual.toggle_details()
            capture('11-road-details')
            app.escape()
            virtual.hide()
            app.schemes.hide()
        assert app.import_record(output/'records'/'brake-gold')
        app.baseline = load_record(output/'records'/'brake-gold'/'baseline-A')
        app.present_summary(app.record.metadata['summary'])
        app.refresh_plots()
        capture('12-expert-record')
        assert app.run_state is None and app.workspace_vehicle is None
        assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in inputs.items())
        result = {'passed': True, 'size': size, 'images': images, 'new_physics_ticks': 0, 'expert_only': expert_only,
                  'basis': '归档真实制动/弯道A/B、方案与道路记录静态复载；条件/指标不伪造。',
                  'human_gate': 'pending',
                  'inputs': {str(path.relative_to(ROOT)): digest for path, digest in inputs.items()}}
        (output/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'passed': True, 'images': len(images), 'new_physics_ticks': 0}
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    parser.add_argument('--expert-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.expert_only)))
