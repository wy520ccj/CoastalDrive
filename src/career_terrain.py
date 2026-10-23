"""回头弯周围的笛卡尔地形；每个全局三角形只属于一个道路分段，避免横向条带折叠。"""

import math
from functools import lru_cache

from career_courses import CareerCourse

STEP = 8


@lru_cache(maxsize=3)
def terrain(course_id):
    course = CareerCourse(course_id)
    points = course.points
    # 赛前/终点外道路仍使用原流送，地形覆盖两端额外200米。
    extended = [*points, course.sample(-200), course.sample(course.length+200)]
    x0, x1 = math.floor((min(p.x for p in extended)-220)/STEP), math.ceil((max(p.x for p in extended)+220)/STEP)
    y0, y1 = math.floor((min(p.y for p in extended)-220)/STEP), math.ceil((max(p.y for p in extended)+220)/STEP)
    grid = {}
    for row in range(y0, y1+1):
        for col in range(x0, x1+1):
            x, y = col*STEP, row*STEP
            s, d = course.project((x, y))
            p = course.sample(s)
            # 道旁保持原地基；远离赛道后才形成低丘，坡顶不随弯向折叠。
            bank = max(0., abs(d)-36.)
            height = p.z-.32+min(44., bank*.24)*(1+.15*math.sin(x*.018+y*.011))
            grid[col, row] = (x, y, height)
    meshes = {}
    for row in range(y0, y1):
        for col in range(x0, x1):
            for keys in (((col,row), (col+1,row), (col+1,row+1)),
                         ((col,row), (col+1,row+1), (col,row+1))):
                x, y = (sum(grid[key][axis] for key in keys)/3 for axis in (0, 1))
                s, d = course.project((x, y))
                if abs(d) > 220 or not -200 <= s <= course.length+200:
                    continue
                index = math.floor(s/200)
                vertices, faces = meshes.setdefault(index, ([], []))
                first = len(vertices)
                vertices.extend(grid[key] for key in keys)
                faces.append((first, first+1, first+2))
    return meshes


def segment_ground(course, index):
    return terrain(course.course_id).get(index, ([], []))
