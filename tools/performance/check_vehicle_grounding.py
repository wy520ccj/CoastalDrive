"""正常山脊120m原车辆，核对显示胎面、轮心与实际路网，并保存原镜头/侧面。"""

import argparse
import faulthandler
import json
import multiprocessing
import sys
from pathlib import Path

from panda3d.core import Filename, GeomVertexReader, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/environment'))

import check_interactive_local_drive
from check_interactive_local_drive import DrivingProbe, check


def inspect(app):
    output = app.probe_output
    state = app.grounding_state
    road = app.session.simulation.road
    pose = road.sample_lateral(road.locate(state.player)[0], 0)
    config = app.session.vehicle_config
    wheels = []
    print('GROUNDING inspect begin', flush=True)
    for node, wheel in zip(app.scene.wheels, state.player.wheels, strict=True):
        points = []
        distance, _ = road.locate(type('Position', (), {'position': wheel.position})())
        center_ground = road.sample_lateral(distance, 0.)
        from math import cos, radians, sin, tan

        slope = tan(radians(center_ground.grade))
        heading = radians(center_ground.heading)
        for part in node.findAllMatches('**/+GeomNode'):
            matrix = part.getMat(app.scene.render)
            for i in range(part.node().getNumGeoms()):
                reader = GeomVertexReader(part.node().getGeom(i).getVertexData(), 'vertex')
                while not reader.isAtEnd():
                    point = matrix.xformPoint(reader.getData3f())
                    # 真实显示车轮的每个顶点相对原道路采样，不用外廓盒下缘冒充胎面。
                    # 同一轮胎周围用该处道路切平面，误差与完整路网另记。
                    tangent_offset = -(point.x-center_ground.x)*sin(heading)+(point.y-center_ground.y)*cos(heading)
                    points.append(point.z-center_ground.z-slope*tangent_offset)
                # 读取器持有顶点数组的流水线读锁，出帧前必须释放。
                del reader
        wheels.append({'name': node.getName(), 'hub': list(wheel.position),
                       'tread_to_road_minimum_m': min(points),
                       'display_position_error_m': (node.getPos()-Vec3(*wheel.position)).length()})
        print('GROUNDING wheel', wheels[-1], flush=True)

    position = Vec3(*state.player.position)
    original_camera = app.camera.getTransform()
    images = []
    for label, camera in (
        ('follow', None), ('side', position+Vec3(-7, 0, .7)),
        ('rear-low', position+Vec3(0, -7, .5))):
        if camera is not None:
            app.camera.setPos(camera)
            app.camera.lookAt(position)
        for bias in (.0007, 0.):
            print('GROUNDING capture', label, bias, flush=True)
            app.pipeline.shadow_bias = bias
            for _ in range(10):
                # 通过正常igLoop出帧；不能在同一任务里反复手动推进/Draw流水线。
                yield
            app.graphicsEngine.syncFrame()
            name = label+'-bias-'+str(bias)+'.png'
            app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/name)))
            images.append(name)
    app.camera.setTransform(original_camera)
    app.pipeline.shadow_bias = .0007
    report = {'scope': '正常入口原GT，独立120Hz驶到山脊120m后暂停；额外镜位/阴影bias仅诊断',
              'vehicle': app.vehicle_model_id, 'radius': config.wheel_radius,
              'body_position': list(position), 'body_pitch': state.player.pitch,
              'road_grade': pose.grade, 'wheel_geometry': wheels, 'images': images}
    (output/'grounding.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


class GroundingProbe(DrivingProbe):
    def apply_scene(self, state, camera_dt):
        super().apply_scene(state, camera_dt)
        self.grounding_state = state

    def probe_frame(self, task):
        if self.inspection is not None:
            try:
                next(self.inspection)
            except StopIteration:
                faulthandler.cancel_dump_traceback_later()
                self.userExit()
                return task.done
            return task.cont
        if self.probe_driver and self.session.simulation.road.locate(self.session.current.player)[0] >= 120:
            self.session.pause()
            print('GROUNDING paused', flush=True)
            self.taskMgr.remove('drive-update')
            self.inspection = inspect(self)
            return task.cont
        return super().probe_frame(task)

    inspection = None


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    faulthandler.enable()
    faulthandler.dump_traceback_later(45, repeat=True)
    check_interactive_local_drive.DrivingProbe = GroundingProbe
    # 该检查刻意不运行450m，不借用通用完成标记。
    try:
        check(args.output.resolve(), False, False)
    except RuntimeError:
        if not (args.output/'grounding.json').is_file():
            raise
