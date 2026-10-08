"""使用提交前Python轮胎本构复现时间戳断言；不改生产文件。"""
import subprocess
import sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
import tire_forces
import tire_compliance
for module in (tire_forces,tire_compliance):
    source=subprocess.check_output(['git','show','12ea82b:src/'+module.__name__+'.py'],text=True,encoding='utf-8')
    exec(compile(source,'12ea82b original '+module.__name__,'exec'),module.__dict__)
import pytest
raise SystemExit(pytest.main(['-q','tests/test_tire_compliance_probe.py::test_real_short_trial_energy_and_control_account']))
