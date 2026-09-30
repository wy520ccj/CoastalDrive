# VEH-01 当前证据

这些图片是Panda3D实际渲染。front-red/rear-red/side-red采用专门检查相机；garage-ui是原车库界面，driving-140是1080p八车自动实际驾驶截图。before-material-front-red是同机位发白修正前的版本，仅供比较。最终图片仍等待用户视觉判断。

- T1-summary：55项相关测试通过，三种子headless通过。
- garage-check：两车型五色，应用/取消/世界冻结/保存失败/驾驶流程通过。
- package-smoke：独立包在仓库外启动退出0；package-resources记录GLB/反射/资产清单与源文件一致。
- 侧碰6项通过，记录 logs/VEH-01/side-collision.log。
- short-drive是365m短程留证；包含启动与截图开销，不是60FPS性能Gate。
- 打包仍有本机已有 api-ms-win-core-path-l1-1-0.dll / PROPSYS.dll 依赖警告，干净机器验收未做。

本任务不等于Visual v1整体通过。玻璃是不透明近似，没有驾驶室内饰，反射是预过滤的静态环境，没有实时镜面/车损/动态灯逻辑。车型物理参数差异已获许可但本轮未实现，现有驾驶数值不变。

1080p/8车/30秒预热+300秒独立采样：平均58.15FPS，P95 20.34ms；平均帧率未达60FPS，性能Gate未通过。正式采样丢时0.016667秒，预热丢时2.308333秒。不得把路线passed=true当成performance_gate_passed=true。
