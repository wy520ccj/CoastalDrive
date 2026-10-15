"""诊断比较必须识别实际数值位差，不能把舍入/类型变化当作相同。"""

import importlib.util
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location("lab_crossover",Path(__file__).resolve().parents[1]/
    "tools/performance/compare_lab_native_crossover.py")
DIAGNOSTIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIAGNOSTIC)


def test_replay_digest_distinguishes_signed_zero_single_bit_dtype_and_shape():
    baseline = np.array((0.,1.))
    changes = [np.array((-0.,1.)),np.array((0.,np.nextafter(1.,2.))),
               baseline.astype(np.float32),baseline.reshape(1,2)]
    assert len({DIAGNOSTIC.digest(value) for value in [baseline,*changes]}) == 5


def test_replay_digest_preserves_python_float_and_numpy_scalar_bit_patterns():
    first_nan = struct.unpack("!d",bytes.fromhex("7ff8000000000001"))[0]
    second_nan = struct.unpack("!d",bytes.fromhex("7ff8000000000002"))[0]
    values = [0.,-0.,np.float64(0.),np.float32(0.),first_nan,second_nan]
    assert len({DIAGNOSTIC.digest(value) for value in values}) == len(values)


def test_replay_digest_compares_all_numeric_fields_and_ignores_only_world_reference():
    @dataclass
    class State:
        force: np.ndarray
        work: float
        contact_geometry: object

    original = State(np.eye(2),1.,object())
    same = State(np.asfortranarray(np.eye(2)),1.,object())
    different = State(np.eye(2),np.nextafter(1.,2.).item(),object())
    assert DIAGNOSTIC.digest(original) == DIAGNOSTIC.digest(same)
    assert DIAGNOSTIC.digest(original) != DIAGNOSTIC.digest(different)
