"""设计阶段按米制路线参数绘制参考图，不改动生产路线。"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src'))
from career_courses import COURSES, CareerCourse

folder = Path(__file__).parent
data = json.loads((folder/'bend-profile.json').read_text(encoding='utf-8-sig'))
COURSES[data['course_id']] = tuple(tuple(row) for row in data['sections'])
course = CareerCourse(data['course_id'])
pts = [course.sample(s) for s in range(1801)]
im = Image.new('RGB', (1672, 941), '#eeede7')
d = ImageDraw.Draw(im)


def font(size):
    return ImageFont.truetype(str(ROOT/'assets/game/ui/fonts/SourceHanSansSC-Regular.otf'), size)


d.rectangle((0, 0, 1672, 110), fill='#101727')
d.text((42, 24), '平路连弯 · 路线设计', font=font(38), fill='white')
d.text((1210, 37), '1.8 公里 / 预算 5000', font=font(23), fill='white')
xs, ys = [p.x for p in pts], [p.y for p in pts]
scale = min(1000/(max(xs)-min(xs)), 680/(max(ys)-min(ys)))


def xy(point):
    return int(60+(point.x-min(xs))*scale), int(830-(point.y-min(ys))*scale)


d.line([xy(p) for p in pts], fill='#606773', width=max(10, round(13*scale)), joint='curve')
d.line([xy(p) for p in pts], fill='#f6f4e9', width=2)
for index, distance in enumerate(data['splits_m'], 1):
    x, y = xy(course.sample(distance))
    d.rectangle((x-8, y-8, x+8, y+8), fill='#ff4f1f')
    d.text((x+14, y-14), f'{index} / {distance}m', font=font(18), fill='#17202a')
x, y = xy(pts[0])
d.text((x+15, y-25), '起点', font=font(22), fill='#17202a')
labels = [('01  加速与第一次制动', '0—380 m'), ('02  快速左右转换', '380—520 m'),
          ('03  再加速、长弯、紧弯', '520—1180 m'), ('04  二次左右弯与高速出口', '1180—1800 m')]
for index, (title, subtitle) in enumerate(labels):
    y = 180+index*150
    d.text((1160, y), title, font=font(23), fill='#17202a')
    d.text((1160, y+45), subtitle, font=font(21), fill='#606773')
d.text((44, 885), '13米路面 · 通过实际曲率形成制动与转向需求 · 改装收益由实测确认', font=font(23), fill='#17202a')
im.save(folder/'01-bend-geometry-reference.png')
print('设计长度', course.length)
