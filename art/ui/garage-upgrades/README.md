# 改装零件图来源与加工

原照片按原始字节保留；`*-source.json`为下载时Commons主站API的作者、许可和原图元数据。

| 原件 | 作者/许可 | 运行衍生 |
|---|---|---|
| [Coilovers.jpg](https://commons.wikimedia.org/wiki/File:Coilovers.jpg) | Cameron Chapman / CC-BY-2.0 | `assets/game/ui/garage-v2/suspension-part.png` |
| [Cold air intake tube with filter](https://commons.wikimedia.org/wiki/File:2008-04-01_Cold_air_intake_tube_with_filter.jpg) | Ildar Sagdejev (Specious) / 选择CC-BY-SA-3.0 | `assets/game/ui/garage-v2/power-part.png`，继续CC-BY-SA-3.0 |

2026-10-22先看原照片，再用内置ImageGen去背景、调曝光/白平衡，保留原物件布局与部件，不手画替代品。输出为透明PNG；源图和衍生SHA随证据保存。照片展示的进气盒不宣称适配所有车型，也不作为动力增幅的测量来源。

悬架提示词：Remove only the bedsheet background. Preserve the exact FOUR actual coilovers, blue/black springs, yellow bodies, black collars, silver shafts, original geometry and arrangement. Mild exposure correction; square canvas with margins; true transparency; no logos, text, frame, or invented parts.

动力提示词：Remove only the wood floor. Preserve BOTH actual black intake tube/airbox halves and cream filter, ribs, clips, hoses, original relative layout. Do not invent a cone filter or a performance part. Modest exposure and white balance; square transparent canvas with margins; no added text or logos.

生成原件分别为`exec-7013a51b-fc8c-4a36-bf39-e2f4fc71d000.png`和`exec-6dba80b4-1f68-4b04-8362-95047d4280d6.png`。页面设计以原01布局与这两张衍生为参考，先生成09/10及提示词，再实施控件；设计值为示例，运行时读取实际配置。完整随包署名见`assets/game/ui/garage-v2/Parts-License.txt`。
