from pathlib import Path
import sys,json,os
root=Path.cwd();sys.path[:0]=[str(root/'src'),str(root/'tools')]
from application import CoastalDrive
from lab_records import load_record
from lab_runtime import runtime_fingerprint
from lab_driving_car_check import sources,finish
from vehicle_workspace import WorkspaceVehicle
from panda3d.core import Filename
source=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir()
os.environ['LOCALAPPDATA']=str(out/'user-data')
summary={'passed':False,'source_start':sources(),'runtime_start':runtime_fingerprint(),'scope':'复载本批真实A/B后的静态界面；不新跑参考物理或道路驾驶','human_gate':'pending'}
app=CoastalDrive(smoke=True,output=out,workspace_vehicle=WorkspaceVehicle.load(source/'test-workspace-vehicle.json'),render_size=tuple(map(int,sys.argv[3:5])))
app.taskMgr.remove('finish-smoke');app.taskMgr.remove('drive-update')
try:
 app.open_vehicle_lab();finish(app,'lab');lab=app.lab
 def capture(name):
  before=lab.record.snapshots
  lab.resize()
  for _ in range(6):app.taskMgr.step()
  app.graphicsEngine.syncFrame();assert lab.record.snapshots==before
  assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(out/(name+'.png'))))
 assert lab.import_record(source/'A')
 lab.baseline=load_record(source/'A');lab.refresh_plots();lab.show_sample(960)
 lab.toggle_record_menu();capture('load-menu')
 lab.stage_driving_vehicle();assert lab.engineered_config.lateral_stiffness==70000.
 capture('prepared-current-car-old-curves')
 assert lab.import_record(source/'B')
 lab.baseline=load_record(source/'A');lab.present_summary(lab.record.metadata['summary']);lab.refresh_plots();lab.show_sample(960)
 capture('new-B-and-old-A')
 summary.update(passed=True,source_end=sources(),runtime_end=runtime_fingerprint())
 assert summary['source_start']==summary['source_end'] and summary['runtime_start']==summary['runtime_end']
finally:
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');app.close_game()
