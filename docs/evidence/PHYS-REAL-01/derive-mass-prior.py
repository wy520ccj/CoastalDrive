"""首款实车的质量分布推导初值；不建立或加载VehicleConfig。"""
import hashlib
import json
from pathlib import Path

root = Path('docs/evidence/PHYS-REAL-01')
source_file = root / 'source-preparation.json'
source = json.loads(source_file.read_text(encoding='utf-8'))
fields = source['manufacturer_fields']
mass = source['published_test']['si_mass_kg']
length, width, height, bottom, wheelbase = (fields[k]['value']/1000 for k in
    ('length', 'width', 'height', 'ground_clearance', 'wheelbase'))
share = fields['front_weight_share']['value']
y_mean = wheelbase*(share-.5)
y_variance = length**2/12-y_mean**2
x_variance = width**2/12
span = height-bottom
cases = []
for cg in (.40, .45, .50):
    u = (cg-bottom)/span
    beta = (1-u)/u
    z_variance = span**2*u**2*(1-u)/(1+u)
    cases.append({'assumed_center_of_mass_height_m':cg,
        'vertical_density_beta':beta,
        'variance_xyz_m2':[x_variance,y_variance,z_variance],
        'whole_rigid_pose_inertia_xyz_kg_m2':[
            mass*(y_variance+z_variance), mass*(x_variance+z_variance), mass*(x_variance+y_variance)]})
record = {'status':'engineering prior only; not manufacturer inertia and not a loadable config',
    'candidate':source['candidate'],
    'source_file_sha256':hashlib.sha256(source_file.read_bytes()).hexdigest(),
    'inputs':{'curb_mass_kg':mass,'body_length_m':length,'body_width_without_mirrors_m':width,
        'body_top_m':height,'body_bottom_m':bottom,'wheelbase_m':wheelbase,'front_weight_share':share},
    'coordinate_definition':'X lateral, Y forward, Z up; body geometry centre is Y=0',
    'derived_center_of_mass_y_m':y_mean,
    'front_hub_y_relative_to_CG_m':wheelbase*(1-share),
    'rear_hub_y_relative_to_CG_m':-wheelbase*share,
    'longitudinal_density_gradient_per_m':12*y_mean/length**2,
    'assumptions':['Mass density uniform across width',
        'Longitudinal density proportional to 1+k*y, preserving the sourced 53:47 static load',
        'Vertical density follows Beta(1,beta) inside sourced ground-clearance/body-top bounds',
        'Three CG heights are engineering sensitivity candidates, not measured heights',
        'No driver or instrument payload is added'],
    'cases':cases,
    'implementation_boundary':'This is total rigid-pose inertia. Before mapping to body_inertia, reconcile explicitly modelled wheel/engine/shaft axial inertia and calibrate with the same standard experiments.'}
(root/'mass-distribution-prior.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'CG_y_m':y_mean,'cases':cases},ensure_ascii=False))
