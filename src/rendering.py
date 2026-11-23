"""渲染线程分档保存相机输入，复用静态景物的组合状态。"""

from types import SimpleNamespace

from panda3d.core import ClockObject, GraphicsEngine, LVecBase3f, PTALVecBase3f, ShaderInput
from simplepbr import Pipeline

_SYNC_TASK = SimpleNamespace(DS_cont=1)


class ScenePipeline(Pipeline):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 每个在途帧持有独立存储；Draw完成前不覆盖它正在读取的位置。
        count = GraphicsEngine.getGlobalPtr().getThreadingModel().getDrawStage() + 1
        self._camera_positions = tuple(PTALVecBase3f.emptyArray(1) for _ in range(count))
        self._camera_inputs = tuple(ShaderInput('camera_world_position', value)
                                    for value in self._camera_positions)

    def sync_frame(self):
        """在主循环外部主动出帧前刷新相机与光照输入，避免着色器缺少 uniform。"""
        self._update(_SYNC_TASK)

    def _update(self, task):
        result = super()._update(task)
        index = ClockObject.getGlobalClock().getFrameCount() % len(self._camera_positions)
        pos = self.camera_node.getPos(self.render_node)
        # 双精度运行库返回 LPoint3d；着色器输入为单精度 vec3，显式转换以兼容全精度 SDK。
        self._camera_positions[index][0] = LVecBase3f(pos.x, pos.y, pos.z)
        # 仍保留原库的灯光/背景更新，只替换本帧相机输入的存储身份。
        self.render_node.setShaderInput(self._camera_inputs[index])
        return result
