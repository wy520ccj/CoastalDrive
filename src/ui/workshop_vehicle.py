"""工坊中的真实车辆预览；独立显示场景，不创建物理世界。"""

import math

import numpy as np
import simplepbr
from direct.gui.DirectGui import DirectFrame
from panda3d.core import (
    AmbientLight,
    CardMaker,
    DirectionalLight,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LineSegs,
    NodePath,
    PerspectiveLens,
    TransparencyAttrib,
)
from simplepbr.envmap import EnvMap

from paths import resource_root
from skins import apply_skin, vehicle_for_design
from ui import theme
from ui.garage_framing import mesh_vertices, project_vertices
from ui.garage_paint import garage_paint_shader
from ui.garage_reflection import reflect_vehicle
from ui.garage_vehicle_style import apply_atelier_vehicle_style
from vehicle_visual import load_vehicle, set_vehicle_reflection, vehicle_reflection


class WorkshopVehicle:
    def __init__(self, base):
        self.base = base
        self.buffer = None
        self.frame = None
        self.identity = None
        self.framing_identity = None
        self.framing_vertices = None
        self.framing_cache = {}
        self.highlight_topic = None
        self.garage_environment = None

    def show(self, parent, box, vehicle, *, studio=False, skin_index=None):
        skin_index = self.base.skin_index if skin_index is None else skin_index
        if self.buffer is None:
            self.scene = NodePath('workshop-display-only')
            self.buffer = self.base.win.makeTextureBuffer('workshop-vehicle', 1280, 720)
            self.buffer.setClearColor((.84, .93, .98, 1))
            lens = PerspectiveLens()
            lens.setFov(46)
            lens.setAspectRatio(1.6)
            lens.setNearFar(.1, 80)
            self.camera = self.base.makeCamera(self.buffer, scene=self.scene, lens=lens)
            self.camera.reparentTo(self.scene)
            self.camera.setPos(5.4, 7.5, 3.0)
            self.camera.lookAt(0, 0, .60)
            self.ambient_light = AmbientLight('workshop-ambient')
            self.ambient_light.setColor((.45, .50, .58, 1))
            self.scene.setLight(self.scene.attachNewNode(self.ambient_light))
            self.key_light = DirectionalLight('workshop-key')
            self.key_light.setColor((3.0, 2.85, 2.65, 1))
            self.key_light_np = self.scene.attachNewNode(self.key_light)
            self.key_light_np.setPos(4, 8, 9)
            self.key_light_np.lookAt(0, 0, .5)
            self.scene.setLight(self.key_light_np)
            # 空车库底图只作展示布景；真实车模和零件仍在其前方独立渲染。
            card = CardMaker('workshop-backplate')
            card.setFrame(-1, 1, -1, 1)
            self.backplate = self.scene.attachNewNode(card.generate())
            self.backplate.setTexture(self.base.loader.loadTexture(
                theme.asset_filename('backgrounds/workshop-bright-v1.png')))
            self.backplate.setMat(self.camera.getMat(self.scene))
            self.backplate.setPos(self.backplate, 0, 30, 0)
            self.backplate.setShaderOff()
            self.backplate.setLightOff()
            self.backplate.setBin('background', 0)
            self.backplate.setDepthWrite(False)
            # 柔和接地阴影属于展台表现，不向Simulation创建额外物体。
            self.shadows = []
            for layer in range(18):
                radius = 1.0-layer*.025
                data = GeomVertexData('contact-shadow', GeomVertexFormat.getV3(), Geom.UHStatic)
                writer = GeomVertexWriter(data, 'vertex')
                writer.addData3f(0, 0, -.013+layer*.0001)
                for step in range(49):
                    phase = step*math.pi/24
                    writer.addData3f(1.65*radius*math.cos(phase),
                                     3.2*radius*math.sin(phase), -.013+layer*.0001)
                triangles = GeomTriangles(Geom.UHStatic)
                for index in range(1, 49):
                    triangles.addVertices(0, index, index+1)
                geom = Geom(data)
                geom.addPrimitive(triangles)
                shadow = GeomNode('contact-shadow')
                shadow.addGeom(geom)
                node = self.scene.attachNewNode(shadow)
                node.setColor(.08, .16, .21, .03)
                node.setTransparency(TransparencyAttrib.MAlpha)
                node.setLightOff()
                node.setShaderOff()
                node.setDepthWrite(False)
                self.shadows.append(node)
            self.car_root = self.scene.attachNewNode('current-vehicle')
            self.studio = None
            self.contact_shadow = None
            self.floor_reflection = None
            self.reflection_identity = None
            self.studio_angle = -42.
            previous_tasks = self.base.taskMgr.getTasksNamed('simplepbr update')
            self.pipeline = simplepbr.init(render_node=self.scene, window=self.buffer,
                camera_node=self.camera, taskmgr=self.base.taskMgr, max_lights=1,
                enable_shadows=False, msaa_samples=4, exposure=0.80)
            self.update_task = next(task for task in self.base.taskMgr.getTasksNamed('simplepbr update')
                                    if task not in previous_tasks)
            self.update_task.setName('workshop-pbr-update')
        identity = (vehicle.design_id, vehicle.config, skin_index, studio)
        if identity != self.identity:
            self.framing_cache.clear()
            self.highlight_topic = None
            for child in self.car_root.getChildren():
                child.removeNode()
            definition = vehicle_for_design(vehicle.design_id, 'sports')
            body, self.wheels = load_vehicle(self.car_root, definition, config=vehicle.config)
            self.car_root.setZ(vehicle.config.center_of_mass_height)
            apply_skin(body.getChild(0), skin_index)
            if studio:
                apply_atelier_vehicle_style(self.car_root, self.wheels, vehicle.design_id)
            self.identity = identity
            self.wheel_radius = vehicle.config.wheel_radius+.035
        if self.frame is not None:
            self.frame.destroy()
        geometry = (vehicle.design_id, vehicle.config)
        if studio and self.framing_identity != geometry:
            self.framing_vertices = mesh_vertices(self.car_root, self.scene)
            self.framing_identity = geometry
        self.frame = DirectFrame(parent=parent, frameSize=box,
                                 frameColor=(1.0, 0.98, 0.95, 1) if studio else (1, 1, 1, 1),
                                 frameTexture=self.buffer.getTexture())
        self.camera.node().getLens().setAspectRatio((box[1]-box[0])/(box[3]-box[2]))
        # 落日工坊采用 34° 中焦摄影镜头，消除广角车头畸变并与车库背景透视自然吻合。
        self.camera.node().getLens().setFov(34 if studio else 46)
        self.camera.node().getLens().setFilmOffset(0, 0)
        self.backplate.hide() if studio else self.backplate.show()
        self.buffer.setClearColor((0, 0, 0, 0) if studio else (.84, .93, .98, 1))
        if studio and self.garage_environment is None:
            from panda3d.core import Filename

            # 使用与落日工坊实景（左侧爱迪生灯、顶棚暗钢梁、右侧落日海门）方向一致的专属 HDRI。
            self.garage_environment = EnvMap.from_file_path(Filename.fromOsSpecific(
                str(resource_root()/'assets/game/vehicles/garage-sunset-workshop.env')))
        self.pipeline.env_map = self.garage_environment if studio else None
        if studio:
            # 落日海岸工坊摄影光影：微弱暗冷环境底光 + 右侧落日海门低角度斜射暖金主光（掠射车身侧面，保留机盖深沉车漆对比）。
            self.ambient_light.setColor((.042, .046, .060, 1))
            self.key_light.setColor((1.95, 1.04, 0.46, 1))
            self.key_light_np.setPos(11.5, -2.2, 2.6)
            self.key_light_np.lookAt(0, 0, .52)
        else:
            self.ambient_light.setColor((.45, .50, .58, 1))
            self.key_light.setColor((3.0, 2.85, 2.65, 1))
            self.key_light_np.setPos(4, 8, 9)
            self.key_light_np.lookAt(0, 0, .5)
        for part in self.car_root.findAllMatches('**/paint'):
            if studio:
                part.setShader(garage_paint_shader(self.pipeline.use_330), 2)
            else:
                part.clearShader()
        for node in (self.car_root.getChild(0), *self.wheels):
            set_vehicle_reflection(node, self.garage_environment if studio else vehicle_reflection())
        if self.floor_reflection is not None and (not studio or self.reflection_identity != identity):
            self.floor_reflection.removeNode()
            self.floor_reflection = None
            self.reflection_identity = None
        if studio and self.floor_reflection is None:
            self.floor_reflection = reflect_vehicle(self.car_root, self.scene, self.pipeline.use_330)
            self.reflection_identity = identity
        if studio and self.contact_shadow is None:
            card = CardMaker('garage-model-shadow')
            card.setFrame(-4, 4, -4, 4)
            self.contact_shadow = self.scene.attachNewNode(card.generate())
            self.contact_shadow.setP(-90)
            self.contact_shadow.setZ(.001)
            self.contact_shadow.setTransparency(TransparencyAttrib.MAlpha)
            self.contact_shadow.setColorScale(1, 1, 1, .94)
            self.contact_shadow.setShaderOff()
            self.contact_shadow.setLightOff()
            self.contact_shadow.setDepthWrite(False)
        if self.contact_shadow is not None:
            self.contact_shadow.show() if studio else self.contact_shadow.hide()
            if studio:
                shadow = ('contact-shadow-porsche-930.png' if vehicle.design_id == 'porsche-930' else
                          'contact-shadow-club-coupe.png' if vehicle.design_id == 'club-coupe' else
                          'contact-shadow-brz.png' if vehicle.design_id == 'game-tuned' else
                          'contact-shadow-subaru.png' if vehicle.design_id == 'subaru-wrx-sti' else
                          'contact-shadow-elise.png' if vehicle.design_id == 'coastal-roadster' else
                          'contact-shadow-gr86.png' if vehicle.design_id == 'gr86-2022-premium-6mt' else
                          'contact-shadow-hatch.png' if vehicle.design_id == 'coastal-hatch' else 'contact-shadow.png')
                self.contact_shadow.setTexture(self.base.loader.loadTexture(theme.asset_filename('garage-v2/'+shadow)))
                self.contact_shadow.setH(0 if vehicle.design_id in ('game-tuned', 'club-coupe', 'coastal-hatch', 'coastal-roadster', 'subaru-wrx-sti', 'gr86-2022-premium-6mt', 'porsche-930') else 180)
        for shadow in self.shadows:
            shadow.hide() if studio else shadow.show()
        self.studio_active = studio
        if studio:
            self.orbit(0)
        else:
            self.camera.setPos(5.4, 7.5, 3.0)
            self.camera.lookAt(0, 0, .60)
        half_width = 30*math.tan(math.radians(self.camera.node().getLens().getHfov()/2))
        self.backplate.setScale(half_width, 1, half_width/(box[1]-box[0])*(box[3]-box[2]))
        self.buffer.setActive(True)
        for buffer in self.pipeline._filtermgr.buffers:
            buffer.setActive(True)
        if not self.base.taskMgr.hasTaskNamed('workshop-pbr-update'):
            self.base.taskMgr.add(self.update_task)

    def orbit(self, step):
        self.studio_angle = (self.studio_angle+step) % 360
        lens = self.camera.node().getLens()
        lens.setFilmOffset(0, 0)
        projection = tuple(value for row in lens.getProjectionMat() for value in row)
        key = self.studio_angle, projection, self.highlight_topic
        if key in self.framing_cache:
            transform, offset = self.framing_cache[key]
            self.camera.setTransform(self.scene, transform)
            lens.setFilmOffset(*offset)
            return
        angle = math.radians(self.studio_angle)
        low, high = self.car_root.getTightBounds(self.scene)
        center = (low+high)/2
        near, far = 2., 30.
        # 依据真实网格和视口留边；车顶、车轮完整放在展示区，不向物理配置反写。
        for _ in range(12):
            radius = (near+far)/2
            self.camera.setPos(math.sin(angle)*radius, math.cos(angle)*radius, center.z+radius*.072)
            self.camera.lookAt(center)
            projected = project_vertices(self.framing_vertices, self.scene, self.camera)
            ratio = float('inf')
            if projected is not None:
                low_x, low_y = np.min(projected, axis=0)
                high_x, high_y = np.max(projected, axis=0)
                ratio = max((high_x-low_x)/1.8, (high_y-low_y)/1.50)
            if ratio <= 1.:
                far = radius
            else:
                near = radius
        self.camera.setPos(math.sin(angle)*far, math.cos(angle)*far, center.z+far*.072)
        self.camera.lookAt(center)
        projected = project_vertices(self.framing_vertices, self.scene, self.camera)
        low_x, low_y = np.min(projected, axis=0)
        high_x, high_y = np.max(projected, axis=0)
        # 镜头偏移居中实际投影，避免近端车头使单侧留白迫使整车缩小。
        size = lens.getFilmSize()
        lens.setFilmOffset((low_x+high_x)*size.x/4, ((low_y+high_y)/2+.08)*size.y/2)
        # 同车、同镜头和同零件标记复用精确结果；不重新投影整车网格。
        self.framing_cache[key] = self.camera.getTransform(self.scene), tuple(lens.getFilmOffset())

    def highlight(self, topic):
        self.highlight_topic = topic
        for index, wheel in enumerate(self.wheels):
            wheel.setColorScale(1, .72, .30, 1) if topic == 'tires' and index < 2 else wheel.clearColorScale()
        old = self.car_root.find('part-highlight')
        if not old.isEmpty():
            old.removeNode()
        if topic is None:
            return
        ring = LineSegs('part-highlight')
        ring.setThickness(3)
        ring.setColor(1, .66, .22, 1)
        for wheel in self.wheels[:2] if topic == 'tires' else self.wheels:
            center = wheel.getPos(self.car_root)
            for step in range(41):
                angle = step*math.pi/20
                point = (center.x*1.04, center.y+math.cos(angle)*self.wheel_radius,
                         center.z+math.sin(angle)*self.wheel_radius)
                ring.moveTo(*point) if step == 0 else ring.drawTo(*point)
        node = self.car_root.attachNewNode(ring.create())
        node.setLightOff()
        node.setShaderOff()

    def hide(self):
        if self.buffer is not None:
            self.buffer.setActive(False)
            for buffer in self.pipeline._filtermgr.buffers:
                buffer.setActive(False)
            self.base.taskMgr.remove(self.update_task)

    def close(self):
        if self.buffer is not None:
            self.update_task.remove()
            # simplepbr未提供销毁入口；其Panda FilterManager持有的HDR缓冲必须同步释放。
            self.pipeline._filtermgr.cleanup()
            self.frame.destroy()
            self.camera.removeNode()
            self.scene.removeNode()
            self.base.graphicsEngine.removeWindow(self.buffer)
            self.buffer = None
