"""从已保存的真实原生世界轨迹绘制簧下质量对比；仅开发图表依赖Matplotlib。"""

import argparse
import csv
from pathlib import Path

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT = Path(__file__).resolve().parents[2]


def plot(source, output):
    font = FontProperties(fname=str(ROOT/"assets/game/ui/fonts/SourceHanSansSC-Bold.otf"))
    plt.rcParams.update({"axes.unicode_minus":False,"figure.dpi":170,"axes.spines.top":False,"axes.spines.right":False})
    fig,axes = plt.subplots(3,1,figsize=(9,8),sharex=True,layout="constrained")
    fig.get_layout_engine().set(rect=(0.,.065,1.,.935))
    for mass,color in zip((25,40,65),("#21859a","#fc7b24","#193542")):
        folder = source/("native-physical-step2" if mass==40 else f"native-physical-mass{mass}")
        with (folder/"trajectory.csv").open(encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        time = np.array([float(row["time"]) for row in rows])
        for axis,key,scale in zip(axes,("normal_force_0","relative_v_0","body_az"),(.001,1.,1.)):
            axis.plot(time,[float(row[key])*scale for row in rows],color=color,lw=1.7,label=f"{mass} kg")
    labels = ("左前轮法向轮荷 / kN","左前轮相对车身速度 / (m/s)","簧上质心垂向加速度 / (m/s²)")
    for axis,label in zip(axes,labels):
        axis.set_ylabel(label,fontproperties=font)
        axis.grid(alpha=.17)
        axis.set_facecolor("#fcfbf7")
    axes[0].axhline(2.943,color="#9ba4a3",ls="--",lw=.8)
    axes[0].legend(loc="upper right",frameon=False)
    axes[2].set_xlabel("时间 / s",fontproperties=font)
    fig.suptitle("实际 10 mm 实体凸起：簧下质量影响轮荷与车身响应",fontproperties=font,fontsize=16)
    fig.text(.52,.008,"假设质量/径向参数 · 同一 1200 kg 总量 · 5 m/s · 120 Hz / 两子步\n"
             "新 Bullet 世界节点，尚未接入生产试验台；并非实测或整车收敛验收",
             fontproperties=font,ha="center",fontsize=9,color="#63716f")
    fig.savefig(output,bbox_inches="tight")
    plt.close(fig)


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    plot(args.source,args.output)
