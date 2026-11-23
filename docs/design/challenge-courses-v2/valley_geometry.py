"""山谷预算路线的精确设计参考；只在本设计进程加载规格。"""

import json
import sys
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src'))
from career_courses import COURSES, CareerCourse

folder = Path(__file__).parent
data = json.loads((folder/'valley-profile.json').read_text(encoding='utf-8'))
COURSES[data['course_id']] = tuple(tuple(row) for row in data['sections'])
course = CareerCourse(data['course_id'])
offset = data['start_height_m']-course.points[0].z
course.points = [replace(point, z=point.z+offset) for point in course.points]
im = Image.new('RGB', (1672, 1050), '#eeede7')
draw = ImageDraw.Draw(im)


def font(size):
    return ImageFont.truetype(str(ROOT/'assets/game/ui/fonts/SourceHanSansSC-Regular.otf'), size)


draw.rectangle((0, 0, 1672, 100), fill='#101727')
draw.text((40, 22), '山谷节奏 · 米制路线设计', font=font(34), fill='white')
draw.text((1170, 32), '1.0 公里 / 预算 5000', font=font(23), fill='white')
xs, ys = [p.x for p in course.points], [p.y for p in course.points]
scale = min(930/(max(ys)-min(ys)), 430/(max(xs)-min(xs)))


def xy(point):
    return round(65+(point.y-min(ys))*scale), round(190+(point.x-min(xs))*scale)


draw.line([xy(p) for p in course.points], fill='#606773', width=max(8, round(13.5*scale)), joint='curve')
for i, (start, end, name) in enumerate(data['zones']):
    color = ('#476e92', '#bd623e', '#98743a', '#476e92', '#476e92')[i]
    draw.line([xy(course.sample(s)) for s in range(start, end+1)], fill=color, width=5)
    draw.text((1100, 150+i*90), f'{i+1:02}  {name}', font=font(23), fill='#17202a')
    draw.text((1150, 182+i*90), f'{start}—{end} m', font=font(18), fill='#606773')
for distance in (0, *data['splits_m']):
    x, y = xy(course.sample(distance))
    draw.ellipse((x-7, y-7, x+7, y+7), fill='#ff4f1f')
    draw.text((x+12, y-17), f'{distance}m', font=font(19), fill='#17202a')
draw.text((55, 675), '250米测速门 ≥60km/h     400—650米全段 35—50km/h', font=font(23), fill='#17202a')
draw.text((55, 735), '高程 / m', font=font(20), fill='#17202a')
draw.line((70, 950, 1600, 950), fill='#a5a9ac', width=2)
draw.line([(round(70+1530*s/1000), round(940-(p.z-10)*9))
           for s, p in enumerate(course.points)], fill='#476e92', width=4)
for distance in (0, 100, 250, 350, 400, 650, 750, 850, 1000):
    point = course.sample(distance)
    x, y = round(70+1530*distance/1000), round(940-(point.z-10)*9)
    draw.text((max(70, min(1520, x-20)), 965), f'{distance}', font=font(17), fill='#606773')
    draw.text((max(70, min(1520, x-20)), y-25), f'{point.z:g}m', font=font(17), fill='#17202a')
draw.text((55, 1010), '13.5米路宽 · 下谷18米 / 再爬升18米 · 原测速门与限速区间保持', font=font(20), fill='#17202a')
im.save(folder/'05-valley-geometry-reference.png')
print('length', course.length, 'height', min(p.z for p in course.points), max(p.z for p in course.points),
      'max_grade', max(abs(p.grade) for p in course.points))
