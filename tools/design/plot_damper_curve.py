"""从已保存实际输入/拟合报告绘制合成力速表、留出及零速线性近似。"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[2]


def plot():
    document=json.loads((ROOT/"logs/SIM-UNSPRUNG-01/damper-curve-energy-input-r1/candidate-vehicle.json").read_text(encoding="utf-8"))
    report=document["metadata"]["suspension_calibration"]
    output=ROOT/"docs/evidence/SIM-UNSPRUNG-01/damper-curve"
    output.mkdir(parents=True,exist_ok=True)
    font=FontProperties(fname=ROOT/"assets/game/ui/fonts/SourceHanSansSC-Bold.otf")
    font_manager.fontManager.addfont(font.get_file())
    plt.rcParams.update({"font.family":font.get_name(),"font.weight":"bold","font.size":10,
                         "axes.titleweight":"bold","axes.labelweight":"bold"})
    fig,axes=plt.subplots(1,2,figsize=(10.8,4),layout="constrained")
    for axis,kind,label in zip(axes,("compression","extension"),("压缩 / 正速度","伸张 / 负速度"),strict=True):
        rows=[row for row in report["input"]["corners"]["FL"]["rows"] if row["kind"]==kind]
        for split,marker,color in (("train","o","#247e96"),("validation","x","#f47c24")):
            points=[row for row in rows if row["split"]==split]
            axis.scatter([abs(row["input"]) for row in points],[abs(row["force_N"]) for row in points],
                         marker=marker,color=color,s=35,label="训练节点" if split=="train" else "独立序列留出",zorder=3)
        train=sorted((abs(row["input"]),abs(row["force_N"])) for row in rows if row["split"]=="train")
        velocity=np.linspace(0.,.85,200)
        node_x,node_y=np.asarray(train).T
        curve=np.interp(velocity,node_x,node_y)
        outer=velocity>node_x[-1]
        curve[outer]=node_y[-1]+(velocity[outer]-node_x[-1])*(node_y[-1]-node_y[-2])/(node_x[-1]-node_x[-2])
        axis.plot(velocity,curve,color="#247e96",lw=1.8,label="分段力速表")
        rate=report["results"]["FL"][kind]["component_rate"]
        axis.plot(velocity,rate*velocity,"--",color="#7d858a",lw=1.3,label="同零速斜率线性近似")
        axis.set(title=label,xlabel="活塞速度幅值 / m/s",ylabel="部件阻力幅值 / N")
        axis.grid(alpha=.2)
        axis.legend(frameon=False,fontsize=9)
    fig.suptitle("合成渐消减振器台架夹具 · 非实测\n转折速度0.05 m/s；高速度段斜率为低速段的1/4",fontproperties=font,fontsize=12)
    fig.savefig(output/"force-speed.png",dpi=160)
    fig.savefig(output/"force-speed.svg")
    plt.close(fig)


if __name__=="__main__":plot()
