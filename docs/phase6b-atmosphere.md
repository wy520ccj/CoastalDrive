# 阶段 6B 增量：环境画面与基础声音

状态：进行中。这份记录只列出当前已接入的内容，不代表完整 6B 验收。

## 已接入内容

- 天空穹顶使用 Poly Haven 的 Industrial Sunset Pure Sky；道路与地面分别使用 Asphalt Floor 和 Grass Ground 漫反射贴图。
- 滨海道路加入代码生成的海面波纹纹理；道路两侧加入简洁的路边标杆。
- 弯坡道路增加 Kenney Nature Kit 的另一种松树和灌木，丰富路边植被层次。
- HUD 状态和操作提示增加半透明底板，提升文字在不同背景上的可读性。
- 加入项目生成的发动机、路噪和碰撞 WAV。发动机与路噪循环，并随车辆状态调整音量/播放速率；碰撞声由碰撞计数触发并带有短冷却。

## 素材来源

素材来源及本地记录见 [asset-register.csv](asset-register.csv)。天空：[Poly Haven Industrial Sunset Pure Sky](https://polyhaven.com/a/industrial_sunset_puresky)，CC0；路面：[Poly Haven Asphalt Floor](https://polyhaven.com/a/asphalt_floor)，CC0；草地：[Poly Haven Grass Ground](https://polyhaven.com/a/grass_ground)，CC0；松树与灌木：[Kenney Nature Kit](https://kenney.nl/assets/nature-kit)，CC0。海面纹理与三段声音由项目代码生成，不使用第三方音频素材。

## 当前渲染证据

- [滨海画面](screenshots/phase6b-coastal.png)：0.8.1 独立版的滨海道路、天空及路面/草地贴图离屏画面；原始记录在 `logs/phase6b/package-coastal/`。
- [弯坡高速画面](screenshots/phase6b-highway.png)：弯坡道路加入松树和灌木后的离屏画面；原始记录在 `logs/phase6b/hills-nature/`。

0.8.1 独立版已核对 JPG、WAV、GLB/BAM 随包；滨海离屏启动通过，20 次重开后场景节点、任务和事件数量稳定。普通声音设备下，三个 WAV 均已加载，发动机与路噪循环状态正常；目前尚未由人耳试听音量、音色及同步。

以上截图用于确认资源已进入渲染路径。正常游戏中的音频试听仍待完成；完整 6B 画面验收、性能测量和人工驾驶检查也尚未完成。当前声音与美术仍属增量原型，不能据此宣称 6B 完成。
