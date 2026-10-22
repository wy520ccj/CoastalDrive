"""工坊中的真实车辆预览；独立显示场景，不创建物理世界。"""

import math

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
    Point2,
    Point3,
    TransparencyAttrib,
)
from simplepbr.envmap import EnvMap

from paths import resource_root
from skins import apply_skin, vehicle_for_design
from ui import theme
from vehicle_visual import load_vehicle, set_vehicle_reflection, vehicle_reflection


class WorkshopVehicle:
    def __init__(self, base):
        self.base = base
        self.buffer = None
        self.frame = None
        self.identity = None
        self.framing_identity = None
        self.framing_points = []
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
            ambient = AmbientLight('workshop-ambient')
            ambient.setColor((.45, .50, .58, 1))
            self.scene.setLight(self.scene.attachNewNode(ambient))
            key = DirectionalLight('workshop-key')
            key.setColor((3.0, 2.85, 2.65, 1))
            light = self.scene.attachNewNode(key)
            light.setPos(4, 8, 9)
            light.lookAt(0, 0, .5)
            self.scene.setLight(light)
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
            self.studio_angle = 35.
            previous_tasks = self.base.taskMgr.getTasksNamed('simplepbr update')
            self.pipeline = simplepbr.init(render_node=self.scene, window=self.buffer,
                camera_node=self.camera, taskmgr=self.base.taskMgr, max_lights=1,
                enable_shadows=False, msaa_samples=4)
            self.update_task = next(task for task in self.base.taskMgr.getTasksNamed('simplepbr update')
                                    if task not in previous_tasks)
            self.update_task.setName('workshop-pbr-update')
        identity = (vehicle.design_id, vehicle.config, skin_index)
        if identity != self.identity:
            for child in self.car_root.getChildren():
                child.removeNode()
            definition = vehicle_for_design(vehicle.design_id, 'sports')
            body, self.wheels = load_vehicle(self.car_root, definition, config=vehicle.config)
            self.car_root.setZ(vehicle.config.center_of_mass_height)
            apply_skin(body.getChild(0), skin_index)
            self.identity = identity
            self.wheel_radius = vehicle.config.wheel_radius+.035
        if self.frame is not None:
            self.frame.destroy()
        if studio and self.framing_identity != identity:
            self.framing_points = []
            # 按各网格部件外廓取景，避免整车空盒角点把敞篷/长车的镜头推得过远。
            for part in self.car_root.findAllMatches('**/+GeomNode'):
                low, high = part.getTightBounds(self.scene)
                self.framing_points.extend(Point3(x, y, z) for x in (low.x, high.x)
                    for y in (low.y, high.y) for z in (low.z, high.z))
            self.framing_identity = identity
        self.frame = DirectFrame(parent=parent, frameSize=box, frameColor=(1, 1, 1, 1),
                                 frameTexture=self.buffer.getTexture())
        self.camera.node().getLens().setAspectRatio((box[1]-box[0])/(box[3]-box[2]))
        self.camera.node().getLens().setFov(46)
        self.camera.node().getLens().setFilmOffset(0, 0)
        self.backplate.hide() if studio else self.backplate.show()
        self.buffer.setClearColor((0, 0, 0, 0) if studio else (.84, .93, .98, 1))
        if studio and self.garage_environment is None:
            from panda3d.core import Filename

            self.garage_environment = EnvMap.from_file_path(Filename.fromOsSpecific(
                str(resource_root()/'assets/game/vehicles/garage-skylit.env')))
        self.pipeline.env_map = self.garage_environment if studio else None
        for node in (self.car_root.getChild(0), *self.wheels):
            set_vehicle_reflection(node, self.garage_environment if studio else vehicle_reflection())
        if studio and self.contact_shadow is None:
            card = CardMaker('garage-model-shadow')
            card.setFrame(-4, 4, -4, 4)
            self.contact_shadow = self.scene.attachNewNode(card.generate())
            self.contact_shadow.setP(-90)
            self.contact_shadow.setZ(.001)
            self.contact_shadow.setTransparency(TransparencyAttrib.MAlpha)
            self.contact_shadow.setColorScale(1, 1, 1, .62)
            self.contact_shadow.setShaderOff()
            self.contact_shadow.setLightOff()
            self.contact_shadow.setDepthWrite(False)
        if self.contact_shadow is not None:
            self.contact_shadow.show() if studio else self.contact_shadow.hide()
            if studio:
                shadow = ('contact-shadow-club-coupe.png' if vehicle.design_id == 'club-coupe' else
                          'contact-shadow-subaru.png' if vehicle.design_id == 'subaru-wrx-sti' else
                          'contact-shadow-hatch.png' if vehicle.design_id == 'coastal-hatch' else 'contact-shadow.png')
                self.contact_shadow.setTexture(self.base.loader.loadTexture(theme.asset_filename('garage-v2/'+shadow)))
                self.contact_shadow.setH(0 if vehicle.design_id in ('club-coupe', 'coastal-hatch', 'subaru-wrx-sti') else 180)
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

    def orbit(self, step):
        self.studio_angle = (self.studio_angle+step) % 360
        angle = math.radians(self.studio_angle)
        low, high = self.car_root.getTightBounds(self.scene)
        center = (low+high)/2
        lens = self.camera.node().getLens()
        lens.setFilmOffset(0, 0)
        near, far = 2., 30.
        # 依据真实网格和视口留边；车顶、车轮完整放在展示区，不向物理配置反写。
        for _ in range(12):
            radius = (near+far)/2
            self.camera.setPos(math.sin(angle)*radius, math.cos(angle)*radius, center.z+radius*.16)
            self.camera.lookAt(center)
            projected_points = []
            for point in self.framing_points:
                projected = Point2()
                visible = lens.project(
                    self.camera.getRelativePoint(self.scene, point), projected)
                if not visible:
                    break
                projected_points.append(projected)
            ratio = float('inf')
            if len(projected_points) == len(self.framing_points):
                low_x, high_x = min(p.x for p in projected_points), max(p.x for p in projected_points)
                low_y, high_y = min(p.y for p in projected_points), max(p.y for p in projected_points)
                ratio = max((high_x-low_x)/1.8, (high_y-low_y)/1.50)
            if ratio <= 1.:
                far = radius
            else:
                near = radius
        self.camera.setPos(math.sin(angle)*far, math.cos(angle)*far, center.z+far*.16)
        self.camera.lookAt(center)
        # 镜头偏移居中实际投影，避免近端车头使单侧留白迫使整车缩小。
        size = lens.getFilmSize()
        lens.setFilmOffset((low_x+high_x)*size.x/4, ((low_y+high_y)/2+.08)*size.y/2)

    def highlight(self, topic):
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
