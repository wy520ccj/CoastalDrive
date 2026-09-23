# 阶段 6B 增量：环境画面与基础声音

状态：进行中。这份记录只列出当前已接入的内容，不代表完整 6B 验收。

## 已接入内容

- 天空穹顶使用 Poly Haven 的 Industrial Sunset Pure Sky；道路与地面分别使用 Asphalt Floor 和 Grass Ground 漫反射贴图。
- 滨海道路加入代码生成的海面波纹纹理；道路两侧加入简洁的路边标杆。
- 弯坡道路增加 Kenney Nature Kit 的另一种松树和灌木，丰富路边植被层次。
- HUD 状态和操作提示增加半透明底板，提升文字在不同背景上的可读性。
- 驾驶声音已按玩家试听反馈替换为录音：怠速与提速发动机两段随转速混合，车内道路声随车速轻声加入。碰撞播放轻碰、侧向金属撞击、金属护栏擦碰或重撞录音，按相邻状态的车辆速度变化估算类别。
- 当前碰撞快照不暴露接触物种类/接触法线，因此擦碰和撞击类别属于声音层运动学估算，不代表识别到实际护栏或碰撞对象。用户最新实际试听不通过：常听到单一、类似盒子落地的无力声音，情形区分和播放时机不符合预期。碰撞声音迭代已按要求暂停；自动测试不代表实际听感验收通过。

## 素材来源

素材来源及本地记录见 [asset-register.csv](asset-register.csv)。天空：[Poly Haven Industrial Sunset Pure Sky](https://polyhaven.com/a/industrial_sunset_puresky)，CC0；路面：[Poly Haven Asphalt Floor](https://polyhaven.com/a/asphalt_floor)，CC0；草地：[Poly Haven Grass Ground](https://polyhaven.com/a/grass_ground)，CC0；松树与灌木：[Kenney Nature Kit](https://kenney.nl/assets/nature-kit)，CC0。海面纹理由项目代码生成。声音取自 [qubodup 的发动机录音循环](https://opengameart.org/content/car-engine-loop-96khz-4s)（CC-BY 3.0）、[microman502 的怠速录音](https://freesound.org/people/microman502/sounds/818291/)、[priesjensen 的车内行驶录音](https://freesound.org/people/priesjensen/sounds/495795/)和 Pól 的 [塑料护栏轻撞](https://freesound.org/people/P%C3%B3l/sounds/385940/)、[金属撞击](https://freesound.org/people/P%C3%B3l/sounds/385937/)、[金属护栏擦碰](https://freesound.org/people/P%C3%B3l/sounds/385939/)及[岩面重撞](https://freesound.org/people/P%C3%B3l/sounds/385938/)（均 CC0）；加工和署名见 `assets/game/audio/License.txt`。

## 当前渲染证据

- [滨海画面](screenshots/phase6b-coastal.png)：0.8.1 独立版的滨海道路、天空及路面/草地贴图离屏画面；原始记录在 `logs/phase6b/package-coastal/`。
- [弯坡高速画面](screenshots/phase6b-highway.png)：弯坡道路加入松树和灌木后的离屏画面；原始记录在 `logs/phase6b/hills-nature/`。

0.8.1 独立版的旧证据只适用于当时合成的三段 WAV；它不包含本轮替换的声音。玩家试听指出旧路噪过吵且不真实、发动机听感差、碰撞有刹车/玻璃前奏且不适合所有接触。本轮录音替换和碰撞分型后仍需玩家再次试听。

以上截图用于确认原有画面资源已进入渲染路径。新声音的真实听感仍待复听；完整 6B 画面验收、性能测量和人工驾驶检查也尚未完成。当前声音与美术仍属增量原型，不能据此宣称 6B 完成。
