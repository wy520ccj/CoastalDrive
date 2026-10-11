from pathlib import Path
import sys

root = Path.cwd()
sys.path.insert(0,str(root/'logs/performance/input-latency-r1/baseline/src'))
sys.path.insert(1,str(root/'tools'))
import session
import vehicle_tires
import wheel_contact_kernels
import pytest

print('BASELINE_MODULES',session.__file__,vehicle_tires.__file__,wheel_contact_kernels.__file__,flush=True)
raise SystemExit(pytest.main(['-q',
    'tests/test_rotor_lifecycle.py',
    'tests/test_tire_compliance_lifecycle.py::test_real_npc_shift_rebase_preserve_elastic_memory_then_reset_and_recycle_clear[DrivingMode.GAME]',
    'tests/test_tire_compliance_lifecycle.py::test_mode_rebuild_creates_true_compliance_cars_without_previous_elastic_energy']))
