"""真实失败轨迹核对两耦合修正块的调用条件，不改变各块方程与原20轮门槛。"""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'src'))
import tire_drivetrain as target
source=(root/'src/tire_drivetrain.py').read_text(encoding='utf-8')
source=source.replace('sweep >= 8 and maximum < .001 and (normal_error', 'sweep >= 8 and (normal_error')
exec(compile(source,str(root/'src/tire_drivetrain.py')+' coupled correction order probe','exec'),target.__dict__)
import vehicle_tires
vehicle_tires.advance_drivetrain=target.advance_drivetrain
import pytest
raise SystemExit(pytest.main(['-q','-x','tests/test_h3_review.py::test_car_hits_solid_roadside_objects[checkpoint]']))
