"""相邻子步数值种子限于单车，原输入可重放，任意方向仍受原物理方程验收。"""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import test_unsprung_joint as case
from lab_solver_validation import model_for, verify_result
from physics.unsprung_step_checkpoint import load_step, save_step
from test_lab_crossover_diagnostics import DIAGNOSTIC

from lab_experiment import LabExperiment, LabOptions
from lab_records import LabRecord, export_record, load_record, recalculate
from unsprung_joint import JointJacobianHint, solve_unsprung_joint
from vehicle_designs import REFERENCE_DESIGN, vehicle_design
from vehicle_parameters import config_from_document
from vehicle_unsprung import UnsprungAdvanceInput


def experiment(duration=.05):
    root=Path(__file__).resolve().parents[1]
    document=json.loads((root/'docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json').read_text(encoding='utf-8'))
    config=config_from_document(document,vehicle_design('reference-rwd').config)
    return LabExperiment(LabOptions(maneuver='ride_bump',duration=duration,bump_distance_m=2.),config=config)


@pytest.mark.parametrize('seed',['none','zero','identity','negative'])
def test_seed_only_changes_search_direction_and_inputs_remain_unchanged(monkeypatch,seed):
    previous={'none':None,'zero':np.zeros((34,34)),'identity':np.eye(34),'negative':-np.eye(34)}[seed]
    if previous is not None:previous.flags.writeable=False
    before=None if previous is None else previous.tobytes()
    hint=JointJacobianHint(previous)
    checked=[]
    def selected(*args,**kwargs):
        model=model_for(args,kwargs)
        result=solve_unsprung_joint(*args,**kwargs,jacobian_hint=hint)
        checked.append(verify_result(model,result))
        return result
    monkeypatch.setattr(case,'solve_unsprung_joint',selected)
    first=case.solve(REFERENCE_DESIGN)[0]
    second=case.solve(REFERENCE_DESIGN)[0]
    assert DIAGNOSTIC.digest(first)==DIAGNOSTIC.digest(second) and len(checked)==2
    assert (None if previous is None else previous.tobytes())==before
    if hint.current is not None:
        assert hint.current.shape==(34,34) and not hint.current.flags.writeable
        assert previous is None or not np.shares_memory(hint.current,previous)


def test_two_nearby_states_reuse_unscaled_direction_but_both_satisfy_original_equations(monkeypatch):
    hints=[];checks=[]
    def selected(*args,**kwargs):
        hint=JointJacobianHint(None if not hints else hints[-1].current)
        model=model_for(args,kwargs)
        result=solve_unsprung_joint(*args,**kwargs,jacobian_hint=hint)
        hints.append(hint);checks.append(verify_result(model,result))
        return result
    monkeypatch.setattr(case,'solve_unsprung_joint',selected)
    case.solve(REFERENCE_DESIGN,finite_geometry=True)
    case.solve(replace(REFERENCE_DESIGN,mass=REFERENCE_DESIGN.mass*1.01),speed=20.01,finite_geometry=True)
    assert hints[0].current is hints[1].previous and len(checks)==2


@pytest.mark.parametrize('changed',['config','dt','ratio','sync'])
def test_vehicle_rejects_seed_after_parameter_step_or_transmission_structure_change(monkeypatch,changed):
    run=experiment();captured=[];original=UnsprungAdvanceInput.solve
    def solve(source,**kwargs):
        captured.append(source.jacobian_hint.previous)
        return original(source,**kwargs)
    try:
        run.step();car=run.experiment.simulation.player
        prior=car._unsprung_jacobian;assert prior is not None
        config,key,matrix=prior;dt,ratio,sync=key
        if changed=='config':config=replace(config)
        elif changed=='dt':dt*=2
        elif changed=='ratio':ratio+=1
        else:sync=not sync
        car._unsprung_jacobian=config,(dt,ratio,sync),matrix
        monkeypatch.setattr(UnsprungAdvanceInput,'solve',solve)
        run.step()
        assert captured[0] is None
        assert captured[1] is not None
    finally:run.close()


def test_warm_input_roundtrip_keeps_prior_seed_but_omits_derived_output(tmp_path,monkeypatch):
    run=experiment();original=UnsprungAdvanceInput.solve;captures=[]
    def solve(source,**kwargs):
        result=original(source,**kwargs)
        if source.jacobian_hint.previous is not None and not captures:
            assert source.jacobian_hint.current is not None
            path=tmp_path/'warm-step.pkl';save_step(source,path)
            loaded=load_step(path)
            assert loaded.jacobian_hint.current is None
            assert loaded.jacobian_hint.previous.tobytes()==source.jacobian_hint.previous.tobytes()
            assert loaded.jacobian_hint is not source.jacobian_hint
            captures.append((path,DIAGNOSTIC.digest(result)))
        return result
    try:
        monkeypatch.setattr(UnsprungAdvanceInput,'solve',solve)
        run.step()
    finally:run.close()
    assert captures
    path,expected=captures[0]
    assert DIAGNOSTIC.digest(original(load_step(path)))==expected
    assert DIAGNOSTIC.digest(original(load_step(path)))==expected


def test_seed_is_vehicle_local_and_initialization_clears_it():
    first,second=experiment(),experiment()
    try:
        a,b=first.experiment.simulation.player,second.experiment.simulation.player
        assert a._unsprung_jacobian is None and b._unsprung_jacobian is None
        first.step()
        assert a._unsprung_jacobian is not None and b._unsprung_jacobian is None
        matrix=a._unsprung_jacobian[2]
        second.step()
        assert not np.shares_memory(matrix,b._unsprung_jacobian[2])
        a.initialize_rolling(5.)
        assert a._unsprung_jacobian is None
        first.step()
        assert a._unsprung_jacobian is not None
        a.reset(a.spawn,speed=0.)
        assert a._unsprung_jacobian is None
    finally:first.close();second.close()


def test_warm_actual_unsprung_record_recalculates_every_snapshot_and_command(tmp_path):
    run=experiment(.6)
    try:
        while not run.done:run.step()
        assert run.experiment.simulation.player._unsprung_jacobian is not None
        record=LabRecord.from_run(run)
    finally:run.close()
    export_record(record,tmp_path/'warm-record')
    loaded=load_record(tmp_path/'warm-record')
    repeated=recalculate(loaded)
    assert loaded.snapshots==repeated.snapshots==record.snapshots
    assert loaded.samples==repeated.samples==record.samples
    assert loaded.commands==repeated.commands==record.commands
