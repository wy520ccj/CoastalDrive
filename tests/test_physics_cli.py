"""短无窗口入口确实启动数值进程，并在参数错误时保持边界清晰。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

MAIN = Path(__file__).resolve().parents[1]/'src/main.py'


def test_short_cli_runs_actual_traffic_workers_from_external_directory(tmp_path):
    completed = subprocess.run([sys.executable,str(MAIN),'--headless','--steps','3',
        '--track','coastal','--traffic-count','2','--physics-workers','2'],
        cwd=tmp_path,capture_output=True,text=True,timeout=15,check=False)
    assert completed.returncode==0,completed.stderr
    report = json.loads(completed.stdout)
    assert report['tick']==3 and len(report['traffic'])==2
    assert report['physics_workers']['processes']==2
    assert report['physics_workers']['remote']==18
    assert report['physics_workers']['world_required']==0


@pytest.mark.parametrize('arguments',[
    ['--headless','--traffic-count','-1'],['--traffic-count','2'],
    ['--headless','--physics-workers','33'],
])
def test_invalid_experiment_arguments_fail_before_creating_window(arguments,tmp_path):
    completed = subprocess.run([sys.executable,str(MAIN),*arguments],cwd=tmp_path,
        capture_output=True,text=True,timeout=10,check=False)
    assert completed.returncode==2
    assert 'error:' in completed.stderr
