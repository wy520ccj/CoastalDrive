"""把当前道路和玩家姿态绘制到轻量 Panda3D 小地图纹理。"""

import math
from itertools import pairwise

from panda3d.core import SamplerState, Texture

import coastal_map


class MinimapRenderer:
    def __init__(self, size=256):
        if size not in (192, 256):
            raise ValueError("小地图尺寸应为 192 或 256")
        self.size = size
        self.texture = Texture("driving-minimap")
        self.texture.setup2dTexture(size, size, Texture.T_unsigned_byte, Texture.F_rgba8)
        self.texture.setMinfilter(SamplerState.FT_nearest)
        self.texture.setMagfilter(SamplerState.FT_nearest)
        self._inside = bytearray(size * size)
        base = bytearray(size * size * 4)
        center = (size - 1) / 2
        radius = size / 2 - 1
        for y in range(size):
            for x in range(size):
                i = y * size + x
                if (x - center) ** 2 + (y - center) ** 2 <= radius ** 2:
                    self._inside[i] = 1
                    base[i * 4:i * 4 + 4] = bytes((35, 111, 139, 255))
        self._base_pixels = bytes(base)
        self._pixels = bytearray(self._base_pixels)

    def _begin(self):
        self._pixels[:] = self._base_pixels

    def _put(self, x, y, color):
        x, y = round(x), round(y)
        if not (0 <= x < self.size and 0 <= y < self.size):
            return
        if not self._inside[y * self.size + x]:
            return
        i = (y * self.size + x) * 4
        self._pixels[i:i + 4] = bytes((*color, 255))

    def _line(self, a, b, color, width=1):
        x0, y0 = (round(v) for v in a)
        x1, y1 = (round(v) for v in b)
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx - dy
        while True:
            half = width // 2
            for ox in range(-half, half + 1):
                for oy in range(-half, half + 1):
                    self._put(x0 + ox, y0 + oy, color)
            if x0 == x1 and y0 == y1:
                break
            twice = 2 * error
            if twice > -dy:
                error -= dy
                x0 += sx
            if twice < dx:
                error += dx
                y0 += sy

    def _polygon(self, points, color):
        """扫描填充多边形，供滨海陆地底色使用。"""
        edges = list(zip(points, points[1:] + points[:1]))
        for y in range(self.size):
            crossings = []
            for (x0, y0), (x1, y1) in edges:
                if (y0 <= y < y1) or (y1 <= y < y0):
                    crossings.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            crossings.sort()
            for left, right in zip(crossings[::2], crossings[1::2]):
                for x in range(max(0, math.ceil(left)), min(self.size, math.floor(right) + 1)):
                    self._put(x, y, color)

    def _upload(self):
        self.texture.setRamImage(bytes(self._pixels))
        return self.texture

    def update(self, snapshot, track, road, origin_y=0.0):
        """返回圆形纹理。海岸使用地图坐标，无限高速使用玩家附近的真实路形。"""
        self._begin()
        track_id = getattr(track, "value", getattr(getattr(track, "id", None), "value", track))
        position = snapshot.player.position
        is_coastal = track_id == "coastal" or getattr(road, "closed", False)
        if is_coastal:
            range_m = 130.0
            center_x, center_y = position[0], position[1]
            from tracks import COASTAL_CIRCUIT
            checkpoints = COASTAL_CIRCUIT.checkpoints
            boundary = [coastal_map.offset_point(p, -coastal_map.SHOULDER_WIDTH / 2)[:2]
                        for p in coastal_map.MAP_POINTS]
            to_screen = lambda p: (
                (p[0] - center_x) * self.size / (2 * range_m) + (self.size - 1) / 2,
                (p[1] - center_y) * self.size / (2 * range_m) + (self.size - 1) / 2,
            )
            self._polygon([to_screen(p) for p in boundary], (91, 131, 89))
            path = [to_screen((p.x, p.y)) for p in coastal_map.MAP_POINTS]
            path.append(path[0])
            for a, b in pairwise(path):
                self._line(a, b, (204, 190, 150), max(10, self.size // 12))
            for a, b in pairwise(path):
                self._line(a, b, (48, 58, 65), max(7, self.size // 30))
            for distance in checkpoints:
                p = coastal_map.point_at(distance)
                x, y = to_screen((p.x, p.y))
                self._dot(x, y, (255, 193, 71), max(2, self.size // 64))
        else:
            # 显示玩家前后约 180 m。重定位只改变本地原点，地图沿全局路线采样。
            range_m = 180.0
            center_x = position[0]
            global_y = position[1] + origin_y
            center_y = global_y
            scale = self.size / (2 * range_m)
            def to_screen(p):
                world_y = p.y + origin_y if road.curve else p.y
                return ((p.x - center_x) * scale + (self.size - 1) / 2,
                        (world_y - center_y) * scale + (self.size - 1) / 2)
            points = [to_screen(road.sample_lateral(s, 0))
                      for s in range(math.floor(global_y - range_m),
                                     math.ceil(global_y + range_m) + 1, 3)]
            for a, b in pairwise(points):
                self._line(a, b, (204, 190, 150), max(4, self.size // 36))
            for a, b in pairwise(points):
                self._line(a, b, (48, 58, 65), max(2, self.size // 60))
        self._player(snapshot.player.heading)
        return self._upload()

    def _dot(self, x, y, color, radius):
        for oy in range(-radius, radius + 1):
            for ox in range(-radius, radius + 1):
                if ox * ox + oy * oy <= radius * radius:
                    self._put(x + ox, y + oy, color)

    def _player(self, heading):
        angle = math.radians(heading)
        # 世界北向固定；只旋转车辆箭头，不旋转地图。
        forward = (-math.sin(angle), math.cos(angle))
        right = (math.cos(angle), math.sin(angle))
        cx = cy = (self.size - 1) / 2
        tip = (cx + forward[0] * 9, cy + forward[1] * 9)
        rear = (cx - forward[0] * 6, cy - forward[1] * 6)
        left = (rear[0] - right[0] * 5, rear[1] - right[1] * 5)
        right_pt = (rear[0] + right[0] * 5, rear[1] + right[1] * 5)
        self._line(tip, left, (255, 255, 255), 2)
        self._line(left, right_pt, (255, 255, 255), 2)
        self._line(right_pt, tip, (255, 255, 255), 2)
