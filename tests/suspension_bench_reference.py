"""有明确解析真值的合成部件数据，只用于验证算法，不作为实测资源。"""

import json

from suspension_bench import DEFINITION, SCHEMA, UNITS, WHEELS


def document(*, bad_validation=False):
    corners = {}
    for index, wheel in enumerate(WHEELS):
        front = index < 2
        rates = {"spring": 60000. if front else 50000., "compression": 6000. if front else 5000.,
                 "extension": 3000. if front else 2500.}
        rows = []
        for kind, rate in rates.items():
            for split in ("train", "validation"):
                inputs = ((0., .012, .035, .08, .14, .22) if kind == "spring" else (0., .02, .05, .15, .35, .8)) if split == "train" else (
                    (0., .009, .031, .07, .15, .23) if kind == "spring" else (0., .015, .06, .2, .4, .85))
                for i, value in enumerate(inputs):
                    x = -value if kind == "extension" else value
                    force = rate*x
                    if bad_validation and split == "validation" and value > .1:
                        force *= 1.4
                    rows.append({"series": f"{wheel}-{kind}-{split}", "split": split,
                                 "kind": kind, "input": x, "force_N": force})
        corners[wheel] = {"spring_id": "synthetic-spring-front" if front else "synthetic-spring-rear",
            "damper_id": "synthetic-damper-front" if front else "synthetic-damper-rear",
            "spring_motion_ratio": .8 if front else .9, "damper_motion_ratio": .75 if front else .85,
            "installation_source": "synthetic constant linkage, zero preload; NOT measured K&C", "rows": rows}
    return {"schema": SCHEMA, "source": "analytic synthetic spring/damper fixture, NOT measured",
            "source_kind": "synthetic", "temperature_c": 20., "units": UNITS.copy(),
            "definition": DEFINITION, "corners": corners}


def write_bench(path, **kwargs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document(**kwargs), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return path
