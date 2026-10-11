import json
import math
from bisect import bisect_left
from itertools import pairwise
from pathlib import Path

root = Path('logs/performance/traffic-native-r1')

def summarize(path):
    record = json.loads(path.read_text())
    published = record['published']
    speed = {}
    for a,b in pairwise(published):
        if b[1] == a[1]+1:
            p,q = a[3][0],b[3][0]
            speed[b[1]] = math.dist((p[0],p[1]+a[2],p[2]),(q[0],q[1]+b[2],q[2]))*120
    ratios, relative, skipped = [],[],0
    for a,b in pairwise(record['rendered']):
        elapsed = b[0]-a[0]
        if speed.get(b[1],0) < 10:
            continue
        if elapsed > .05:
            skipped += 1
            continue
        p,q = a[3][0],b[3][0]
        distance = math.dist((p[0],p[1]+a[2],p[2]),(q[0],q[1]+b[2],q[2]))
        ratios.append(distance/elapsed/speed[b[1]])
        da = math.hypot(a[4][0]-p[0],a[4][1]-p[1])
        db = math.hypot(b[4][0]-q[0],b[4][1]-q[1])
        relative.append(abs(db-da)*1000)
    def quantiles(values):
        values = sorted(values)
        return {str(p):values[int((len(values)-1)*p)] for p in (.05,.5,.95,.99)}
    return {'render_velocity_ratio':quantiles(ratios),
            'relative_camera_distance_change_mm':quantiles(relative),
            'velocity_outside_10_percent':sum(abs(v-1)>.1 for v in ratios)/len(ratios),
            'samples':len(ratios),'long_frames_excluded':skipped}

old = json.loads((root/'window-integrated-short/presentation.json').read_text())
new = json.loads((root/'window-fixed-presentation/presentation.json').read_text())
old_positions = {t:(o,p) for _,t,o,p in old['published']}
common = [(t,(o,p)==old_positions[t]) for _,t,o,p in new['published'] if t in old_positions]
result = {'kind':'observed presentation diagnostic; foreground validity stays in window report',
          'old':summarize(root/'window-integrated-short/presentation.json'),
          'fixed':summarize(root/'window-fixed-presentation/presentation.json'),
          'common_physics_position_snapshots':len(common),
          'complete_position_arrays_equal':all(equal for _,equal in common)}
continuous = json.loads((root/'window-continuous-camera/presentation.json').read_text())
same = [(t,(o,p)==old_positions[t]) for _,t,o,p in continuous['published'] if t in old_positions]
result['continuous_camera'] = summarize(root/'window-continuous-camera/presentation.json')
result['continuous_common_snapshots'] = len(same)
result['continuous_positions_equal'] = all(equal for _,equal in same)
readonly = json.loads((root/'window-readonly-final/presentation.json').read_text())
same = [(t,(o,p)==old_positions[t]) for _,t,o,p in readonly['published'] if t in old_positions]
result['readonly_camera'] = summarize(root/'window-readonly-final/presentation.json')
result['readonly_common_snapshots'] = len(same)
result['readonly_positions_equal'] = all(equal for _,equal in same)
current = json.loads((root/'window-owner-production/presentation.json').read_text())
result['owner_production'] = summarize(root/'window-owner-production/presentation.json')
published = current['published']
reference = [(b[3][0][1],math.dist(a[3][0],b[3][0])*120) for a,b in pairwise(published) if b[1]==a[1]+1]
ys = [p[0] for p in reference]
draw = json.loads((root/'window-owner-production/draw-poses.json').read_text())
ratios = {name:[] for name in ('car_wall','car_frame','camera_wall','camera_frame')}
for a,b in pairwise(draw):
    index = min(len(reference)-1,bisect_left(ys,b[2][1]))
    velocity = reference[index][1]
    if velocity < 10 or b[0]-a[0] > .05 or b[1] <= a[1]:
        continue
    for object_index,name in ((2,'car'),(3,'camera')):
        distance = math.dist(a[object_index],b[object_index])
        for time_index,axis in ((0,'wall'),(1,'frame')):
            ratios[name+'_'+axis].append(distance/(b[time_index]-a[time_index])/velocity)
result['actual_draw_velocity_ratio'] = {name:{
    'p5':sorted(values)[int((len(values)-1)*.05)],
    'p50':sorted(values)[int((len(values)-1)*.5)],
    'p95':sorted(values)[int((len(values)-1)*.95)],
    'outside_10_percent':sum(abs(v-1)>.1 for v in values)/len(values),
    'samples':len(values)} for name,values in ratios.items()}
(root/'presentation-comparison.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
