import sys
from pathlib import Path

folder=Path(__file__).resolve().parent
variant=sys.argv[1]
source=(folder/'replay-latest.py').read_text(encoding='utf-8')
replay=(folder/'replay-original.py').read_text(encoding='utf-8')
replay=replay.replace("root=Path(__file__).resolve().parents[3]","root=Path('C:/Users/15120/.codex/worktrees/gr86-physics/CoastalDrive')")
replay=replay.replace('replay-original.json',f'replay-query-{variant}.json').replace('diagnostic-original.json',f'diagnostic-query-{variant}.json')
injection='''
from suspension_contacts import cylinder_suspension_rays
def uncached_query(self,start,end,axis):
    hit,=cylinder_suspension_rays(self.world,self.chassis,((start,end),),(axis,),self.wheel_radius,self.width,
        self.shoulder,self.crown,envelope=self.envelope,ray_origin=self.offset)
    return (hit.fraction,hit.normal,hit.point,hit.support_face) if hit is not None else None
def rays_only_query(self,start,end,axis):
    key=start,end,axis
    if key not in self.queries: self.queries[key]=uncached_query(self,start,end,axis)
    return self.queries[key]
'''
if variant=='none': injection+='WorldSurface.relative_entry=uncached_query\n'
elif variant=='rays': injection+='WorldSurface.relative_entry=rays_only_query\n'
else: raise ValueError(variant)
replay=replay.replace('folder=Path(__file__).resolve().parent',injection+'\nfolder=Path(__file__).resolve().parent')
exec(compile(replay,str(__file__),'exec'),{'__file__':str(__file__)})
