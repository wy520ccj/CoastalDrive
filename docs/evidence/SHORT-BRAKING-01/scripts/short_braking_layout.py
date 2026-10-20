import argparse,json,sys
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from application import CoastalDrive
from braking_lesson import BrakingResult
from session import Phase
from race import GameMode
from panda3d.core import Filename
from vehicle_workspace import WorkspaceVehicle
from workshop import build_config
p=argparse.ArgumentParser();p.add_argument('--input',type=Path);p.add_argument('--output',type=Path);p.add_argument('--size',type=int,nargs=2);a=p.parse_args();a.output.mkdir()
case=json.loads((a.input/'2/summary.json').read_text(encoding='utf-8'))
app=CoastalDrive(smoke=True,output=a.output,lab_output=a.output/'reports',workspace_vehicle=WorkspaceVehicle('reference-rwd',build_config(2,False)),render_size=tuple(a.size))
app.taskMgr.remove('finish-smoke');app.taskMgr.remove('drive-update')
try:
 app.back_to_menu();app.choose_braking_lesson(GameMode.SHORT_BRAKING);app.start_braking_lesson()
 for _ in range(360):app.session.tick()
 highway=app.session.highway.snapshot
 for name,warning in [('actual-result',''),('save-warning','本次成绩未保存；请检查存储目录，可继续练习。')]:
  result=replace(BrakingResult(**case['result']),save_notice=warning)
  app.session.highway.snapshot=replace(highway,braking=result,elapsed=case['rows']/120,finished=True,running=False,succeeded=True)
  app.session.phase=Phase.RESULTS;app._shown_phase=None;app.refresh_panel();app.main_menu.resize(app.getAspectRatio());app.hud.resize(app.getAspectRatio())
  for _ in range(6):app.taskMgr.step()
  app.graphicsEngine.syncFrame();assert app.win.getScreenshot().write(Filename.fromOsSpecific(str((a.output/(name+'.png')).resolve())))
 app.open_brake_tuning();app.tire_tuning.activate(2)
 assert not app.tire_tuning.root.isHidden() and not app.main_menu.root.isHidden() and app.panel.isHidden()
 for _ in range(6):app.taskMgr.step()
 app.graphicsEngine.syncFrame();assert app.win.getScreenshot().write(Filename.fromOsSpecific(str((a.output/'brake-preview.png').resolve())))
 (a.output/'summary.json').write_text(json.dumps({'passed':True,'scope':'已保存实际银牌结算静态复载；长保存失败文字为明确UI夹具，无新完整驾驶','input':str(a.input),'size':a.size},ensure_ascii=False,indent=2),encoding='utf-8')
finally:app.close_game()
