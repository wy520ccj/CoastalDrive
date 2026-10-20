from pathlib import Path
import sys,os,json,hashlib
root=Path.cwd();sys.path[:0]=[str(root/'src'),str(root/'tools')]
from application import CoastalDrive
from race import GameMode
from panda3d.core import Filename
from fast_slalom_check import sources
from lab_runtime import runtime_fingerprint
out=Path(sys.argv[1]).resolve();out.mkdir();os.environ['LOCALAPPDATA']=str(out/'user-data')
app=CoastalDrive(smoke=True,output=out,render_size=(1024,768))
app.taskMgr.remove('finish-smoke');app.taskMgr.remove('drive-update')
summary={'passed':False,'source_start':sources(),'runtime_start':runtime_fingerprint(),'scope':'最终倒计时HUD静态图，未新跑完整课题','human_gate':'pending'}
try:
 app.back_to_menu();app.choose_slalom_lesson(GameMode.FAST_SLALOM);app.buttons[0]['command']()
 app.refresh_panel()
 app.lab_return_button.setX(app.getAspectRatio()-.44)
 app.ghost_button.setX(app.getAspectRatio()-.44)
 app.main_menu.resize(app.getAspectRatio());app.hud.resize(app.getAspectRatio())
 app.hud.update(app.session.current,app.session.race.snapshot,app.session.highway.snapshot,track='endless',countdown='准备',notice='')
 assert '70–80' in app.hud.detail.getText()
 before=app.session.current
 for _ in range(6):app.taskMgr.step()
 app.graphicsEngine.syncFrame();assert before==app.session.current
 assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(out/'countdown.png')))
 summary.update(passed=True,source_end=sources(),runtime_end=runtime_fingerprint())
 assert summary['source_start']==summary['source_end'] and summary['runtime_start']==summary['runtime_end']
finally:
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');app.close_game()
