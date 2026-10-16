"""字段化中文输入错误；格式、有限性、范围与可选空值边界。"""

import pytest

from lab_inputs import FIELDS, LabInputError, read_number


@pytest.mark.parametrize("key", tuple(FIELDS))
@pytest.mark.parametrize("text", ("22wd", "", "NaN", "inf"))
def test_invalid_numeric_text_has_chinese_field_and_no_python_exception(key, text):
    with pytest.raises(LabInputError) as captured:
        read_number(text, key)
    error = captured.value
    assert error.key == key and FIELDS[key][0] in str(error)
    assert "could not convert" not in str(error)


@pytest.mark.parametrize("key,value", (("radius", "6"), ("right_mu", "0"),
    ("onset", "-1"), ("bump_height", ".1"), ("tire_load", "0"), ("manual.gear", "1.5")))
def test_range_errors_name_the_actual_field(key, value):
    with pytest.raises(LabInputError) as captured:
        read_number(value, key)
    assert captured.value.key == key


def test_optional_and_signed_inputs_keep_their_meaning():
    assert read_number("  ", "cg", optional=True) is None
    assert read_number("-2.5", "steer", bounds=(-26., 26.)) == -2.5
    assert read_number("-1", "manual.gear", bounds=(-1, 6)) == -1


def test_english_exception_with_chinese_user_text_still_has_chinese_feedback():
    from ui.lab_feedback import error_text

    message = error_text(ValueError("could not convert string to float: '错误'"))
    assert "could not" not in message and "参数" in message
