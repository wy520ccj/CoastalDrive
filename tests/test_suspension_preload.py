"""安装预压的虚功/储能/松弛、原始台架映射与历史协议。"""

import copy
from dataclasses import asdict, replace

import numpy as np
import pytest
from suspension_bench_reference import document
from test_unsprung_dynamics import GUIDES, partition

from suspension_bench import (
    INSTALLED_DEFINITION,
    INSTALLED_SCHEMA,
    fit_bench,
    record_coverage,
    source_note,
    validate_metadata,
)
from unsprung_contact import normal_block, normal_material, suspension_potential
from unsprung_dynamics import assemble_unsprung
from vehicle_designs import REFERENCE_DESIGN
from vehicle_parameters import config_from_document, grouped_parameters

COIL = replace(REFERENCE_DESIGN,unsprung_enabled=True,suspension_coil_enabled=True,
               suspension_spring_preloads=(960.,)*4,suspension_antiroll_rates=(0.,0.),
               suspension_stop_rates=(0.,)*4)


def installed_document(precompression=.02):
    value = document()
    value.update(schema=INSTALLED_SCHEMA,definition=INSTALLED_DEFINITION)
    for corner in value["corners"].values():
        corner["spring_installed_compression_m"] = precompression
        corner["installation_source"] = "synthetic reference installation; NOT measured"
    return value


def test_installed_energy_has_correct_gradient_constant_active_rate_and_no_tension():
    q = np.array((-.03,-.015,0.,.01))
    energy,force = suspension_potential(q,COIL)
    actual_compression = np.array((0.,.005,.02,.03))
    assert force == pytest.approx(48000*actual_compression,abs=1e-12)
    assert energy == pytest.approx(sum(.5*48000*x*x for x in actual_compression))
    for i in range(4):
        perturbation = np.eye(4)[i]*1e-7
        numerical = (suspension_potential(q+perturbation,COIL)[0]-suspension_potential(q-perturbation,COIL)[0])/2e-7
        assert numerical == pytest.approx(force[i],abs=1e-7)
    material = normal_material(q,np.zeros(4),np.zeros(4),np.zeros(4),.01,COIL,np.zeros(4),np.zeros(4))
    expected = np.diag((0.,48000.,48000.,48000.))*.01+np.diag(COIL.suspension_compression_damping)
    assert material.suspension_tangent == pytest.approx(expected,abs=1e-12)
    assert suspension_potential(np.full(4,-.02),COIL)[0] == pytest.approx(0.,abs=1e-25)
    assert suspension_potential(np.zeros(4),replace(COIL,suspension_spring_preloads=(0.,)*4))[1] == pytest.approx(np.zeros(4))


def test_full_frozen_normal_energy_includes_release_of_installation_storage():
    q = np.zeros(4)
    speed = np.r_[np.zeros(6),np.full(4,-10.)]
    config = replace(COIL,suspension_compression_damping=(0.,)*4,suspension_extension_damping=(0.,)*4)
    mechanics = assemble_unsprung(partition(),np.eye(3),q,GUIDES,speed)
    step = normal_block(mechanics,speed,q,np.full(4,-1.),np.asarray(GUIDES),np.zeros(4),np.zeros(4),
                        np.zeros(10),np.zeros(4),1/240,config)
    assert np.all(step.compression < -.02)
    assert step.suspension_force == pytest.approx(np.zeros(4))
    assert step.energy_error == pytest.approx(0.,abs=1e-10)
    assert step.suspension_damping_loss == 0.
    assert step.elastic_numerical_loss >= 0.


def test_component_installed_compression_is_mapped_once_and_rates_are_unchanged():
    base = replace(REFERENCE_DESIGN,unsprung_enabled=True)
    zero,zero_report = fit_bench(installed_document(0.),base)
    config,report = fit_bench(installed_document(),base)
    assert zero.suspension_coil_enabled and config.suspension_coil_enabled
    assert config.suspension_spring_rates == zero.suspension_spring_rates
    assert config.suspension_spring_preloads == pytest.approx((960.,960.,900.,900.))
    assert zero.suspension_spring_preloads == (0.,)*4
    metadata = {"suspension_calibration":report}
    validate_metadata(metadata)
    assert "安装压缩" in source_note(metadata,"suspension_spring_preloads",config.suspension_spring_preloads,asdict(config))
    assert "压缩/伸张" in source_note(metadata,"suspension_compression_damping",config.suspension_compression_damping,asdict(config))
    tampered = copy.deepcopy(metadata)
    tampered["suspension_calibration"]["parameters"]["suspension_spring_preloads"][0] += 1.
    with pytest.raises(ValueError,match="原始数据"):
        validate_metadata(tampered)
    assert zero_report["passed"] and report["passed"]


def test_coverage_uses_installed_component_compression_and_releases_changed_installation():
    config,report = fit_bench(installed_document(.2),replace(REFERENCE_DESIGN,unsprung_enabled=True))
    metadata = {"suspension_calibration":report}
    row = {**{f"travel_{wheel}":.05 for wheel in ("fl","fr","rl","rr")},
           **{f"travel_rate_{wheel}":0. for wheel in ("fl","fr","rl","rr")}}
    covered = record_coverage(metadata,asdict(config),[row])
    assert covered["corners"]["FL"]["spring"]["sampled_input_domain"] == pytest.approx([.24,.24])
    assert covered["corners"]["FL"]["spring"]["status"] == "outside_bench_domain"
    changed = asdict(replace(config,suspension_spring_preloads=(0.,)*4))
    assert record_coverage(metadata,changed,[row])["corners"]["FL"]["spring"]["status"] == "overridden"
    assert "安装值已覆盖" in source_note(metadata,"suspension_spring_rates",config.suspension_spring_rates,changed)


def test_legacy_engineering_does_not_inherit_new_coil_mechanism():
    parameters = grouped_parameters(COIL)
    del parameters["suspension"]["suspension_coil_enabled"]
    del parameters["suspension"]["suspension_spring_preloads"]
    restored = config_from_document({"schema":"vehicle-engineering-v1","parameters":parameters},COIL)
    assert not restored.suspension_coil_enabled and restored.suspension_spring_preloads==(0.,)*4
    old_config,_ = fit_bench(document(),COIL)
    assert not old_config.suspension_coil_enabled and old_config.suspension_spring_preloads==(0.,)*4


@pytest.mark.parametrize("values", ({"suspension_coil_enabled":False}, {"unsprung_enabled":False},
                                  {"suspension_spring_preloads":(-1.,)*4}, {"suspension_spring_preloads":(float("nan"),)*4}))
def test_unsupported_configuration_is_rejected(values):
    with pytest.raises(ValueError): replace(COIL,**values)
