"""端口乘积保留fma低位，再用补偿求和与fma重建末速度。"""
from pathlib import Path
root=Path.cwd();p=root/'logs/physics/PHYS-DESIGN-01-wall/build-stable-map.py'
s=p.read_text(encoding='utf-8').replace('PHYS-DESIGN-01-wall/stable-map','PHYS-DESIGN-01-wall/accurate-map')
old='''            double updates[4]={projected[a],-data->dt*port_values[0]*branch->mc[a],
                -data->dt*port_values[2]*branch->ml[a],-data->dt*port_values[1]*branch->mg[a]};
            end[a]=compensated(updates,4);'''
new='''            double updates[6],torques[3]={port_values[0],port_values[2],port_values[1]},
                responses[3]={branch->mc[a],branch->ml[a],branch->mg[a]};
            for (int j=0; j<3; ++j) {
                updates[2*j]=torques[j]*responses[j];
                updates[2*j+1]=fma(torques[j],responses[j],-updates[2*j]);
            }
            end[a]=fma(-data->dt,compensated(updates,6),projected[a]);'''
assert old in s
s=s.replace(old,new).replace('_stable_map','_accurate_map')
exec(compile(s,__file__,'exec'))
