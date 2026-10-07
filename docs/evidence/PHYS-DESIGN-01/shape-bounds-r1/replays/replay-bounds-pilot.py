"""原主目录机械方程，只用真实形状边界筛选候选，不扩大实际查询范围。"""
from pathlib import Path

folder=Path(__file__).resolve().parent
source=(folder/'replay-original.py').read_text(encoding='utf-8')
injection='''
from types import ModuleType
import vehicle_suspension
candidate_source=Path('C:/Users/15120/.codex/worktrees/gr86-physics/CoastalDrive/src/suspension_contacts.py').read_text(encoding='utf-8')
candidate_module=ModuleType('candidate_bounds_pilot')
sys.modules[candidate_module.__name__]=candidate_module
exec(compile(candidate_source,'candidate_bounds_pilot.py','exec'),candidate_module.__dict__)
vehicle_suspension.cylinder_suspension_rays=candidate_module.cylinder_suspension_rays
'''
source=source.replace('folder=Path(__file__).resolve().parent',injection+'\nfolder=Path(__file__).resolve().parent')
source=source.replace('replay-original.json','replay-bounds-pilot.json')
source=source.replace('original Python equations and arithmetic','original Python equations, exact shape bounds candidate pilot; no cache or padding expansion')
exec(compile(source,str(__file__),'exec'),{'__file__':str(__file__)})
