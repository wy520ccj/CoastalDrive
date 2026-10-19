"""参考数据读取边界；IO格式夹具不替代实际Double方程检验。"""

import json
import shutil
from pathlib import Path

import mechanical_kernels
import pytest
import test_continuous_solver as solver
from panda3d.core import LPoint3, LPoint3d
from physics.capture_double_reference import capture


@pytest.fixture
def reference(tmp_path, monkeypatch):
    folder = tmp_path/'reference'
    shutil.copytree(solver.DOUBLE_REFERENCE, folder)
    context = json.loads((folder/'context.json').read_text(encoding='utf-8'))
    # 只测试IO校验：不在Normal SDK中假装执行Double力学。
    monkeypatch.setattr(solver, 'DOUBLE_REFERENCE', folder)
    monkeypatch.setattr(solver, 'runtime_fingerprint', lambda: context['sdk'])
    solver.double_context.cache_clear()
    yield folder, context
    solver.double_context.cache_clear()


def test_actual_sdk_explicitly_selects_reference_without_fallback():
    identifier = 6240
    folder = solver.DOUBLE_REFERENCE if LPoint3 is LPoint3d else solver.FIXTURE
    assert solver.reference_result(identifier) == (folder/f'result-{identifier}.bin').read_bytes()


@pytest.mark.parametrize('damage,message', [('schema', '格式版本'), ('sdk', 'SDK摘要'),
    ('source', '独立旧模块'), ('codec', '数值包格式'), ('input-set', '输入集合'),
    ('input-sha', '输入内容'), ('hardware', '有效硬件'), ('output-set', '结果集合')])
def test_changed_reference_conditions_are_rejected(reference, monkeypatch, damage, message):
    folder, context = reference
    if damage == 'schema':
        context['schema'] = 'unknown'
    elif damage == 'sdk':
        monkeypatch.setattr(solver, 'runtime_fingerprint', lambda: {**context['sdk'], 'math_scalar_bits': 32})
    elif damage == 'source':
        context['reference']['module_sha256'] = '0'*64
    elif damage == 'codec':
        context['codec_sha256'] = '0'*64
    elif damage == 'input-set':
        context['input_sha256'].pop('input-6240.bin')
    elif damage == 'input-sha':
        context['input_sha256']['input-6240.bin'] = '0'*64
    elif damage == 'hardware':
        context['effective_hardware']['mass'] += 1.
    else:
        context['output_sha256'].pop('result-6240.bin')
    (folder/'context.json').write_text(json.dumps(context), encoding='utf-8')
    with pytest.raises(ValueError, match=message):
        solver.double_result(6240)


def test_missing_metadata_or_modified_payload_cannot_fall_back_to_normal(reference):
    folder, _context = reference
    path = folder/'result-6240.bin'
    data = bytearray(path.read_bytes())
    data[-1] ^= 1
    path.write_bytes(data)
    with pytest.raises(ValueError, match='结果内容'):
        solver.double_result(6240)
    solver.double_context.cache_clear()
    (folder/'context.json').unlink()
    with pytest.raises(FileNotFoundError):
        solver.double_result(6240)


def test_generator_rejects_current_module_as_its_own_expected_values(tmp_path):
    output = tmp_path/'not-created'
    with pytest.raises(ValueError, match='只能用已归档修复前模块'):
        capture(output, Path(mechanical_kernels.__file__).resolve(), solver.PRIOR_REFERENCE.parent/'production-before.c')
    assert not output.exists()
