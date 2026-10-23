import os,sys,json
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,'src')
from application import CoastalDrive
from panda3d.core import Filename, Shader, DepthTestAttrib
from simplepbr._shaderutils import _load_shader_str
out=Path('logs/validation/GARAGE-DESIGN-02-floor-probe');out.mkdir(exist_ok=False)
os.environ['LOCALAPPDATA']=str(out/'user')
app=CoastalDrive(smoke=True,output=out,render_size=(1280,720));app.taskMgr.remove('finish-smoke');app.taskMgr.remove('drive-update')
app.open_career_collection();app.career_action('garage-car','game-tuned');app.career_action('garage-tab','upgrade')
view=app.workshop_vehicle
mirror=view.floor_reflection;surface,depth=mirror.getChildren()
def shot(name):
 for _ in range(8): app.taskMgr.step()
 app.graphicsEngine.syncFrame();app.win.getScreenshot().write(Filename.fromOsSpecific(str(out/(name+'.png'))))
 return np.asarray(Image.open(out/(name+'.png')).convert('RGB')).astype(float)
try:
 original=shot('original')
 mirror.hide();off=shot('off');mirror.show()
 surface.setAttrib(DepthTestAttrib.make(DepthTestAttrib.MLessEqual),3);less=shot('less-equal')
 defines={'MAX_LIGHTS':1,'USE_330':view.pipeline.use_330}
 frag=_load_shader_str('simplepbr.frag',defines.copy()).replace('color.rgb += emission;','color.rgb += emission; color.a *= 0.2;')
 surface.setShader(Shader.make(Shader.SLGLSL,_load_shader_str('simplepbr.vert',defines.copy()),frag),3)
 nofade=shot('no-fade')
 results={}
 for name,img in [('original',original),('less-equal',less),('no-fade',nofade)]:
  mask=np.max(abs(img-off),axis=2)>2
  y,x=np.where(mask)
  results[name]={'pixels':int(mask.sum()),'bounds':[int(x.min()),int(y.min()),int(x.max()),int(y.max())] if len(x) else None,'max_difference':float(np.max(abs(img-off)))}
 (out/'summary.json').write_text(json.dumps(results,indent=2)+'\n');print(results)
finally: app.close_game()
