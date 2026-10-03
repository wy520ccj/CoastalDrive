"""独立检验逆列的公共表达式复用；不修改当前运行的物理源码。"""

import hashlib
import json
from pathlib import Path
import random
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from rotor_dynamics import cross, dot
from transmission_ports import _solve_three, clutch_brake_plans


def old_columns(rows):
    return tuple(_solve_three(rows, tuple(float(i == j) for i in range(3))) for j in range(3))


def reused_columns(rows):
    cofactors = cross(rows[1], rows[2]), cross(rows[2], rows[0]), cross(rows[0], rows[1])
    determinant = dot(rows[0], cofactors[0])
    # 保持每列的乘加、sum起始值与除法顺序，只复用同一矩阵的余子式。
    return tuple(tuple(sum(cofactors[j][i] * float(j == k) for j in range(3)) / determinant
                       for i in range(3)) for k in range(3))


def rows_for(response, efficiency):
    for clutch_locked in (False, True):
        for slope in (1 - efficiency, 1 - 1 / efficiency, None):
            for brake_locked in (False, True):
                yield (response[0] if clutch_locked else (1., 0., 0.),
                       response[1] if slope is None else (-slope, 1., 0.),
                       response[2] if brake_locked else (0., 0., 1.))


def packed(columns):
    return struct.pack("!9d", *(value for column in columns for value in column))


def reused_plans(response, capacity, brake_capacity, efficiency):
    plans, by_rows = [], {}
    clutch_modes = ("locked", "positive-slip", "negative-slip") if capacity else ("positive-slip", "negative-slip")
    brake_modes = ("locked", "positive-slip", "negative-slip") if brake_capacity else ("positive-slip", "negative-slip")
    for clutch_mode in clutch_modes:
        for gear_mode in ("positive-motion", "negative-motion", "static"):
            for sign in ((-1, 1) if gear_mode != "static" else (0,)):
                slope = (1 - efficiency if (gear_mode == "positive-motion") == (sign > 0)
                         else 1 - 1 / efficiency)
                for brake_mode in brake_modes:
                    rows = (response[0] if clutch_mode == "locked" else (1., 0., 0.),
                            response[1] if gear_mode == "static" else (-slope, 1., 0.),
                            response[2] if brake_mode == "locked" else (0., 0., 1.))
                    if rows not in by_rows:
                        by_rows[rows] = reused_columns(rows)
                    plans.append(((clutch_mode, gear_mode, brake_mode), sign, by_rows[rows]))
    return tuple(plans), len(by_rows)


def packed_plans(plans):
    return tuple((modes, sign, packed(columns)) for modes, sign, columns in plans)


def main():
    rng = random.Random(20261003)
    matrices, responses = [], [((7., -2., .4), (-2., 4., -.7), (.4, -.7, 1.5)),
                              ((7., 0., 0.), (0., 4., 0.), (0., 0., 1.5))]
    for _ in range(400):
        factor = tuple(tuple(rng.uniform(-5., 5.) for _ in range(3)) for _ in range(3))
        response = tuple(tuple(sum(factor[k][i] * factor[k][j] for k in range(3))
                               + (rng.uniform(.1, 10.) if i == j else 0.)
                               for j in range(3)) for i in range(3))
        responses.append(response)
        for efficiency in (.88, 1.):
            matrices.extend(rows_for(response, efficiency))
    before = hashlib.sha256()
    after = hashlib.sha256()
    differences = 0
    for rows in matrices:
        original, candidate = packed(old_columns(rows)), packed(reused_columns(rows))
        before.update(original)
        after.update(candidate)
        differences += original != candidate
    timings = []
    sample = matrices[:1200]
    for round_index in range(6):
        row = {}
        functions = (("old", old_columns), ("reuse", reused_columns))
        if round_index % 2:
            functions = tuple(reversed(functions))
        for label, function in functions:
            started = time.perf_counter()
            for matrix in sample:
                function(matrix)
            row[label] = time.perf_counter() - started
        timings.append(row)
    plan_differences = 0
    plan_cases = 0
    for response in responses:
        for efficiency in (.88, 1.):
            for capacity, brake_capacity in ((0., 0.), (0., 600.), (300., 0.), (300., 600.)):
                original = clutch_brake_plans(response, capacity, brake_capacity, efficiency)
                candidate, unique_rows = reused_plans(response, capacity, brake_capacity, efficiency)
                plan_differences += packed_plans(original) != packed_plans(candidate)
                plan_cases += 1
    original = clutch_brake_plans(responses[0], 300., 600., .88)
    _candidate, unique_rows = reused_plans(responses[0], 300., 600., .88)
    result = {"scope": "independent finite SPD/constraint matrices; no production changes; concurrent T1, not native/frame-rate evidence",
              "matrix_count": len(matrices), "double_values": len(matrices) * 9,
              "byte_different_matrices": differences, "old_sha256": before.hexdigest(),
              "reuse_sha256": after.hexdigest(), "timing_sample_matrices": len(sample),
              "alternating_timing_seconds": timings, "plan_cases": plan_cases,
              "byte_or_order_different_plan_cases": plan_differences,
              "nonzero_capacities_eta088": {"plans": len(original), "unique_matrices": unique_rows}}
    target = Path(__file__).with_suffix(".json")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    assert differences == 0 and plan_differences == 0


if __name__ == "__main__":
    main()
