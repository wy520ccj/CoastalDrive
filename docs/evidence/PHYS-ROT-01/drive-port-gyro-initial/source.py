"""传动预研：完整惯量下曲轴摩擦、转子输运和有限传动同末状态。"""

import json
import math
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_name("drive-port-gyro-initial")
proof_path = Path(__file__).with_name("drive-port-active-probe.py")
proof = runpy.run_path(str(proof_path))
active, dot, hashes = (proof[name] for name in ("active", "dot", "source_hashes"))


def cross(a, b):
    return a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]


def trial(h, ratio, gross, capacity, bank, eta, engine_gyro=True):
    principal, je, jw, drag = (1900., 510., 2200.), .2, 1.15, .12
    angle = .63
    rotation = ((math.cos(angle), 0., math.sin(angle)), (0., 1., 0.), (-math.sin(angle), 0., math.cos(angle)))
    tensor = tuple(tuple(sum(rotation[a][c] * rotation[b][c] / principal[c] for c in range(3)) for b in range(3)) for a in range(3))
    inertia = tuple(tuple(sum(rotation[a][c] * rotation[b][c] * principal[c] for c in range(3)) for b in range(3)) for a in range(3))
    ae = (0., math.cos(.2), math.sin(.2))
    def axis(steer):
        return math.cos(steer)*math.cos(bank), -math.sin(steer), math.cos(steer)*math.sin(bank)
    axes = (axis(.3), axis(.28), axis(0.), axis(0.))
    rear = tuple(ratio / 2 * (axes[2][a] + axes[3][a]) for a in range(3))
    ge = tuple(-v for v in ae) + (1., 0., 0., 0., 0.)
    gc = tuple(-ae[a] - rear[a] for a in range(3)) + (1., 0., 0., -ratio/2, -ratio/2)
    gl = rear + (0., 0., 0., ratio/2, ratio/2)
    def mass(v):
        return tuple(dot(row, v[:3]) for row in inertia) + (je*v[3],) + tuple(jw*x for x in v[4:])
    def minv(v):
        return tuple(dot(row, v[:3]) for row in tensor) + (v[3]/je,) + tuple(x/jw for x in v[4:])
    mg = minv(ge)
    factor = h*drag/(1+h*drag*dot(ge, mg))
    def mobility(v):
        response = minv(v)
        return tuple(response[i]-factor*mg[i]*dot(mg, v) for i in range(8))
    dcc, dcl, dll = dot(gc, mobility(gc)), dot(gc, mobility(gl)), dot(gl, mobility(gl))
    q0 = (.03, -.02, .2, 220., 60., 60., 42., 78.)
    def spin(q, include_engine=True):
        return tuple((je*q[3]*ae[a] if include_engine else 0.) - jw*sum(q[i+4]*axes[i][a] for i in range(4)) for a in range(3))
    def evaluate(q):
        gyro = cross(spin(q, engine_gyro), q[:3]) + (0.,)*5
        known = tuple(mass(q0)[i] + h*(gross*ge[i]+gyro[i]) for i in range(8))
        qfree = mobility(known)
        result, labels = active(dot(gc, qfree), dot(gl, qfree), dcc, dcl, dll, h, capacity, eta)
        clutch, loss = result[:2]
        end = tuple(qfree[i]-h*(clutch*mobility(gc)[i]+loss*mobility(gl)[i]) for i in range(8))
        return end, result, labels
    q = q0
    iterations = []
    for iteration in range(50):
        end, result, labels = evaluate(q)
        residual = max(abs(end[i]-q[i]) for i in range(8))
        iterations.append(residual)
        q = end
        if residual < 1e-12:
            break
    else:
        raise ArithmeticError("共同传动/输运末状态不收敛")
    check, result, labels = evaluate(q)
    assert max(abs(check[i]-q[i]) for i in range(8)) < 1e-12
    clutch, loss, slip, speed, cmode, gmode = result
    ue, change = dot(ge, q), tuple(q[i]-q0[i] for i in range(8))
    energy = (.5*(dot(q,mass(q))-dot(q0,mass(q0))+dot(change,mass(change)))
              + h*(drag*ue**2+clutch*slip+loss*speed-gross*ue))
    assert abs(energy) < 3e-9
    spin_start, spin_end = spin(q0), spin(q)
    momentum = tuple(dot(inertia[a], change[:3])+spin_end[a]-spin_start[a]+h*cross(q[:3],spin_end)[a] for a in range(3))
    if engine_gyro:
        assert max(abs(v) for v in momentum) < 1e-10
    else:
        missing = cross(q[:3], tuple(je*q[3]*v for v in ae))
        assert max(abs(momentum[a]-h*missing[a]) for a in range(3)) < 1e-10
        assert max(abs(v) for v in momentum) > 1e-7
    return {"h":h,"ratio":ratio,"gross":gross,"capacity":capacity,"bank":bank,"eta":eta,
            "engine_gyro":engine_gyro,"inertia":inertia,"je":je,"jw":jw,"drag":drag,"ae":ae,"axes":axes,
            "q0":q0,"qend":q,"clutch":clutch,"loss":loss,"slip":slip,"speed":speed,
            "clutch_mode":cmode,"gear_mode":gmode,"labels":labels,"iteration_residuals":iterations,
            "energy_error_j":energy,"momentum_error_nms":momentum,"spin_end":spin_end}


def main():
    OUT.mkdir(exist_ok=False)
    (OUT/"source.py").write_bytes(Path(__file__).read_bytes())
    (OUT/"active-source.py").write_bytes(proof_path.read_bytes())
    before = hashes()
    trials = [trial(h, ratio, gross, capacity, bank, eta)
              for h in (1/240,1/960) for ratio in (-12.,12.)
              for gross,capacity in ((160.,300.),(0.,300.),(160.,0.))
              for bank in (-.3,0.,.3) for eta in (.88,1.)]
    trials.extend(trial(h,12.,160.,300.,.3,.88,engine_gyro=False) for h in (1/240,1/960))
    after = hashes()
    assert before == after
    report = {"claim":"72 fixed-world-axis airborne joint port/drag/gyro steps and two missing-engine-gyro negatives; no contacts or finite world integration; prototype only",
              "source_before":before,"source_after":after,"source_stable":before==after,"trials":trials,
              "maximum_energy_error_j":max(abs(t["energy_error_j"]) for t in trials),
              "maximum_positive_momentum_error_nms":max(max(abs(v) for v in t["momentum_error_nms"]) for t in trials if t["engine_gyro"]),
              "maximum_iterations":max(len(t["iteration_residuals"]) for t in trials)}
    (OUT/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    print({k:report[k] for k in ("maximum_energy_error_j","maximum_positive_momentum_error_nms","maximum_iterations","source_stable")})


if __name__ == "__main__":
    main()
