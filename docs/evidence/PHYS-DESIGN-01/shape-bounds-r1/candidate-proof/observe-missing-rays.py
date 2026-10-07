from pathlib import Path

folder=Path(__file__).resolve().parent
source=(folder/'replay-original.py').read_text(encoding='utf-8')
injection='''
import vehicle_suspension
original_query=vehicle_suspension.cylinder_suspension_rays
misses=[]
def observed_query(*args,**kwargs):
    result=original_query(*args,**kwargs)
    if result == (None,):
        misses.append({'rays':args[2],'axes':args[3],'radius':args[4],'width':args[5],
                       'shoulder':args[6],'crown':args[7],'ray_origin':kwargs['ray_origin']})
    return result
vehicle_suspension.cylinder_suspension_rays=observed_query
'''
source=source.replace('folder=Path(__file__).resolve().parent',injection+'\nfolder=Path(__file__).resolve().parent')
source=source.replace('replay-original.json','replay-missing-rays.json')
source+='\n(folder/"missing-rays.json").write_text(json.dumps(misses,indent=2),encoding="utf-8")\nprint("missing rays:",len(misses))\n'
exec(compile(source,str(__file__),'exec'),{'__file__':str(__file__)})
