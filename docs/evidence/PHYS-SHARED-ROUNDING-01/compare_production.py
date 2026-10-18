import hashlib,importlib.util,json,pickle,sys
from pathlib import Path
root=Path.cwd();sys.path[:0]=[str(root/"src"),str(root/"tools")]
base=Path(__file__).resolve().parent
old_path=next(base.glob("production-before-mechanical_kernels*.pyd"))
old_spec=importlib.util.spec_from_file_location("mechanical_kernels",old_path)
old_module=importlib.util.module_from_spec(old_spec);sys.modules["mechanical_kernels"]=old_module;old_spec.loader.exec_module(old_module)
import tire_drivetrain
import pytest
path=next((root/"src").glob("mechanical_kernels*.pyd"))
spec=importlib.util.spec_from_file_location("mechanical_kernels",path)
candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
assert candidate is not old_module and Path(candidate.__file__).resolve()==path.resolve()
original=tire_drivetrain.shared_load_solution
stats={"calls":0,"identical":0,"different":0,"original_errors":0,"error_mismatches":0,"examples":[]}
def compare(*args):
    stats["calls"]+=1
    try: before=original(*args)
    except ArithmeticError:
        stats["original_errors"]+=1
        try: candidate.shared_load_solution(*args)
        except ArithmeticError: pass
        else: stats["error_mismatches"]+=1
        raise
    try: after=candidate.shared_load_solution(*args)
    except ArithmeticError as error:
        stats["different"]+=1
        if len(stats["examples"])<3:stats["examples"].append(str(error))
    else:
        if pickle.dumps(before,protocol=5)==pickle.dumps(after,protocol=5):stats["identical"]+=1
        else:
            stats["different"]+=1
            if len(stats["examples"])<3:stats["examples"].append({"old":repr(before),"candidate":repr(after)})
    return before
tire_drivetrain.shared_load_solution=compare
code=pytest.main(["-q","tests/test_driveline_native.py","tests/test_drivetrain_jacobian.py","tests/test_drivetrain_prepare.py","tests/test_tire_drivetrain.py","tests/test_transmission_ports.py","tests/test_continuous_solver.py"])
stats.update(pytest_exit=code,original_module_sha=hashlib.sha256(Path(old_module.__file__).read_bytes()).hexdigest(),candidate_module_sha=hashlib.sha256(path.read_bytes()).hexdigest())
output=base/sys.argv[1];output.write_text(json.dumps(stats,indent=2),encoding="utf-8")
print(json.dumps(stats))
raise SystemExit(bool(code or stats["different"] or stats["error_mismatches"] or not stats["calls"]))
