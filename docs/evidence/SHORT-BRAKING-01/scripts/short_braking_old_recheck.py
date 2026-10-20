import sys,json,gzip,math
from dataclasses import asdict
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from braking_lesson import BrakingLesson,BrakingScores
from lab_records import model_fingerprint
out=Path('logs/validation/BRAKE-ROAD-01-probe')
summary={'passed':True,'scope':'旧原始物理记录重放全旧字段；不是新驾驶','cases':[],'source':model_fingerprint()}
for index in range(4):
 with gzip.open(out/f'{index}-raw.json.gz','rt',encoding='utf-8') as f:rows=json.load(f)
 run=BrakingLesson(8.,BrakingScores(out/f'recheck-{index}-best.json','check'))
 for i,row in enumerate(rows):
  result=run.update(row['position'][1],row['velocity'][1],math.hypot(*row['velocity'][:2]),(i+1)/120,1/120,collisions=row['collisions'],lateral=row['position'][0])
  for key,value in row['result'].items():
   assert asdict(result)[key]==value,(index,i,key,asdict(result)[key],value)
 summary['cases'].append({'index':index,'rows':len(rows),'old_keys':list(rows[-1]['result'])})
summary['rows']=sum(c['rows'] for c in summary['cases'])
(out/'old-rule-recheck.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(summary['rows'])
