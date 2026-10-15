"""离线科学图：纯滑移拟合/留出及联合滑移验证，来源分类进入图标题。"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))

from tire_calibration import load_bench, predict
from vehicle_designs import vehicle_design
from vehicle_parameters import config_from_document


def render(folder, output):
    bench = load_bench(folder/"input.csv", folder/"conditions.json")
    document = json.loads((folder/"candidate-vehicle.json").read_text(encoding="utf-8"))
    config = config_from_document(document, vehicle_design("reference-rwd").config)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    fig.set_facecolor("#fefcf5")
    for ax in axes.flat:
        ax.set_facecolor("#fefcf5")
        ax.grid(alpha=.2)
    for ax, kind, slip_key, component in ((axes[0, 0], "longitudinal", "kappa", 0),
                                         (axes[0, 1], "lateral", "alpha_rad", 1)):
        for split, marker, color in (("train", ".", "#859898"), ("validation", "o", "#f47c24")):
            rows = [row for row in bench.rows if row["kind"] == kind and row["split"] == split]
            ax.scatter([row[slip_key] for row in rows], [row[("fx_N", "fy_N")[component]] for row in rows],
                       marker=marker, c=color, s=20, label=split+" data")
        for load in sorted({row["fz_N"] for row in bench.rows if row["split"] == "validation"}):
            rows = [{"fz_N": load, "kappa": value if component == 0 else 0.,
                     "alpha_rad": value if component == 1 else 0.} for value in np.linspace(-.3, .3, 161)]
            ax.plot(np.linspace(-.3, .3, 161), predict(rows, config)[:, component], lw=1.5,
                    label=f"model at {load:g} N")
        ax.set(xlabel="Slip ratio" if component == 0 else "Slip angle / rad",
               ylabel="Fx / N" if component == 0 else "Fy / N", title="Pure "+kind)
        ax.legend(fontsize=8)
    combined = [row for row in bench.rows if row["kind"] == "combined"]
    predictions = predict(combined, config)
    for component, ax in enumerate(axes[1]):
        observed = np.array([row[("fx_N", "fy_N")[component]] for row in combined])
        ax.scatter(observed, predictions[:, component], s=24, c="#247e96")
        limits = [min(observed.min(), predictions[:, component].min()),
                  max(observed.max(), predictions[:, component].max())]
        ax.plot(limits, limits, color="#f47c24", linestyle="--")
        ax.set(xlabel="Held-out data / N", ylabel="Predicted force / N",
               title="Combined slip - "+("Fx", "Fy")[component])
    classification = "SYNTHETIC ALGORITHM CHECK - NOT MEASURED" if bench.conditions["source_kind"] == "synthetic" else "BENCH DATA FIT - VEHICLE VALIDATION SEPARATE"
    fig.suptitle(classification+"\nEntire series held out; 6 fitted parameters; shape and compliance fixed", fontsize=14)
    fig.savefig(output, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.fit.resolve(), args.output.resolve())
