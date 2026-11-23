"""生涯专用路线：手工安排弯型和高差，显示与Bullet共用米制弧长采样。"""

import math
from collections import defaultdict
from functools import lru_cache

from coastal_map import MapPoint

# 每段为弧长、航向变化、高差；段端曲率/坡度归零，避免拼接产生台阶。
COURSES = {
    'budget-ridge-long-waves': (
        (180, 0, 0), (200, -30, 14), (90, 80, 5), (60, 0, 0),
        *((8, 1.25, .12), (8, 1.25, -.12))*4,
        *((12, 1.25, .12), (12, 1.25, -.12))*4,
        *((10, 1.25, .12), (10, 1.25, -.12))*4,
        (60, 0, 0), (150, -110, -15), (80, 0, 0), (100, 100, -2), (100, -100, 2), (140, 0, 4)),
    'budget-ridge-suspension': (
        (180, 0, 0), (200, -30, 14), (90, 80, 5), (60, 0, 0),
        *((8, 2.5, .06), (8, 2.5, -.06))*4,
        *((12, 2.5, .06), (12, 2.5, -.06))*4,
        *((10, 2.5, .06), (10, 2.5, -.06))*4,
        (60, 0, 0), (150, -110, -15), (80, 0, 0), (100, 100, -2), (100, -100, 2), (140, 0, 4)),
    'budget-valley': (
        (100, 0, 0), (150, -20, -8), (100, 45, -10), (50, 0, 0),
        (100, -65, 0), (150, 70, 0), (100, 0, 8), (100, -45, 10), (150, 0, 0)),
    'budget-ridge-rough': (
        (180, 0, 0), (200, -30, 14), (90, 80, 5), (60, 0, 0),
        *((6, 1.5, .06), (6, 1.5, -.06))*10,
        (60, 0, 0), (150, -110, -15), (80, 0, 0), (100, 100, -2), (100, -100, 2), (260, 0, 4)),
    'budget-ridge': (
        (180, 0, 0), (200, -30, 14), (90, 80, 5), (60, 0, 0),
        (20, 0, .3), (20, 0, -.3), (20, 0, .3), (20, 0, -.3), (20, 0, .3), (20, 0, -.3),
        (60, 0, 0), (150, -110, -15), (80, 0, 0), (100, 100, -2), (100, -100, 2), (260, 0, 4)),
    'budget-bend': (
        (180, 0, 0), (130, -55, 0), (70, 0, 0), (70, 80, 0), (70, -80, 0),
        (220, 0, 0), (150, 85, 0), (80, 0, 0), (90, -110, 0), (120, 0, 0),
        (80, 65, 0), (80, -65, 0), (460, 0, 0)),
    'coast-club': (
        (140, 0, 0), (100, -55, 0), (70, 0, 0), (65, 95, 0),
        (65, -95, 0), (160, 80, 0), (80, 0, 0), (100, -55, 0), (120, 30, 0)),
    'ridge-club': (
        (140, 0, 8), (100, 50, 8), (100, 0, 5), (160, -140, -8),
        (100, 0, -10), (160, 140, -8), (100, 0, 6), (140, -50, 3)),
    'coast-final': (
        (150, 0, 0), (120, -60, 0), (80, 0, 0), (90, 100, 3), (90, -100, -3),
        (150, 60, 8), (120, 0, 10), (170, 140, -8), (140, 0, -8),
        (170, -140, -6), (120, 0, -6), (90, 65, 0), (90, -65, 0), (220, 0, 0)),
}


class CareerCourse:
    def __init__(self, course_id, seed=0):
        self.course_id, self.seed = course_id, seed
        sections = COURSES[course_id]
        x, y, heading = 0., 0., 0.
        z = {'coast-club': 0., 'budget-bend': 0., 'budget-valley': 30.}.get(course_id, 16.)
        self.points = [MapPoint(x, y, z, heading, 0.)]
        for length, turn, rise in sections:
            start_z = z
            for meter in range(1, length+1):
                mid = (meter-.5)/length
                eased = mid*mid*(3-2*mid)
                angle = math.radians(heading+turn*eased)
                dz = rise*6*mid*(1-mid)/length
                horizontal = math.sqrt(1-dz*dz)
                x -= math.sin(angle)*horizontal
                y += math.cos(angle)*horizontal
                t = meter/length
                z = start_z+rise*t*t*(3-2*t)
                gradient = rise*6*t*(1-t)/length
                self.points.append(MapPoint(x, y, z, heading+turn*t*t*(3-2*t),
                                            math.degrees(math.asin(gradient))))
            heading += turn
        self.length = len(self.points)-1
        self.grid = defaultdict(list)
        for index in range(0, len(self.points), 8):
            p = self.points[index]
            self.grid[math.floor(p.x/32), math.floor(p.y/32)].append(index)
        self.sample = lru_cache(maxsize=8192)(self.sample)

    def sample(self, distance, lateral=0.):
        if distance < 0 or distance > self.length:
            p, extra = ((self.points[0], distance) if distance < 0 else
                        (self.points[-1], distance-self.length))
            angle = math.radians(p.heading)
            x, y, z, heading, grade = p.x-extra*math.sin(angle), p.y+extra*math.cos(angle), p.z, p.heading, 0.
        else:
            index = min(int(distance), self.length-1)
            a, b, t = self.points[index], self.points[index+1], distance-index
            x, y, z, heading, grade = (low+(high-low)*t for low, high in zip(
                (a.x, a.y, a.z, a.heading, a.grade), (b.x, b.y, b.z, b.heading, b.grade)))
            angle = math.radians(heading)
        return MapPoint(x+lateral*math.cos(angle), y+lateral*math.sin(angle), z, heading, grade)

    def project(self, position):
        x, y = position[:2]
        cell = math.floor(x/32), math.floor(y/32)
        candidates = [index for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                      for index in self.grid.get((cell[0]+dx, cell[1]+dy), ())]
        if not candidates:
            candidates = range(0, len(self.points), 8)
        nearest = min(candidates, key=lambda i: (self.points[i].x-x)**2+(self.points[i].y-y)**2)
        best, distance = math.inf, 0.
        for index in range(max(0, nearest-12), min(self.length, nearest+13)):
            a, b = self.points[index], self.points[index+1]
            dx, dy = b.x-a.x, b.y-a.y
            t = max(0., min(1., ((x-a.x)*dx+(y-a.y)*dy)/(dx*dx+dy*dy)))
            error = (x-a.x-t*dx)**2+(y-a.y-t*dy)**2
            if error < best:
                best, distance = error, index+t
        # 两端延续真实切线，供出生区和终点外的原分段世界使用。
        for p, origin, before in ((self.points[0], 0., True), (self.points[-1], self.length, False)):
            angle = math.radians(p.heading)
            extra = -(x-p.x)*math.sin(angle)+(y-p.y)*math.cos(angle)
            if (before and extra < 0) or (not before and extra > 0):
                error = ((x-p.x)*math.cos(angle)+(y-p.y)*math.sin(angle))**2
                if error < best:
                    best, distance = error, origin+extra
        p = self.sample(distance)
        angle = math.radians(p.heading)
        return distance, (x-p.x)*math.cos(angle)+(y-p.y)*math.sin(angle)

    def on_asphalt(self, x, y):
        return abs(self.project((x, y))[1]) <= 6.75
