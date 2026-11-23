"""相机移动不能无限生成材质状态，也不能改写在途绘制帧的数据。"""

from types import SimpleNamespace

import pytest
from panda3d.core import ClockObject, GraphicsThreadingModel, NodePath, Vec3

import rendering
from rendering import ScenePipeline


@pytest.mark.parametrize('model', ['', '/Draw', 'Cull/Draw'])
def test_camera_input_reuses_states_and_preserves_inflight_frames(monkeypatch, model):
    engine = SimpleNamespace(getThreadingModel=lambda: GraphicsThreadingModel(model))
    monkeypatch.setattr(rendering, 'GraphicsEngine', SimpleNamespace(getGlobalPtr=lambda: engine))
    root = NodePath('render')
    camera = root.attachNewNode('camera')
    updates = []

    def initialize(pipeline, **kwargs):
        pipeline.render_node = root
        pipeline.camera_node = camera

    def original_update(pipeline, task):
        updates.append(tuple(camera.getPos(root)))
        root.setShaderInput('camera_world_position', camera.getPos(root))
        return 'continue-original-task'

    monkeypatch.setattr(rendering.Pipeline, '__init__', initialize)
    monkeypatch.setattr(rendering.Pipeline, '_update', original_update)
    clock = ClockObject()
    monkeypatch.setattr(rendering, 'ClockObject', SimpleNamespace(getGlobalClock=lambda: clock))
    pipeline = ScenePipeline()
    depth = GraphicsThreadingModel(model).getDrawStage()
    states, positions = set(), {}
    for frame in range(90):
        clock.setFrameCount(frame)
        position = Vec3(frame*.25, frame*1.5, -frame*.5)
        camera.setPos(position)
        assert pipeline._update(None) == 'continue-original-task'
        states.add(root.getState())
        positions[frame] = position
        for queued in range(max(0, frame-depth), frame+1):
            assert pipeline._camera_positions[queued % (depth+1)][0] == positions[queued]
    assert len(updates) == 90
    assert len(states) == depth+1


def test_camera_input_accepts_double_precision_point(monkeypatch):
    from panda3d.core import LPoint3d, LVecBase3f

    engine = SimpleNamespace(getThreadingModel=lambda: GraphicsThreadingModel('/Draw'))
    monkeypatch.setattr(rendering, 'GraphicsEngine', SimpleNamespace(getGlobalPtr=lambda: engine))
    root = NodePath('render')
    camera = SimpleNamespace(getPos=lambda _node: LPoint3d(1.5, -2.5, 3.5))
    monkeypatch.setattr(rendering.Pipeline, '__init__',
                        lambda self, **kwargs: (setattr(self, 'render_node', root), setattr(self, 'camera_node', camera)))
    monkeypatch.setattr(rendering.Pipeline, '_update', lambda self, task: task.DS_cont)
    pipeline = ScenePipeline()
    pipeline.sync_frame()
    stored = pipeline._camera_positions[ClockObject.getGlobalClock().getFrameCount() % len(pipeline._camera_positions)][0]
    assert stored == LVecBase3f(1.5, -2.5, 3.5)
