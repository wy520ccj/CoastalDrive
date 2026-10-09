"""多核完整车辆数值求解；进程不创建Bullet世界，不提交刚体状态。"""

import logging
import pickle
import time
import traceback
from collections import deque
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from functools import lru_cache
from multiprocessing import get_context
from multiprocessing.shared_memory import SharedMemory

from wheel_contact_kernels import cached_surface_entry, prepared_support_candidates

from coastal_map import on_road
from highway_curve import HighwayCurve
from highway_map import on_road as highway_on_road
from suspension_contacts import StaticSupportShapes
from suspension_geometry import CylinderSurface
from test_track import on_asphalt
from tire_drivetrain import DrivetrainInput, DrivetrainStep
from triangle_support import TriangleSupport, triangle_entry
from vehicle_tire_step import TireAdvanceInput
from wheel_envelope import _simplex_coordinates, cylinder_box_entry

_worker_geometry = None
_worker_memory = None
_worker_version = None
_worker_material = None


@dataclass(frozen=True)
class StaticSource:
    """唯一世界已确认的静态资格；查询引用只保留源分区编号。"""
    index: int

    def isStatic(self):
        return True


class StaticQueryBoundary:
    def sweepTestClosest(self, *args):
        raise WorldQueryRequired()


def material_query(x, y):
    track,curve,origin = _worker_material
    if curve is not None:
        return curve.on_asphalt(x,y+origin)
    if track=='coastal':
        return on_road(x,y)
    if track=='highway':
        return highway_on_road(x,y)
    if track=='test':
        return on_asphalt(x,y)
    return abs(x)<=6.75


class WorldQueryRequired(Exception):
    """末查询遇到不支持的原生凸体，必须由唯一世界完成这一车的求解。"""


@dataclass(frozen=True)
class GeometryRef:
    name: str
    size: int
    version: int


@dataclass(frozen=True)
class FrozenWorldSurface(CylinderSurface):
    """同子步真实静态几何的只读数值视图；没有世界或刚体引用。"""
    candidate_low: tuple = ()
    candidate_high: tuple = ()
    candidate_surfaces: tuple = ()
    candidates: dict = field(default_factory=dict, init=False, repr=False, compare=False)
    queries: dict = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self):
        self.candidates.update(low=self.candidate_low, high=self.candidate_high,
                               surfaces=list(self.candidate_surfaces), native_needed=False)

    def relative_entry(self, start, end, axis):
        key = start, end, axis
        if key in self.queries:
            return self.queries[key]
        covered, entry = cached_surface_entry(self.candidates, start, end, axis, self.offset,
            self.wheel_radius, self.width, self.shoulder, self.crown, triangle_entry, cylinder_box_entry,
            _simplex_coordinates)
        if not covered:
            # 离开预取邻域时仍查询完整真实静态几何；原范围、padding和三角面顺序保持。
            padding = self.wheel_radius + self.width / 2 + 1e-5
            points = tuple(tuple(p[a] + self.offset[a] for a in range(3)) for p in (start,end))
            low = tuple(min(p[a] for p in points)-padding-.05 for a in range(3))
            high = tuple(max(p[a] for p in points)+padding+.05 for a in range(3))
            selected = prepared_support_candidates(_worker_geometry.native, low, high)
            surfaces = []
            for body, supported, parts in selected:
                if not supported:
                    raise WorldQueryRequired()
                for part, local_center, local_half in parts:
                    inverse, frame, translation, half, margin, plane, triangles, _bounds = part
                    if triangles is not None:
                        triangles = TriangleSupport(triangles.low,triangles.high,
                            tuple(triangles.candidates(local_center,local_center,
                                                       tuple(value+margin for value in local_half))))
                    surfaces.append((body,inverse,frame,half,margin,plane,triangles,translation))
            self.candidates.update(low=low,high=high,surfaces=surfaces,native_needed=False)
            covered, entry = cached_surface_entry(self.candidates, start, end, axis, self.offset,
                self.wheel_radius, self.width, self.shoulder, self.crown, triangle_entry, cylinder_box_entry,
                _simplex_coordinates)
            if not covered:
                raise AssertionError("数值候选必须覆盖刚完成筛选的真实路径")
        self.queries[key] = entry
        return entry


def _load_geometry(reference):
    global _worker_geometry, _worker_memory, _worker_version, _worker_material
    if _worker_version == reference:
        return
    if _worker_memory is not None:
        _worker_memory.close()
    _worker_memory = SharedMemory(name=reference.name)
    groups,material,hulls = pickle.loads(_worker_memory.buf[:reference.size])
    _worker_geometry = StaticSupportShapes(tuple((StaticSource(index),supported,parts) for index,supported,parts in groups))
    _worker_geometry.install_hulls({StaticSource(index):parts for index,parts in hulls})
    track,curve_values,origin = material
    curve = None
    if curve_values is not None:
        curve = HighwayCurve.__new__(HighwayCurve)
        curve.seed,curve.height,curve.base_height,curve.y_table,curve.advance = curve_values
        curve.sample = lru_cache(maxsize=8192)(curve.sample)
    _worker_material = track,curve,origin
    _worker_version = reference


def _solve_vehicle(request, reference):
    _load_geometry(reference)
    try:
        result = (request.solve(static_geometry=_worker_geometry,surface_material=material_query)
                  if isinstance(request,TireAdvanceInput) else request.solve())
    except WorldQueryRequired:
        return None
    if isinstance(result,DrivetrainStep) and result.suspension_system is not None:
        # 只返回末状态；支持面含本地原生缓存，不跨进程传送或代替主世界的支持面。
        result = replace(result, suspension_system=replace(result.suspension_system, kinematics=None))
    return result


def _worker_loop(connection):
    """每个进程一条直接管道；避免通用任务队列的额外GIL线程和唤醒延迟。"""
    configurations = {}
    try:
        while True:
            try:
                message = connection.recv()
            except EOFError:
                break
            if message is None:
                break
            identifier, request, reference, configuration_id, configuration = message
            if configuration_id is not None:
                if configuration is not None:
                    configurations[configuration_id] = configuration
                request = replace(request, config=configurations[configuration_id])
            wall,cpu = time.perf_counter(),time.process_time()
            try:
                result = _solve_vehicle(request, reference)
            except Exception as error:  # noqa: BLE001 - 外部进程边界必须回传原异常
                # 外部进程边界回传真实异常；主进程报告失败，不改用较松的求解。
                connection.send((identifier,None,error,traceback.format_exc(),
                                 (time.perf_counter()-wall,time.process_time()-cpu)))
            else:
                connection.send((identifier,result,None,None,(time.perf_counter()-wall,time.process_time()-cpu)))
    finally:
        connection.close()
        if _worker_memory is not None:
            _worker_memory.close()


def _freeze_system(system):
    if system.kinematics is None:
        return system
    planes = []
    for contact in system.kinematics:
        if contact is None:
            planes.append(None)
            continue
        surface = contact.surface
        candidates = surface.candidates
        if not candidates or candidates['native_needed'] or candidates.get('hulls'):
            return None
        # 去掉Bullet节点和矩阵对象；后续求交只读取实际数值变换及有限网格。
        surfaces = tuple((index,None,*part[2:]) for index,part in enumerate(candidates['surfaces']))
        frozen = FrozenWorldSurface(surface.half,surface.radius,surface.axes,surface.offset,
            surface.wheel_radius,surface.reach,surface.width,surface.shoulder,surface.wheel_axis,
            surface.plane,surface.crown,surface.triangles,
            candidates['low'],candidates['high'],surfaces)
        planes.append(replace(contact, surface=frozen))
    return replace(system, kinematics=tuple(planes))


def _freeze_request(request):
    if isinstance(request,TireAdvanceInput):
        if request.normal_system is None:
            return replace(request, world_source=None)
        system = _freeze_system(request.normal_system)
        return replace(request, normal_system=system) if system is not None else None
    system = request.parameters['suspension']
    if system is None:
        return request
    frozen = _freeze_system(system)
    if frozen is None:
        return None
    parameters = dict(request.parameters)
    parameters['suspension'] = frozen
    return DrivetrainInput(request.values, parameters)


class PhysicsWorkers:
    """持久数值进程直接交换输入/末状态，所有车辆完整方程并行。"""

    def __init__(self, count):
        self.count = count
        self.processes = []
        self.identifier = 0
        self.in_flight = {}
        self.completed = {}
        self.memory = None
        self.reference = None
        self.shapes = None
        self.version = 0
        self.material = None
        self.remote_count = 0
        self.world_query_count = 0
        self.samples = deque(maxlen=4096)
        self.configurations = {}
        self.worker_configurations = []
        self.configuration_transfers = 0

    def clear_geometry(self):
        self.shapes = None
        self.reference = None
        self.material = None
        if self.memory is not None:
            self.memory.close()
            self.memory.unlink()
            self.memory = None

    def _publish_geometry(self, shapes, material):
        if self.shapes is shapes and self.material==material:
            return
        self.clear_geometry()
        # 顺序与唯一世界的静态分区完全一致，共享内存只保存数值而非第二个物理世界。
        groups = tuple((index,supported,tuple((None,*part[1:]) for part in parts))
                       for index,(_body,supported,parts) in enumerate(shapes))
        track,curve,origin = material
        curve_values = (curve.seed,curve.height,curve.base_height,tuple(curve.y_table),curve.advance) if curve is not None else None
        hulls = tuple((index,shapes.hulls[body]) for index,(body,_supported,_parts) in enumerate(shapes) if body in shapes.hulls)
        payload = pickle.dumps((groups,(track,curve_values,origin),hulls), protocol=pickle.HIGHEST_PROTOCOL)
        self.memory = SharedMemory(create=True, size=len(payload))
        self.memory.buf[:len(payload)] = payload
        self.version += 1
        self.reference = GeometryRef(self.memory.name, len(payload), self.version)
        self.shapes = shapes
        self.material = material

    def submit(self, request, shapes, material):
        """该车读取完成便开始数值计算，与主进程读取后续车辆重叠。"""
        frozen = _freeze_request(request)
        if frozen is None:
            return None
        if not self.processes:
            context = get_context('spawn')
            for _ in range(self.count):
                parent,child = context.Pipe()
                process = context.Process(target=_worker_loop,args=(child,),daemon=True)
                process.start()
                child.close()
                self.processes.append((process,parent))
                self.worker_configurations.append(set())
        self._publish_geometry(shapes, material)
        identifier = self.identifier
        self.identifier += 1
        index = identifier % len(self.processes)
        if index in self.in_flight:
            previous = self.in_flight[index]
            self.completed[previous] = self._receive(index, previous)
        configuration_id,configuration = None,None
        if isinstance(frozen,TireAdvanceInput):
            configuration_id = id(frozen.config)
            self.configurations[configuration_id] = frozen.config
            if configuration_id not in self.worker_configurations[index]:
                configuration = frozen.config
                self.worker_configurations[index].add(configuration_id)
                self.configuration_transfers += 1
            frozen = replace(frozen,config=None)
        self.processes[index][1].send((identifier,frozen,self.reference,configuration_id,configuration))
        self.in_flight[index] = identifier
        return index,identifier

    def _receive(self, index, identifier):
        process,connection = self.processes[index]
        try:
            returned,result,error,trace,timing = connection.recv()
        except EOFError as disconnected:
            raise RuntimeError(f"车辆数值进程{process.pid}意外退出") from disconnected
        if returned != identifier:
            raise RuntimeError("车辆数值进程返回的请求编号不一致")
        del self.in_flight[index]
        self.samples.append(timing)
        if error is not None:
            error.add_note(trace)
            raise error
        return result

    def results(self, requests, pending, query_lock=None):
        """所有车已读取后，按原顺序交回结果；后续数值计算与已完成车的提交重叠。"""
        for request,handle in zip(requests,pending):
            result = None
            if handle is not None:
                index,identifier = handle
                result = self.completed.pop(identifier) if identifier in self.completed else self._receive(index,identifier)
            if result is None:
                # 原生凸体求交明确交回唯一世界；数值收敛异常仍直接报告，不重试或掩盖。
                self.world_query_count += 1
                with query_lock if query_lock is not None else nullcontext():
                    result = request.solve()
            else:
                self.remote_count += 1
                if isinstance(result,DrivetrainStep) and result.suspension_system is not None:
                    system = result.suspension_system
                    result = replace(result, suspension_system=replace(system,
                        kinematics=request.parameters['suspension'].kinematics))
            yield result

    def diagnostics(self):
        values = {}
        for column,name in ((0,'wall'),(1,'cpu')):
            samples = sorted(timing[column]*1000 for timing in self.samples)
            values[name] = {'mean_ms':sum(samples)/len(samples),'p95_ms':samples[int((len(samples)-1)*.95)],
                            'max_ms':samples[-1]} if samples else {}
        return {'processes':len(self.processes),'configured_processes':self.count,'geometry_versions':self.version,
                'remote':self.remote_count,'world_required':self.world_query_count,'worker_solve':values,
                'configuration_transfers':self.configuration_transfers,'timing_window_requests':len(self.samples)}

    def close(self):
        try:
            for process,connection in self.processes:
                try:
                    connection.send(None)
                except OSError as disconnected:
                    logging.getLogger(__name__).warning("关闭数值进程%s时管道已断开：%s",process.pid,disconnected)
            for process,connection in self.processes:
                process.join(5.)
                if process.is_alive():
                    process.terminate()
                    process.join()
                connection.close()
                process.close()
            self.processes.clear()
            self.configurations.clear()
            self.worker_configurations.clear()
            self.in_flight.clear()
            self.completed.clear()
        finally:
            self.clear_geometry()
