"""从实际同源细化报告绘制原始残差；参照斜率不是误差拟合或闭合判据。"""

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
    data=json.loads((ROOT/"logs/SIM-UNSPRUNG-01/energy-refinement-report-r2/result.json").read_text(encoding="utf-8"))
    output=ROOT/"docs/evidence/SIM-UNSPRUNG-01/energy-refinement"
    output.mkdir(parents=True,exist_ok=True)
    font=FontProperties(fname=ROOT/"assets/game/ui/fonts/SourceHanSansSC-Bold.otf")
    font_manager.fontManager.addfont(font.get_file())
    plt.rcParams.update({"font.family":font.get_name(),"font.weight":"bold","font.size":10,
                         "axes.titleweight":"bold","axes.labelweight":"bold","mathtext.fontset":"stix"})
    fig,axes=plt.subplots(1,2,figsize=(10.8,4),layout="constrained")
    n=np.array([row["substeps"] for row in data["results"]])
    for axis,key,title,order in zip(axes,("raw_energy_sum_J","raw_energy_abs_peak_J"),
            ("累计原始残差幅值","单机械步原始残差峰值"),(1,2),strict=True):
        values=np.array([abs(row[key]) for row in data["results"]])
        axis.loglog(n,values,"o-",color="#247e96",lw=2,label="实际原生世界结果")
        axis.loglog(n,values[-1]*(n[-1]/n)**order,"--",color="#f47c24",lw=1.4,
                    label="一阶参照斜率" if order==1 else "二阶参照斜率")
        axis.set(title=title,xlabel="每120 Hz拍机械子步数",ylabel="能量 / J")
        axis.set_xticks(n,labels=[str(value) for value in n])
        axis.grid(alpha=.2,which="both")
        axis.legend(frameon=False,fontsize=9)
    fig.suptitle("同一非线性部件/安装候选 · 实体凸起2.4 s\n2子步复用已有完整节点；4/8实际运行；原始残差仍非零",fontproperties=font,fontsize=12)
    fig.savefig(output/"refinement.png",dpi=160)
    fig.savefig(output/"refinement.svg")
    plt.close(fig)


if __name__=="__main__":plot()
