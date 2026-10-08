import json
import sys
import types
from dataclasses import fields, is_dataclass
from pathlib import Path
root = Path(__file__).resolve().parents[3]
folder = root / 'logs/physics/PHYS-PERF-01'
sys.path[:0] = [str(root / 'src'), str(folder / 'triangle-packet-baseline')]
import _triangle_packet_old
import suspension_contacts
from suspension_geometry import CylinderSurface
baseline = types.ModuleType('_original_cylinder_surface')
sys.modules[baseline.__name__] = baseline
exec(compile((folder / 'surface-entry-original.py').read_text(encoding='utf-8'), 'a2f743e-original-surface', 'exec'), baseline.__dict__)
counts = {'ray_queries': 0, 'original_surfaces': 0, 'current_surfaces': 0, 'direct_entries': 0}
def hex_tree(value):
    if is_dataclass(value):
        return {field.name: hex_tree(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, (tuple, list)):
        return [hex_tree(item) for item in value]
    return value
original = _triangle_packet_old.surface_ray_hits
current = suspension_contacts.surface_ray_hits
def old_surface(*args):
    counts['original_surfaces'] += 1
    return baseline.CylinderSurface(*args)
def new_surface(*args):
    counts['current_surfaces'] += 1
    return CylinderSurface(*args)
def audited(surfaces, start, end, axis, origin, radius, reach, width, shoulder, crown, surface_class, contact_class, edge_entry, box_entry, relative):
    old_surfaces = [part[:7] for part in surfaces]
    expected = original(old_surfaces, start, end, axis, origin, radius, reach, width, shoulder, crown, old_surface, contact_class, relative)
    actual = current(surfaces, start, end, axis, origin, radius, reach, width, shoulder, crown, new_surface, contact_class, edge_entry, box_entry, relative)
    assert hex_tree(actual) == hex_tree(expected), (counts, start, end, axis)
    counts['ray_queries'] += 1
    return actual
suspension_contacts.surface_ray_hits = audited
for plane in (None, ((0.,0.,1.),.03), ((.3,.4,.8660254037844386),-.1)):
    values = {'half': (1.,1.,.1), 'radius': .01, 'axes': ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)),
              'offset': (.15,-.24,.03), 'wheel_radius': .33, 'reach': 2., 'width': .205,
              'shoulder': .01, 'wheel_axis': (1.,0.,0.), 'crown': .003, 'plane': plane}
    old = baseline.CylinderSurface(**values)
    new = CylinderSurface(**values)
    for x in (-1.2,-.95,0.,.95,1.2):
        for y in (0.,.95,1.1):
            for axis in ((1.,0.,0.),(0.,1.,0.)):
                arguments = ((x,y,1.),(x,y,-1.),axis)
                assert hex_tree(new.entry(*arguments)) == hex_tree(old.entry(*arguments)), (plane,arguments)
                counts['direct_entries'] += 1
from simulation import Simulation, Control
from vehicle_designs import GR86_DESIGN
from driver_assist import GAME_INPUT
sim = Simulation(17, track='coastal', traffic_count=8, config=GR86_DESIGN, input_config=GAME_INPUT)
try:
    for tick in range(24):
        sim.step(Control(throttle=.3))
finally:
    sim.close()
report = {'baseline': 'independent old surface-ray C DLL plus a2f743e original Python CylinderSurface.entry',
          'all_fields_hex_and_references_equal': True, 'counts': counts,
          'scope': '一次组对照；未重跑pytest/T1/三种子/48拍/profile。'}
(folder / 'surface-entry-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
