"""山脊样板米制俯视与高程参考，仅设计进程临时载入路线。"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src'))
from career_courses import COURSES, CareerCourse

folder = Path(__file__).parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--profile', default='ridge-profile.json')
parser.add_argument('--output', default='02-ridge-geometry-reference.png')
parser.add_argument('--caption', default='13.5米原路宽 · 19米爬升 · 0.3米连续缓起伏 · 真实下坡与弯道，不加隐藏限速')
args = parser.parse_args()
data = json.loads((folder/args.profile).read_text(encoding='utf-8'))
COURSES[data['course_id']] = tuple(tuple(row) for row in data['sections'])
course = CareerCourse(data['course_id'])
points = course.points
im = Image.new('RGB', (1672, 1050), '#eeede7')
draw = ImageDraw.Draw(im)
colors = ('#476e92', '#bd623e', '#98743a', '#bd623e', '#476e92', '#476e92')


def font(size):
    return ImageFont.truetype(str(ROOT/'assets/game/ui/fonts/SourceHanSansSC-Regular.otf'), size)


draw.rectangle((0, 0, 1672, 100), fill='#101727')
draw.text((40, 22), '山脊冲刺 · 米制路线设计', font=font(34), fill='white')
draw.text((1170, 32), '1.4 公里 / 预算 5000', font=font(23), fill='white')
xs, ys = [p.x for p in points], [p.y for p in points]
scale = min(930/(max(ys)-min(ys)), 470/(max(xs)-min(xs)))


def xy(p):
    return round(65+(p.y-min(ys))*scale), round(200+(p.x-min(xs))*scale)


draw.line([xy(p) for p in points], fill='#606773', width=max(8, round(13.5*scale)), joint='curve')
for index, (start, end, name) in enumerate(data['zones']):
    draw.line([xy(course.sample(s)) for s in range(start, end+1)], fill=colors[index], width=5)
    draw.text((1100, 145+index*86), f'{index+1:02}  {name}', font=font(23), fill='#17202a')
    draw.text((1150, 177+index*86), f'{start}—{end} m', font=font(18), fill='#606773')
for distance in (0, *data['splits_m']):
    x, y = xy(course.sample(distance))
    draw.ellipse((x-7, y-7, x+7, y+7), fill='#ff4f1f')
    draw.text((x+12, y-17), f'{distance}m', font=font(19), fill='#17202a')
draw.text((55, 735), '高程 / m', font=font(20), fill='#17202a')
draw.line((70, 950, 1600, 950), fill='#a5a9ac', width=2)


def elevation(p, distance):
    return round(70+1530*distance/1400), round(950-(p.z-16)*8)


draw.line([elevation(p, s) for s, p in enumerate(points)], fill='#476e92', width=4)
for distance in (0, 380, 530, 650, 860, 1140, 1400):
    x, y = elevation(course.sample(distance), distance)
    draw.text((max(70, min(1520, x-20)), 965), f'{distance}', font=font(17), fill='#606773')
    draw.line((x, y+6, x, 950), fill='#d0cfc9', width=1)
draw.text((55, 1010), args.caption, font=font(20), fill='#17202a')
im.save(folder/args.output)
print('length', course.length, 'height', min(p.z for p in points), max(p.z for p in points),
      'max_grade', max(abs(p.grade) for p in points))
