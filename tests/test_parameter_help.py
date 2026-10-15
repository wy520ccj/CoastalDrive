"""计算说明覆盖当前配置/输入，单位表不复制，未知字段明确报错。"""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from parameter_formulas import FORMULAS, formula_key
from parameter_help import EDITOR_INFO, explanation, group_parameters
from vehicle_config import CAR
from vehicle_parameter_info import BRAKE_FIELDS, STABILITY_FIELDS, TRACTION_FIELDS, VEHICLE_FIELDS
from vehicle_parameters import PARAMETER_GROUPS


def test_unit_catalog_completely_covers_real_configuration_and_controls():
    config = asdict(CAR)
    assert set(VEHICLE_FIELDS) == set(config)
    for parent, fields in (("braking", BRAKE_FIELDS), ("traction", TRACTION_FIELDS), ("stability", STABILITY_FIELDS)):
        assert set(fields) == set(config[parent])
    for group in PARAMETER_GROUPS:
        for key in group_parameters(group):
            info = explanation(key)
            assert info.unit and info.formula and info.source and info.role


def test_context_explanations_distinguish_inputs_from_solved_force():
    for key in EDITOR_INFO:
        assert explanation(key).source.startswith("src/")
    assert "固定" in explanation("tire_load").role
    assert "Fn/Fn0" in explanation("tire_load").formula
    assert "不直接施加" in explanation("cg").use
    assert "公式" in explanation("mass").formula


def test_unknown_parameter_is_not_given_a_fake_formula():
    with pytest.raises(KeyError):
        explanation("invented_mass_equation")


def test_shipped_equations_match_current_tex_and_have_not_been_replaced():
    directory = Path(__file__).resolve().parents[1] / "assets/game/ui/formulas"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["formulas"]) == set(FORMULAS)
    for key, (lines, _) in FORMULAS.items():
        entries = manifest["formulas"][key]
        assert [entry["tex"] for entry in entries] == list(lines)
        for entry in entries:
            data = (directory / entry["file"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == entry["sha256"]
            assert entry["width"] > 0 and entry["height"] > 0
    assert formula_key("tire_load") == "tire_reference_load"
    assert formula_key("mass") is None
