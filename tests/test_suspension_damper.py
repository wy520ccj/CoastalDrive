"""分段被动阻尼的独立功/切线、旧模型退化、原始留出与表外范围。"""

import copy
from dataclasses import asdict, replace

import numpy as np
import pytest
from damper_bench_reference import document, force
from suspension_motion_reference import document as linear_document
from test_unsprung_dynamics import GUIDES, partition

from suspension_bench import fit_bench, record_coverage, source_note, validate_metadata
from suspension_damper import damper_curve
from suspension_installation import installation_curve
from unsprung_contact import damping_material, normal_block, normal_material
from unsprung_dynamics import assemble_unsprung
from vehicle_designs import REFERENCE_DESIGN
from vehicle_parameters import config_from_document, grouped_parameters

BASE=replace(REFERENCE_DESIGN,unsprung_enabled=True)


def test_raw_table_preserves_digression_and_passivity_inside_and_beyond_domain():
    car,report=fit_bench(document(),BASE)
    assert report["passed"]
    rd0=report["results"]["FL"]["compression"]["motion_ratio"]
    curve=damper_curve(car.suspension_damper_curves[0])
    for velocity in (-2.,-.8,-.33,-.02,0.,.017,.2,.8,2.):
        actual,slope=curve.at(velocity/rd0)
        expected=force(velocity,"compression" if velocity>=0 else "extension")
        assert actual/rd0==pytest.approx(expected,abs=1e-10)
        assert velocity*actual>=0. and slope>=0.
    assert curve.at(.4/rd0)[1]==pytest.approx(.25*curve.at(.01/rd0)[1])


def test_linear_table_exactly_matches_original_nonlinear_installation_path():
    raw=document()
    for corner in raw["corners"].values():
        for row in corner["rows"]:
            if row["kind"]!="spring":
                row["force_N"]=row["input"]*(5280./.75**2 if row["kind"]=="compression" else 2760./.75**2)
    table,_=fit_bench(raw,BASE)
    linear,_=fit_bench(linear_document(),BASE)
    for value in (-.3,0.,.3):
        q=np.array((-.07,.023,.072,.17))
        a=damping_material(q,np.full(4,value),table)
        b=damping_material(q,np.full(4,value),linear)
        for x,y in zip(a,b,strict=True):assert x==pytest.approx(y,abs=1e-10)


@pytest.mark.parametrize("speed",(-.23,.23))
def test_component_power_and_full_implicit_derivative_use_actual_curve_and_geometry(speed):
    car,_=fit_bench(document(),BASE)
    q0=np.full(4,.031)
    u=np.full(4,speed)
    q=q0+.01*u
    resistance,du,dq=damping_material(q,u,car)
    for i in range(4):
        axis=installation_curve(car.suspension_installation_curves[i])[1]
        rd=axis.at(q[i])[1]
        vd=rd*speed
        fd=force(vd,"compression" if vd>=0 else "extension")
        assert resistance[i]==pytest.approx(rd*fd,abs=1e-10)
        assert resistance[i]*speed==pytest.approx(fd*vd,abs=1e-10)
        eps=np.eye(4)[i]*1e-6
        plus=damping_material(q0+.01*(u+eps),u+eps,car)[0]
        minus=damping_material(q0+.01*(u-eps),u-eps,car)[0]
        assert (plus-minus)/2e-6==pytest.approx(np.eye(4)[i]*(du[i]+.01*dq[i]),rel=1e-8,abs=1e-5)
    material=normal_material(q,u,np.zeros(4),np.zeros(4),.01,car,np.zeros(4),np.zeros(4))
    assert material.suspension_damping==pytest.approx(.01*np.dot(resistance,u),abs=1e-12)
    assert material.suspension_damping>=0.


def test_actual_table_overrides_inactive_reference_slopes_and_legacy_load_clears_table():
    car,report=fit_bench(document(),BASE)
    changed=replace(car,suspension_compression_damping=(1.,)*4,suspension_extension_damping=(2.,)*4)
    q,u=np.full(4,.03),np.full(4,.2)
    assert damping_material(q,u,car)[0]==pytest.approx(damping_material(q,u,changed)[0])
    params=grouped_parameters(car)
    del params["suspension"]["suspension_damper_curves"]
    assert config_from_document({"schema":"vehicle-engineering-v1","parameters":params},car).suspension_damper_curves is None
    assert fit_bench(linear_document(),car)[0].suspension_damper_curves is None
    metadata={"suspension_calibration":report}
    assert "分段力速表" in source_note(metadata,"suspension_damper_curves",car.suspension_damper_curves,asdict(car))
    covered=asdict(car)
    covered["suspension_damper_curves"]=None
    assert "本构已覆盖" in source_note(metadata,"suspension_compression_damping",car.suspension_compression_damping,covered)


def test_complete_normal_energy_ledger_counts_nonlinear_resistance_as_heat():
    car,_=fit_bench(document(),BASE)
    q=np.array((.03,.04,.05,.06))
    v=np.r_[np.zeros(6),(.15,-.15,.2,-.2)]
    mechanics=assemble_unsprung(partition(),np.eye(3),q,GUIDES,v)
    result=normal_block(mechanics,v,q,np.full(4,.014),np.asarray(GUIDES),np.full(4,200000.),np.full(4,500.),
        mechanics.gravity_forces((0.,0.,-9.81)),np.zeros(4),1/240,car)
    assert result.impulse_residual<1e-10
    assert result.energy_error==pytest.approx(0.,abs=1e-9)
    assert result.suspension_damping_loss>0.


def test_whole_series_holdout_cannot_change_nodes_and_rejects_incompatible_force():
    good,report=fit_bench(document(),BASE)
    bad,rejected=fit_bench(document(bad_validation=True),BASE)
    assert report["passed"] and not rejected["passed"]
    assert good==bad
    validate_metadata({"suspension_calibration":report})
    modified=copy.deepcopy(report)
    modified["parameters"]["suspension_damper_curves"][0][0][1]-=1.
    with pytest.raises(ValueError):validate_metadata({"suspension_calibration":modified})
    # 同样的渐消曲线用v3线性拟合应失败，不能因升级而放宽旧误差阈值。
    raw=document()
    raw.update(schema="coastal-suspension-bench-v3",definition=linear_document()["definition"])
    assert fit_bench(raw,BASE)[1]["passed"] is False


@pytest.mark.parametrize("failure",("bias","active","order","missing_zero"))
def test_nonpassive_or_ambiguous_raw_table_rejected(failure):
    raw=document()
    rows=raw["corners"]["FL"]["rows"]
    if failure=="bias":
        for row in rows:
            if row["kind"]=="compression" and row["input"]==0.:row["force_N"]=10.
    elif failure=="active":
        for row in rows:
            if row["kind"]=="extension":row["force_N"]*=-1
    elif failure=="order":
        for row in rows:
            if row["kind"]=="compression" and row["input"]==.02:row["force_N"]+=10000.
    else:
        raw["corners"]["FL"]["rows"]=[row for row in rows if not (row["kind"]=="compression" and row["input"]==0.)]
    with pytest.raises(ValueError):fit_bench(raw,BASE)


def test_range_report_detects_force_table_extrapolation_and_actual_override():
    car,report=fit_bench(document(),BASE)
    metadata={"suspension_calibration":report}
    row={**{f"travel_{wheel}":.03 for wheel in ("fl","fr","rl","rr")},
         **{f"travel_rate_{wheel}":2. for wheel in ("fl","fr","rl","rr")}}
    result=record_coverage(metadata,asdict(car),[row])["corners"]["FL"]["compression"]
    assert result["table_extrapolated_samples"]==1
    changed=asdict(car)
    changed["suspension_compression_damping"]=(1.,)*4
    assert record_coverage(metadata,changed,[row])["corners"]["FL"]["compression"]["status"]!="overridden"
    changed["suspension_damper_curves"]=None
    assert record_coverage(metadata,changed,[row])["corners"]["FL"]["compression"]["status"]=="overridden"
