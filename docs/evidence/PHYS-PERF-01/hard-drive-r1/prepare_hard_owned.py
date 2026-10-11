from pathlib import Path
import shutil

root = Path.cwd()
out = root/'logs/performance/hard-drive-r1/owned/src'
shutil.copytree(root/'src',out,ignore=shutil.ignore_patterns('__pycache__'))
p = out/'physics_workers.py'
s = p.read_text(encoding='utf-8')
s = s.replace("_job_header = struct.Struct('<QQ')", "_job_header = struct.Struct('<QQq')")
s = s.replace('identifier,configuration_id = _job_header.unpack_from(payload,1)', 'identifier,configuration_id,vehicle_slot = _job_header.unpack_from(payload,1)')
s = s.replace("return 'numeric',identifier,configuration_id,from_bytes", "return 'numeric',identifier,configuration_id,vehicle_slot,from_bytes")
s = s.replace('def _solve_vehicle(request, reference):','def _solve_vehicle(request, reference, vehicle_slot):')
s = s.replace('_worker_candidates.setdefault(request.config,{})','_worker_candidates.setdefault((request.config,vehicle_slot),{})')
s = s.replace('_,identifier,configuration_id,request = message','_,identifier,configuration_id,vehicle_slot,request = message')
s = s.replace('identifier, request, reference, configuration_id, configuration = message','identifier, request, reference, configuration_id, configuration, vehicle_slot = message')
s = s.replace('_solve_vehicle(request, reference)','_solve_vehicle(request, reference, vehicle_slot)')
s = s.replace('def submit(self, request, shapes, material):','def submit(self, request, shapes, material, *, vehicle_slot=-1):')
s = s.replace('index = identifier % len(self.processes)','index = (identifier if vehicle_slot == -1 else vehicle_slot) % len(self.processes)')
s = s.replace('_job_header.pack(identifier,configuration_id)','_job_header.pack(identifier,configuration_id,vehicle_slot)')
s = s.replace('(identifier,frozen,self.reference,configuration_id,configuration)', '(identifier,frozen,self.reference,configuration_id,configuration,vehicle_slot)')
p.write_text(s,encoding='utf-8')
p = out/'world_step.py'
s = p.read_text(encoding='utf-8').replace('workers.submit(inputs, static_shapes, material)','workers.submit(inputs, static_shapes, material, vehicle_slot=i)')
p.write_text(s,encoding='utf-8')
