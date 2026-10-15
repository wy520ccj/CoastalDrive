"""用实际原生释放样本绘制行程/力与解析解，不生成或修改游戏图像资产。"""

import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[2]


def plot():
    source=ROOT/"logs/SIM-UNSPRUNG-01/preload-release-r2"
    output=ROOT/"docs/evidence/SIM-UNSPRUNG-01/preload"
    output.mkdir(parents=True,exist_ok=True)
    result=json.loads((source/"result.json").read_text(encoding="utf-8"))
    font=FontProperties(fname=ROOT/"assets/game/ui/fonts/SourceHanSansSC-Bold.otf")
    plt.rcParams.update({"font.family":font.get_name(),"font.size":11,"font.weight":"bold",
                         "axes.titleweight":"bold","axes.labelweight":"bold","mathtext.fontset":"stix"})
    # 显式登记已有本地字体，不安装系统字体。
    from matplotlib import font_manager
    font_manager.fontManager.addfont(font.get_file())
    fig,axes=plt.subplots(1,2,figsize=(10.8,4),layout="constrained")
    colors=("#247e96","#f47c24","#755994")
    for count,color in zip((2,4,8),colors,strict=True):
        with (source/f"samples-{count}.csv").open(encoding="utf-8",newline="") as stream:
            rows=list(csv.DictReader(stream))
        time=[0.,*[float(row["time_s"]) for row in rows]]
        axes[0].plot(time,[0.,*[float(row["q_mean_m"])*1000 for row in rows]],color=color,label=f"{count}机械子步",lw=1.8)
        axes[1].plot(time,[960.,*[float(row["spring_force_max_N"]) for row in rows]],color=color,lw=1.8)
    times=np.linspace(0.,.125,400)
    omega,release=result["omega_rad_s"],result["analytic_release_time_s"]
    q=[.02*(math.cos(omega*t)-1) if t<=release else -.02-.02*omega*(t-release) for t in times]
    axes[0].plot(times,np.asarray(q)*1000,"--",color="#122e3a",lw=1.5,label="连续解析解")
    axes[1].plot(times,[max(0.,48000*(value+.02)) for value in q],"--",color="#122e3a",lw=1.5)
    for axis,title,ylabel in zip(axes,("实际轮心相对行程","实际弹簧力 / 单角峰值"),("q / mm","F / N"),strict=True):
        axis.set(title=title,xlabel="t / s",ylabel=ylabel)
        axis.axvline(release,color="#8c9698",lw=.8,ls=":")
        axis.grid(alpha=.2)
    axes[0].legend(frameon=False,fontsize=10)
    fig.suptitle("安装预压释放：实际五刚体与解析极限\n无空气 / 无阻尼；仅初值离地，重力和碰撞保留",fontproperties=font,fontsize=13)
    fig.savefig(output/"release.png",dpi=160)
    fig.savefig(output/"release.svg")
    plt.close(fig)


if __name__=="__main__":plot()
