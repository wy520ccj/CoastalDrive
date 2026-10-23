import ast,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,'src')
from panda3d.core import DynamicTextFont,DynamicTextGlyph,SamplerState,TextNode
from ui import theme
folder=Path('logs/validation/GARAGE-DESIGN-02-font-sampling')
corpus=''.join(sorted(set(''.join(n.value for p in Path('src/ui').glob('*.py') for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n,ast.Constant) and isinstance(n.value,str)))))
reports={}
for filename in (theme.FONT_FILE,'fonts/SourceHanSansSC-Regular.otf',theme.DISPLAY_FONT_FILE,'fonts/Tabler-Menu.ttf'):
 fonts={};metrics={}
 for mode in ('linear','mipmap'):
  font=theme.load_font(filename)
  if mode=='linear':font.setTextureMargin(2);font.setPolyMargin(0);font.setMinfilter(SamplerState.FTLinear)
  requested = ''.join(chr(c) for c in (0xeb45,0xebbb,0xee2f,0xef3d,0xff9b)) if 'Tabler' in filename else corpus
  glyphs=[font.getGlyph(ord(c)) for c in requested]
  node=TextNode('metrics');node.setFont(font)
  values=[]
  for text in ('升级改装','运动前轮','去试车 · 穿过海风','0123456789 99.000 km/h','COASTAL DRIVE'):
   supported=''.join(c for c in text if c.isspace() or isinstance(font.getGlyph(ord(c)),DynamicTextGlyph))
   node.setText(supported);values.append({'text':text,'width':node.getWidth(),'height':node.getHeight()})
  textures=[font.getPage(i) for i in range(font.getNumPages())]
  fonts[mode]={'pages':len(textures),'atlas_base_bytes':sum(t.getRamImageSize() for t in textures),'mipmaps_estimated_bytes':int(sum(t.getRamImageSize() for t in textures)*4/3) if mode=='mipmap' else None}
  metrics[mode]=values
 if metrics['linear']!=metrics['mipmap']: print(filename,metrics)
 assert metrics['linear']==metrics['mipmap']
 reports[filename]={'atlases':fonts,'metrics_unchanged':True,'metrics':metrics['mipmap']}
(folder/'atlas-comparison-final.json').write_text(json.dumps({'scope':'same UI source literal corpus; full font atlas stress not runtime memory benchmark','characters':len(corpus),'fonts':reports},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'characters':len(corpus),'fonts':{k:v['atlases'] for k,v in reports.items()}},ensure_ascii=False))
