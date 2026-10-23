import argparse,json,os,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
from panda3d.core import Filename
from application import CoastalDrive
from career_run import CareerResult
p=argparse.ArgumentParser();p.add_argument('--output',type=Path);p.add_argument('--size',nargs=2,type=int);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);os.environ['LOCALAPPDATA']=str(out/'user')
app=CoastalDrive(smoke=True,output=out,render_size=tuple(args.size));app.taskMgr.remove('finish-smoke');app.taskMgr.remove('drive-update');names=[]
def capture(name):
 before=app.session.current
 for _ in range(8):app.taskMgr.step()
 app.graphicsEngine.syncFrame();app.win.getScreenshot().write(Filename.fromOsSpecific(str(out/(name+'.png'))));assert app.session.current==before;names.append(name)
try:
 app.open_career()
 for event in ('first-drive','parking'):app.career_progress.record(CareerResult(event,8.,elapsed=25.,finished=True,succeeded=True,stars=3))
 result=CareerResult('slalom',8.,elapsed=35.008,finished=True,succeeded=True,stars=3)
 award=app.career_progress.record(result);assert award['vehicles']==('coastal-gt','porsche-930');app.career_panel.show_result(app.career_progress,result,award);capture('01-nine-star-reward')
 button=next(b for b in app.career_panel.buttons if b['extraArgs'][0]=='garage-new');button['command'](*button['extraArgs']);assert app.career_preview.design_id=='porsche-930' and app.workspace_vehicle.design_id=='game-tuned';capture('02-new-car-preview')
 app.career_action('garage-select');assert app.workspace_vehicle.design_id=='porsche-930';app.career_action('garage-back');assert app.career_panel.page=='brief' and app.career_panel.event_id=='slalom';capture('03-return-to-event')
 (out/'summary.json').write_text(json.dumps({'passed':True,'size':args.size,'captures':names,'new_driving_steps':0,'fixture':'isolated synthetic 9-star award; preview and explicit select; original earned event return'},indent=2));print('PASSED',out)
finally:app.close_game()
