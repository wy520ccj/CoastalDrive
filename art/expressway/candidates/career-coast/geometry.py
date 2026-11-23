import math
from functools import lru_cache
from career_courses import CareerCourse
from environment.expressway import smooth


def _career_shoreline(y):
    """沿海生涯的世界岸线；地形与水面共用，不跟着回头弯翻转。"""
    return 30+.12*y+20*math.sin(y/240)


@lru_cache(maxsize=3)
def _career_terrain(course_id):
    """只复制沿海表现网格，原地形仍由Bullet使用。"""
    from career_terrain import terrain

    original = terrain(course_id)
    if course_id not in ('coast-club', 'coast-final'):
        return original
    curve = CareerCourse(course_id)
    heights = {}
    result = {}
    for index, (vertices, faces) in original.items():
        changed = []
        for x, y, z in vertices:
            key = x, y
            if key not in heights:
                _station, lateral = curve.project((x, y))
                # 48米涵盖原35米树带与一个8米网格对角线，插值也不侵入近路。
                shore = smooth(-12, 24, x-_career_shoreline(y))
                fall = smooth(48, 120, abs(lateral))
                # 不把原来持续上升的山坡一起混入下降坡，否则中间会拱出挡海的高脊。
                bank = min(44., max(0., abs(lateral)-36)*.24)
                lip = min(44., max(0., min(abs(lateral), 48)-36)*.24)
                edge = z-(bank-lip)*(1+.15*math.sin(x*.018+y*.011))
                heights[key] = z if abs(lateral) <= 48 or shore == 0 else z*(1-shore)+(edge*(1-fall)-8*fall)*shore
            changed.append((x, y, heights[key]))
        result[index] = changed, faces
    return result


def _career_water_surface(curve):
    """有限路线只需一片低面数海面，不随路段重复或沿弯道折叠。"""
    bottom = min(p.y for p in curve.points)-1400
    top = max(p.y for p in curve.points)+1400
    count = math.ceil((top-bottom)/80)
    vertices, faces = [], []
    right = max(p.x for p in curve.points)+2200
    for row in range(count+1):
        y = bottom+(top-bottom)*row/count
        vertices.extend(((_career_shoreline(y)-30, y, -3), (right, y, -3)))
        if row:
            a = (row-1)*2
            faces.extend(((a, a+1, a+3), (a, a+3, a+2)))
    return vertices, faces
