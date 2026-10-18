# VALIDATION-FONT-01 字体扫描区分替换输入与显示文字

- 状态：done（实际显示字符/固定来源检查通过）；基线main/9e1014e，工作区干净。
- 触发：T2-after-compliance在763通过后命中WORKSPACE-ART-02已留证的旧字体误报：把replace("s⁻¹", "1/s")的输入匹配字符⁻当成最终显示字形。
- 范围：tests/test_ui_theme.py的AST采集，仅排除str.replace首参数匹配字面量；输出字面量、其他界面常量与固定字体/许可哈希检查保持。禁止换字体、删除实际文案或忽略实际缺字。
- 验收：完整ui_theme T1/三种子；扫描实际来源依据解释，输入模式不进入显示字符、替换输出仍扫描。原失败和既有实界面证据保持。

- 完整ui_theme T1 5项/三种子通过。仅排除replace输入匹配字面量，替换输出1/s与其他所有界面字符串继续检查；字体/图标/许可SHA、对比度检查保持。原763通过/1误报在[证据](../evidence/VALIDATION-FONT-01/)。
- 命令`tools/validate.py T1 --tests tests/test_ui_theme.py --output logs/validation/VALIDATION-FONT-01-T1 --timeout 300`。继续余277项与未执行T2长测；生产未改。
