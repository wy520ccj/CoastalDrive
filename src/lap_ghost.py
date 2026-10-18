"""120Hz完成步的轻量幽灵记录；只保存显示位姿，不创建或推进物理世界。"""

import ast
import hashlib
import json
import math
import struct
import sys
import zlib
from array import array
from dataclasses import dataclass

from panda3d import bullet, core

from lab_runtime import library_hashes
from paths import resource_root
from race import valid_splits
from vehicle_state import FIXED_DT, WheelState

ROW = struct.Struct("<34d")
HEADER = struct.Struct("<I")
MAX_TICKS = 120*60*30
MAX_BYTES = ROW.size*(MAX_TICKS+1)+65540


def covers_lap(frames, seconds):
    return (frames >= 2 and (frames-2)*FIXED_DT < seconds+1e-7
            and seconds <= (frames-1)*FIXED_DT+1e-7)


def ghost_context(seed):
    """覆盖物理/输入/判圈依赖及实际SDK；纯表现改动不使有效记录失效。"""
    root = resource_root()
    source = root/"src"
    pending = ["session", "simulation", "driving_modes", "controls", "race"]
    paths = set()
    while pending:
        module = pending.pop()
        path = source.joinpath(*module.split(".")).with_suffix(".py")
        if not path.is_file():
            path = source.joinpath(*module.split("."))/"__init__.py"
        if not path.is_file() or path in paths:
            continue
        paths.add(path)
        package = path.parent.relative_to(source).parts
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if isinstance(node, ast.Import):
                pending.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                prefix = package[:len(package)-node.level+1] if node.level else ()
                name = ".".join((*prefix, *((node.module or "").split(".") if node.module else ())))
                if name:
                    pending.append(name)
                pending.extend(".".join(filter(None, (name, alias.name))) for alias in node.names)
    paths.update(path for path in source.glob("*") if path.suffix in (".c", ".cpp", ".h", ".pyd"))
    if not paths:
        paths.update((*root.glob("*.exe"), *root.glob("*.pyd")))
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return {"source": digest.hexdigest(), "seed": seed, "panda": core.PandaSystem.getVersionString(),
            "bullet": bullet.getBulletVersion(), "bits": 64 if core.LPoint3 is core.LPoint3d else 32,
            "runtime_files": dict(library_hashes()),
            "source_files": [str(path.relative_to(root)) for path in sorted(paths)]}


@dataclass(frozen=True)
class GhostPose:
    position: tuple
    hpr: tuple
    wheels: tuple


@dataclass(frozen=True)
class GhostLap:
    score_id: str
    seconds: float
    splits: tuple
    context: dict
    data: bytes

    @property
    def frames(self):
        return len(self.data)//ROW.size

    def pose_at(self, seconds):
        if not math.isfinite(seconds) or seconds < 0 or seconds > self.seconds:
            return None
        index = min(self.frames-2, int(seconds/FIXED_DT))
        alpha = min(1., max(0., seconds/FIXED_DT-index))
        previous, current = (ROW.unpack_from(self.data, i*ROW.size) for i in (index, index+1))

        def vector(start, count):
            return tuple(a+(b-a)*alpha for a, b in zip(previous[start:start+count], current[start:start+count]))

        def orientation(start):
            old, new = previous[start:start+4], current[start:start+4]
            sign = 1. if sum(a*b for a, b in zip(old, new)) >= 0 else -1.
            values = tuple(a+(sign*b-a)*alpha for a, b in zip(old, new))
            norm = math.sqrt(sum(value*value for value in values))
            return tuple(value/norm for value in values)

        hpr = tuple(a+((b-a+180.)%360.-180.)*alpha for a, b in zip(previous[3:6], current[3:6]))
        return GhostPose(vector(0, 3), hpr,
                         tuple(WheelState(vector(6+7*i, 3), orientation(9+7*i)) for i in range(4)))


class GhostRecorder:
    def __init__(self, state, context):
        self.start_tick = state.tick
        self.context = context
        self.values = array("d")
        self.notice = ""
        self.append(state)

    @property
    def frames(self):
        return len(self.values)//34

    def append(self, state):
        if self.notice:
            return
        if self.frames > MAX_TICKS:
            self.notice = "已超过30分钟幽灵记录上限；本圈仍可继续计时。"
            self.values = array("d")
            return
        if state.tick != self.start_tick+self.frames:
            raise ValueError("幽灵记录必须来自连续的真实完成步")
        car = state.player
        self.values.extend((*car.position, car.heading, car.pitch, car.roll))
        for wheel in car.wheels:
            self.values.extend((*wheel.position, *wheel.orientation))

    def finish(self, score_id, race):
        if self.notice:
            raise ValueError(self.notice)
        if (not race.finished or race.invalidated or not race.new_best
                or not valid_splits(race.splits, race.last_lap)
                or not covers_lap(self.frames, race.last_lap)):
            raise ValueError("只有覆盖完整有效最佳圈的连续记录可以保存幽灵")
        values = self.values
        if sys.byteorder != "little":
            values = array("d", values)
            values.byteswap()
        return GhostLap(score_id, race.last_lap, race.splits, self.context, values.tobytes())


def save_ghost(lap, scores, mode):
    metadata = {"schema": "coastal-lap-ghost-v1", "hz": 120, "score_id": lap.score_id,
                "seconds": lap.seconds, "splits": lap.splits, "context": lap.context, "frames": lap.frames}
    header = json.dumps(metadata, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    if len(header) > 65536:
        raise ValueError("幽灵头信息超出记录格式范围")
    blob = b"CDG1"+zlib.compress(HEADER.pack(len(header))+header+lap.data, level=5)
    digest = hashlib.sha256(blob).hexdigest()
    folder = scores.path.parent/"ghosts"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/(digest+".cdg")
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(blob)
    temporary.replace(path)
    scores.attach_ghost(mode, lap.score_id, lap.seconds, lap.splits, digest)
    return path


def load_ghost(scores, mode, score_id, context, seconds, splits):
    digest = scores.ghost_digest(mode, score_id)
    if digest is None:
        return None
    path = scores.path.parent/"ghosts"/(digest+".cdg")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("幽灵文件过大，未载入")
    blob = path.read_bytes()
    if len(blob) > MAX_BYTES or hashlib.sha256(blob).hexdigest() != digest or blob[:4] != b"CDG1":
        raise ValueError("幽灵内容损坏，成绩保留")
    decoder = zlib.decompressobj()
    try:
        raw = decoder.decompress(blob[4:], MAX_BYTES+1)
    except zlib.error as error:
        raise ValueError("幽灵压缩数据损坏") from error
    if len(raw) > MAX_BYTES or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or len(raw) < 4:
        raise ValueError("幽灵压缩数据不完整或超限")
    size, = HEADER.unpack_from(raw)
    if size > 65536 or 4+size > len(raw):
        raise ValueError("幽灵头信息不完整")
    metadata = json.loads(raw[4:4+size])
    if (metadata["schema"] != "coastal-lap-ghost-v1" or metadata["hz"] != 120
            or metadata["score_id"] != score_id or metadata["context"] != context
            or metadata["seconds"] != seconds or tuple(metadata["splits"]) != tuple(splits)):
        raise ValueError("幽灵与本圈参考的版本、条件或成绩不同，请完成当前版本的新最佳圈。")
    frames = metadata["frames"]
    data = raw[4+size:]
    if (type(frames) is not int or not 2 <= frames <= MAX_TICKS+1 or len(data) != frames*ROW.size
            or not valid_splits(metadata["splits"], seconds)
            or not covers_lap(frames, seconds)):
        raise ValueError("幽灵采样数量或终点无效")
    for row in ROW.iter_unpack(data):
        if not all(math.isfinite(value) and abs(value) <= 1e7 for value in row):
            raise ValueError("幽灵包含非有限位姿")
        for start in (9, 16, 23, 30):
            norm = sum(value*value for value in row[start:start+4])
            if not .99 <= norm <= 1.01:
                raise ValueError("幽灵车轮姿态无效")
    return GhostLap(score_id, seconds, tuple(splits), context, data)
