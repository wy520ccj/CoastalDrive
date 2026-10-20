from pathlib import Path
import os,sys,json,hashlib
from dataclasses import fields, replace
root=Path.cwd();sys.path[:0]=[str(root/'src'),str(root/'tools')]
from application import CoastalDrive
from race import GameMode
from session import Phase
from highway_run import HighwayResult
from slalom_lesson import SlalomResult
from vehicle_workspace import WorkspaceVehicle
from workshop_cornering import build_config
from lab_runtime import runtime_fingerprint
from lab_records import model_fingerprint
from panda3d.core import Filename
source=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir();os.environ['LOCALAPPDATA']=str(out/'user-data')
def sources():return {**model_fingerprint(),'preview-tool':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
summary={'passed':False,'source_start':sources(),'runtime_start':runtime_fingerprint(),'scope':'原真实课题结果的静态UI复载，未新跑完整驾驶；车型位置仅当前初始化场景，图中结算来自原真实记录','human_gate':'pending'}
app=CoastalDrive(smoke=True,output=out,workspace_vehicle=WorkspaceVehicle('reference-rwd',build_config(0,False,False)),render_size=tuple(map(int,sys.argv[3:5])))
app.taskMgr.remove('finish-smoke');app.taskMgr.remove('drive-update')
try:
 app.back_to_menu();app.choose_slalom_lesson(GameMode.FAST_SLALOM);app.start_slalom_lesson()
 for _ in range(360):app.session.tick()
 app.countdown.update('results',0,0.)
 for index in (0,3):
  row=json.loads((source/str(index)/'summary.json').read_text(encoding='utf-8'))
  result=SlalomResult(**{f.name:tuple(row['result'][f.name]) if isinstance(row['result'][f.name],list) else row['result'][f.name] for f in fields(SlalomResult)})
  if len(sys.argv)>5 and index==3:result=replace(result,save_notice='本次过门成绩未保存，请检查存储目录。',new_best=False)
  app.session.highway.snapshot=HighwayResult(finished=True,challenge=True,succeeded=result.succeeded,slalom=result,elapsed=row['rows']/120,reason=result.reason)
  app.session.phase=Phase.RESULTS;app._shown_phase=None;app.refresh_panel()
  app.main_menu.resize(app.getAspectRatio());app.hud.resize(app.getAspectRatio())
  before=app.session.current
  for _ in range(6):app.taskMgr.step()
  app.graphicsEngine.syncFrame();assert app.session.current==before
  assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(out/(str(index)+'-result.png'))))
 summary.update(passed=True,source_end=sources(),runtime_end=runtime_fingerprint())
finally:
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');app.close_game()
