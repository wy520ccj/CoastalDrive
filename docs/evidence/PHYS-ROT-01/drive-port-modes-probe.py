"""定向覆盖九种离合/齿轮活动集，包含完整世界惯量与不平行后轮轴。"""

import json
import math
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_name("drive-port-modes-initial")
proof = runpy.run_path(str(Path(__file__).with_name("drive-port-active-probe.py")))
active, nested, limits, dot = (proof[name] for name in ("active", "nested", "limits", "dot"))
hashes = proof["source_hashes"]


def run():
    OUT.mkdir(exist_ok=False)
    (OUT / "source.py").write_bytes(Path(__file__).read_bytes())
    (OUT / "active-source.py").write_bytes(Path(__file__).with_name("drive-port-active-probe.py").read_bytes())
    before = hashes()
    theta = .63
    rotation = ((math.cos(theta), 0., math.sin(theta)), (0., 1., 0.), (-math.sin(theta), 0., math.cos(theta)))
    principal = (1900., 510., 2200.)
    tensor = tuple(tuple(sum(rotation[a][c] * rotation[b][c] / principal[c] for c in range(3)) for b in range(3)) for a in range(3))
    body_inertia = tuple(tuple(sum(rotation[a][c] * rotation[b][c] * principal[c] for c in range(3)) for b in range(3)) for a in range(3))
    je, jw, drag, gross = .2, 1.15, .6, 140.
    ae = (0., math.cos(.2), math.sin(.2))
    eleft, eright = (math.cos(.3), 0., math.sin(.3)), (math.cos(.4), 0., -math.sin(.4))
    ge = tuple(-v for v in ae) + (1., 0., 0.)
    def minv(vector):
        return tuple(dot(row, vector[:3]) for row in tensor) + (vector[3] / je, vector[4] / jw, vector[5] / jw)
    def mass(vector):
        return tuple(dot(row, vector[:3]) for row in body_inertia) + (je * vector[3], jw * vector[4], jw * vector[5])
    trials = []
    for h in (1 / 240, 1 / 960):
        mg = minv(ge)
        factor = h * drag / (1 + h * drag * dot(ge, mg))
        def mobility(v):
            result = minv(v)
            return tuple(result[i] - factor * mg[i] * dot(mg, v) for i in range(6))
        for ratio in (-12., 12.):
            axes = tuple(ratio / 2 * (eleft[a] + eright[a]) for a in range(3))
            gc = tuple(-ae[a] - axes[a] for a in range(3)) + (1., -ratio / 2, -ratio / 2)
            gl = axes + (0., ratio / 2, ratio / 2)
            dcc, dcl, dll = dot(gc, mobility(gc)), dot(gc, mobility(gl)), dot(gl, mobility(gl))
            determinant = dcc * dll - dcl * dcl
            for eta in (.88, 1.):
                for cmode in ("locked", "positive-slip", "negative-slip"):
                    for gmode in ("static", "positive-motion", "negative-motion"):
                        capacity = 300.
                        clutch = 120. if cmode == "locked" else (capacity if cmode == "positive-slip" else -capacity)
                        slip = 0. if cmode == "locked" else (40. if cmode == "positive-slip" else -40.)
                        speed = 0. if gmode == "static" else (40. if gmode == "positive-motion" else -40.)
                        low, high = limits(clutch, eta)
                        loss = (low + high) / 2 if gmode == "static" else (high if gmode == "positive-motion" else low)
                        dfree, xfree = slip + h * (dcc * clutch + dcl * loss), speed + h * (dcl * clutch + dll * loss)
                        a = (dll * dfree - dcl * xfree) / determinant
                        b = (dcc * xfree - dcl * dfree) / determinant
                        qfree = tuple(a * mobility(gc)[i] + b * mobility(gl)[i] for i in range(6))
                        ue_free = dot(ge, qfree)
                        q0 = tuple(qfree[i] + h * mg[i] * (drag * ue_free - gross) for i in range(6))
                        result, candidates = active(dfree, xfree, dcc, dcl, dll, h, capacity, eta)
                        assert max(abs(result[i] - (clutch, loss, slip, speed)[i]) for i in range(4)) < 1e-9
                        reference = nested(dfree, xfree, dcc, dcl, dll, h, capacity, eta)
                        assert max(abs(result[i] - reference[i]) for i in range(2)) < 1e-8
                        qend = tuple(qfree[i] - h * (clutch * mobility(gc)[i] + loss * mobility(gl)[i]) for i in range(6))
                        ue, change = dot(ge, qend), tuple(qend[i] - q0[i] for i in range(6))
                        error = (.5 * (dot(qend, mass(qend)) - dot(q0, mass(q0)) + dot(change, mass(change)))
                                 + h * (drag * ue**2 + clutch * slip + loss * speed - gross * ue))
                        assert abs(error) < 3e-9
                        trials.append({"h":h,"ratio":ratio,"eta":eta,"expected":[cmode,gmode],"result":result,
                                       "capacity":capacity,"q0":q0,"qend":qend,"clutch":clutch,"loss":loss,
                                       "slip":slip,"speed":speed,"candidates":candidates,"nested":reference,"energy_error":error})
    after = hashes()
    assert before == after
    report = {"claim":"72 directed fixed-mobility port trials; no tire/gyro/native evolution; prototype only",
              "source_before":before,"source_after":after,"source_stable":before==after,
              "inverse_body_tensor":tensor,"engine_axis":ae,"left_axis":eleft,"right_axis":eright,
              "engine_inertia":je,"wheel_inertia":jw,"drag":drag,"gross":gross,"trials":trials,
              "maximum_energy_error_j":max(abs(t["energy_error"]) for t in trials)}
    (OUT / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print({"trials":len(trials),"source_stable":before==after,"maximum_energy_error_j":report["maximum_energy_error_j"]})


if __name__ == "__main__":
    run()
