"""多核完整车辆数值求解；进程不创建Bullet世界，不提交刚体状态。"""

import logging
import pickle
import struct
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
from convex_queries import wheel_hull
from highway_curve import HighwayCurve
from highway_map import on_road as highway_on_road
from physics_wire import from_bytes, input_bytes, result_bytes
from suspension_contacts import StaticSupportShapes
from suspension_geometry import CylinderSurface
from test_track import on_asphalt
from tire_drivetrain import DrivetrainInput, DrivetrainStep
from triangle_support import TriangleSupport, triangle_entry
from vehicle_tire_step import TireAdvanceInput, tire_hardware
from wheel_envelope import _simplex_coordinates, cylinder_box_entry

_worker_geometry = None
_worker_memory = None
_worker_version = None
_worker_material = None
_worker_candidates = {}
_job_header = struct.Struct('<QQ')
_result_header = struct.Struct('<Qdd')


def _send_message(connection, message):
    connection.send_bytes(b'\0'+pickle.dumps(message,protocol=pickle.HIGHEST_PROTOCOL))


def _receive_message(connection):
    payload = connection.recv_bytes()
    kind = payload[0]
    if kind == 0:
        return pickle.loads(payload[1:])
    if kind == 1:
        identifier,configuration_id = _job_header.unpack_from(payload,1)
        return 'numeric',identifier,configuration_id,from_bytes(memoryview(payload)[1+_job_header.size:])
    if kind in (2,3):
        identifier,wall,cpu = _result_header.unpack_from(payload,1)
        result = from_bytes(memoryview(payload)[1+_result_header.size:]) if kind==2 else None
        return identifier,result,None,None,(wall,cpu)
    raise ValueError("未知车辆数值进程消息类型")


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
    _worker_candidates.clear()
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
        result = (request.solve(static_geometry=_worker_geometry,surface_material=material_query,
                                surface_candidates=_worker_candidates.setdefault(request.config,{}))
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
    reference = None
    try:
        while True:
            try:
                message = _receive_message(connection)
            except EOFError:
                break
            if message is None:
                break
            if message[0] == 'context':
                _,reference,configuration_id,config = message
                if config is not None:
                    configurations[configuration_id] = config
                continue
            if message[0] in ('initialise','prepare'):
                command = message[0]
                _,reference,configs = message
                try:
                    _load_geometry(reference)
                    for configuration_id,config in configs:
                        if config is not None:
                            configurations[configuration_id] = config
                        if command == 'prepare':
                            config = configurations[configuration_id]
                            tire_hardware(config)
                            wheel_hull(config.wheel_radius,config.wheel_width,
                                       config.wheel_shoulder_radius,config.wheel_crown_height)
                except Exception as error:  # noqa: BLE001 - 外部进程边界回传真实准备失败
                    _send_message(connection,(command,error,traceback.format_exc()))
                else:
                    _send_message(connection,(command,None,None))
                continue
            numeric = message[0] == 'numeric'
            if numeric:
                _,identifier,configuration_id,request = message
                configuration = None
            else:
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
                _send_message(connection,(identifier,None,error,traceback.format_exc(),
                                          (time.perf_counter()-wall,time.process_time()-cpu)))
            else:
                timing = time.perf_counter()-wall,time.process_time()-cpu
                if numeric:
                    packet = b'\2'+_result_header.pack(identifier,*timing)+result_bytes(result) if result is not None else b'\3'+_result_header.pack(identifier,*timing)
                    connection.send_bytes(packet)
                else:
                    _send_message(connection,(identifier,result,None,None,timing))
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
            return request
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
        self.worker_references = []
        self.configuration_transfers = 0
        self.numeric_packets = 0
        self.preparation_seconds = 0.
        self.preparing = set()
        self.preparation_configs = None
        self.preparation_started = None
        self.next_prepare_start = 0.
        self.preparation_next = 0
        self.initialisation_seconds = 0.

    def _start_one(self):
        context = get_context('spawn')
        parent,child = context.Pipe()
        process = context.Process(target=_worker_loop,args=(child,),daemon=True)
        process.start()
        child.close()
        self.processes.append((process,parent))
        self.worker_configurations.append(set())
        self.worker_references.append(None)

    def _start(self):
        while len(self.processes)<self.count:
            self._start_one()

    def _prepare_process(self, index):
        _send_message(self.processes[index][1],('prepare',self.reference,tuple((key,None) for key in self.preparation_configs)))
        self.preparing.add(index)

    def prepare(self, shapes, material, configs, *, background=False):
        """加载阶段启动进程并准备固定几何/硬件，不求解或推进任何车辆。"""
        if self.in_flight or self.completed:
            raise RuntimeError("物理预加载必须在世界停止推进时执行")
        self.finish_preparation()
        self.preparation_started = time.perf_counter()
        self._publish_geometry(shapes,material)
        configurations = {id(config):config for config in configs}
        self.configurations.update(configurations)
        self.preparation_configs = configurations
        # 进程启动、模块导入和地图几何在加载画面完成；倒计时只分担固定轮端缓存准备。
        self._start()
        for index in range(len(self.processes)):
            _send_message(self.processes[index][1],('initialise',self.reference,tuple(configurations.items())))
            self.worker_configurations[index].update(configurations)
            self.worker_references[index] = self.reference
            self.configuration_transfers += len(configurations)
        for process,connection in self.processes:
            self._prepared_response(process,connection,'initialise')
        self.initialisation_seconds = time.perf_counter()-self.preparation_started
        self.preparation_next = min(2,self.count) if background else self.count
        for index in range(self.preparation_next):
            self._prepare_process(index)
        self.next_prepare_start = time.perf_counter()+.12
        if not background:
            self.finish_preparation()

    def preparation_ready(self, *, wait=False):
        if self.preparation_configs is None:
            return True
        if self.preparation_next<self.count and (wait or time.perf_counter()>=self.next_prepare_start):
            self._prepare_process(self.preparation_next)
            self.preparation_next += 1
            self.next_prepare_start = time.perf_counter()+.12
        for index in tuple(self.preparing):
            process,connection = self.processes[index]
            if not wait and not connection.poll():
                continue
            self._prepared_response(process,connection,'prepare')
            self.preparing.remove(index)
        if self.preparation_next==self.count and not self.preparing:
            self.preparation_seconds = time.perf_counter()-self.preparation_started
            self.preparation_configs = None
            return True
        return False

    def _prepared_response(self, process, connection, command):
        try:
            kind,error,trace = _receive_message(connection)
        except EOFError as disconnected:
            raise RuntimeError(f"预加载时数值进程{process.pid}意外退出") from disconnected
        if kind != command:
            raise RuntimeError("物理预加载返回类型不一致")
        if error is not None:
            error.add_note(trace)
            raise error

    def finish_preparation(self):
        while not self.preparation_ready(wait=True):
            pass

    def clear_geometry(self):
        self.finish_preparation()
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
        self._start()
        self.finish_preparation()
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
        connection = self.processes[index][1]
        if isinstance(frozen,TireAdvanceInput) and frozen.normal_system is None:
            if configuration is not None or self.worker_references[index] != self.reference:
                _send_message(connection,('context',self.reference,configuration_id,configuration))
                self.worker_references[index] = self.reference
            connection.send_bytes(b'\1'+_job_header.pack(identifier,configuration_id)+input_bytes(frozen))
            self.numeric_packets += 1
        else:
            if isinstance(frozen,TireAdvanceInput):
                frozen = replace(frozen,config=None,world_source=None)
            _send_message(connection,(identifier,frozen,self.reference,configuration_id,configuration))
        self.in_flight[index] = identifier
        return index,identifier

    def _receive(self, index, identifier):
        process,connection = self.processes[index]
        try:
            returned,result,error,trace,timing = _receive_message(connection)
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
                'configuration_transfers':self.configuration_transfers,'timing_window_requests':len(self.samples),
                'preparation_seconds':self.preparation_seconds,'initialisation_seconds':self.initialisation_seconds,
                'numeric_packets':self.numeric_packets}

    def close(self):
        try:
            for process,connection in self.processes:
                try:
                    _send_message(connection,None)
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
            self.worker_references.clear()
            self.in_flight.clear()
            self.completed.clear()
            self.preparing.clear()
            self.preparation_configs = None
        finally:
            self.clear_geometry()
