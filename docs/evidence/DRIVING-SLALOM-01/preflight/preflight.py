import sys,math,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from simulation import Simulation,Control
from driving_modes import DrivingMode
from driver_assist import steering_limit

GATES=[(120.,-2.),(160.,2.),(200.,-2.),(240.,2.),(280.,-2.),(320.,0.)]
def path_x(y):
    a,xa=80.,0.
    for b,xb in GATES:
        if y<=b:
            f=max(0.,min(1.,(y-a)/(b-a)))
            return xa+(xb-xa)*.5*(1-math.cos(math.pi*f))
        a,xa=b,xb
    return 0.
class Driver:
    def __init__(self,speed,binary=False,origin=0):self.speed=speed/3.6;self.binary=binary;self.origin=origin
    def sample(self,state,dt):
        car=state.player;x,y=car.position[:2];y-=self.origin
        look=5+abs(car.speed)*.45
        tx=path_x(y+look)
        dx,dy=tx-x,look
        error=math.atan2(-dx,dy)-math.radians(car.heading)
        angle=math.degrees(math.atan2(5.4*math.sin(error),math.hypot(dx,dy)))
        steer=max(-1.,min(1.,-angle/steering_limit(car.speed)))
        e=self.speed-car.speed
        if self.binary:
            steer=0. if abs(steer)<.08 else math.copysign(1.,steer)
            return Control(steering=steer,throttle=1. if e>-.25 else 0.,brake=1. if e<-1. else 0.)
        return Control(steering=steer,throttle=max(0.,min(1.,.18+.4*e)),brake=max(0.,min(1.,-.3*e)) if e<-.5 else 0.)
out=[]
for binary in (False,True):
 for speed in (40,50,60,70):
    app=Simulation(0,track='endless',road_shape='straight',traffic_count=0,
                   config=DrivingMode.GAME.configured_vehicle(),input_config=DrivingMode.GAME.input_config,physics_workers=0)
    try:
        app.settle_initial();origin=app.snapshot().player.position[1]
        driver=Driver(speed,binary,origin)
        passed=[];entry=None;prev=app.snapshot();coll=0
        for _ in range(45*120):
            app.step(driver.sample(prev,1/120));now=app.snapshot()
            x,y=now.player.position[:2];px,py=prev.player.position[:2];y-=origin;py-=origin
            if py<80<=y:entry=prev.time+(now.time-prev.time)*(80-py)/(y-py)
            if len(passed)<6 and py<GATES[len(passed)][0]<=y:
                gy,gx=GATES[len(passed)];f=(gy-py)/(y-py)
                error=px+(x-px)*f-gx;angle=math.radians(now.player.heading)
                span=app.config.collision_half_width*abs(math.cos(angle))+app.config.collision_half_length*abs(math.sin(angle))
                passed.append({'y':gy,'error':error,'heading':now.player.heading,'speed':now.player.speed*3.6,'time':now.time-entry,'clearance':2.-span-abs(error)})
            coll=now.collisions
            if len(passed)==6:break
            prev=now
        out.append({'binary':binary,'target':speed,'gates':passed,'position':list(now.player.position),'collisions':coll,'origin':origin})
    finally:app.close()
Path('logs/DRIVING-SLALOM-01/preflight.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out))
