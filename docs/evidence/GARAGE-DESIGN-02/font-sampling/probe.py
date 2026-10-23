import argparse,os,sys,json
from pathlib import Path
from dataclasses import asdict
sys.path.insert(0,'src')
from panda3d.core import Filename,SamplerState
from ui import theme
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['linear','mipmap']);parser.add_argument('--size',nargs=2,type=int,default=[1280,720]);args=parser.parse_args()
folder=Path('logs/validation/GARAGE-DESIGN-02-font-sampling')/(args.mode+'-'+str(args.size[0]));folder.mkdir(exist_ok=False)
original=theme.load_font
def font(filename=theme.FONT_FILE):
 result=original(filename)
 result.setMinfilter(SamplerState.FTLinearMipmapLinear if args.mode=='mipmap' else SamplerState.FTLinear)
 result.setTextureMargin(16 if args.mode=='mipmap' else 2)
 result.setPolyMargin(8 if args.mode=='mipmap' else 0)
 return result
theme.load_font=font
from application import CoastalDrive
os.environ['LOCALAPPDATA']=str(folder/'user')
app=CoastalDrive(smoke=True,output=folder,render_size=tuple(args.size));app.taskMgr.remove('finish-smoke');app.taskMgr.remove('drive-update')
def shot(name):
 before=asdict(app.session.current)
 for _ in range(8):app.taskMgr.step()
 app.graphicsEngine.syncFrame();app.win.getScreenshot().write(Filename.fromOsSpecific(str(folder/(name+'.png'))))
 assert before==asdict(app.session.current)
try:
 shot('home')
 app.open_career_collection();app.career_action('garage-tab','upgrade');shot('upgrade')
 font=app.ui_font
 report=dict(passed=True,mode=args.mode,size=args.size,font=dict(pixels_per_unit=font.getPixelsPerUnit(),scale=font.getScaleFactor(),texture_margin=font.getTextureMargin(),poly_margin=font.getPolyMargin(),minfilter=font.getMinfilter()),new_driving_steps=0)
 (folder/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
finally:app.close_game()
