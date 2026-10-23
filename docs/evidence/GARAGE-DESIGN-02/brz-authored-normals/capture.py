import os,sys,json
from dataclasses import replace,asdict
from pathlib import Path
sys.path.insert(0,'src')
from application import CoastalDrive
from panda3d.core import Filename
import ui.workshop_vehicle as workshop
root=Path.cwd();folder=root/'logs/validation/GARAGE-DESIGN-02-paint-normals';out=folder/'render';out.mkdir(exist_ok=False)
os.environ['LOCALAPPDATA']=str(out/'user');app=CoastalDrive(smoke=True,output=out,render_size=(1280,720));app.taskMgr.remove('finish-smoke');app.taskMgr.remove('drive-update')
before=asdict(app.session.current);names=[]
def shot(name):
 for _ in range(8): app.taskMgr.step()
 app.graphicsEngine.syncFrame();app.win.getScreenshot().write(Filename.fromOsSpecific(str(out/name)));names.append(name);assert asdict(app.session.current)==before
try:
 app.open_career_collection();app.career_action('garage-car','game-tuned');view=app.workshop_vehicle
 for angle in (55.,35.):
  view.orbit(angle-view.studio_angle);shot('baseline-'+str(int(angle))+'.png')
 original=workshop.vehicle_for_design
 workshop.vehicle_for_design=lambda design,current:replace(original(design,current),visual=str(folder/'subaru_brz.bam'))
 view.identity=None;view.framing_identity=None;view.floor_reflection.removeNode();view.floor_reflection=None
 app.career_action('garage-car','game-tuned')
 for angle in (55.,35.):
  view.orbit(angle-view.studio_angle);shot('authored-'+str(int(angle))+'.png')
 (out/'summary.json').write_text(json.dumps(dict(passed=True,captures=names,new_driving_steps=0,scope='isolated authored normal candidate; no runtime files or physics changed'),indent=2)+'\n')
 print('passed',names)
finally:app.close_game()
