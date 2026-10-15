"""就地参数说明与分组浏览；只读取配置和已有试验输入。"""

import json
from dataclasses import asdict

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, OnscreenText
from panda3d.core import CardMaker, Filename, Point2, TextNode, Texture, TransparencyAttrib

from lab_metrics import engineering_analysis
from parameter_formulas import FORMULAS, formula_key
from parameter_help import (
    ALIASES,
    EDITOR_INFO,
    METRIC_INFO,
    explanation,
    group_parameters,
    parameter_group,
)
from paths import resource_root
from ui import theme
from ui.lab_widgets import MUTED, rounded_panel
from vehicle_designs import DESIGN_VEHICLES, GR86_PROFILE_PATH

GROUP_LABELS = {"chassis": "底盘与转向", "tires": "轮胎", "suspension": "悬架",
                "powertrain": "动力与传动", "electronics": "制动与控制"}
BROWSER_LABELS = {"suspension_spring_rates":"轮心等效弹簧率",
                  "suspension_compression_damping":"轮心等效压缩阻尼","suspension_extension_damping":"轮心等效伸张阻尼",
                  "suspension_stiffness":"质量归一化弹簧率",
                  "suspension_compression":"质量归一化压缩阻尼","suspension_relaxation":"质量归一化伸张阻尼"}
OPTION_FIELDS = {"speed": "speed_kph", "duration": "duration", "steer": "steering_deg",
                 "onset": "onset", "radius": "radius_m", "bump_height": "bump_height_m",
                 "bump_length": "bump_length_m", "bump_distance": "bump_distance_m"}


class ParameterHelp:
    def __init__(self, app):
        self.app = app
        self.group, self.page, self.key = "chassis", 0, "speed"
        self.root = DirectFrame(parent=app.root, frameColor=(.04, .10, .14, .55),
                               frameSize=(-1.78, 1.78, -1, 1), sortOrder=110, state=DGG.NORMAL)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        rounded_panel(self.root, "parameter-help-card", (-1.48, 1.55, -.76, .74), theme.PAPER_LIGHT)
        rounded_panel(self.root, "parameter-browser", (-1.40, -.53, -.56, .565), theme.PAPER)
        DirectFrame(parent=self.root, frameColor=theme.ORANGE,
                    frameSize=(-1.41, -1.40, .624, .683))
        app.text("参数计算说明", -1.37, .646, .048, parent=self.root, font=app.heading_font)
        app.button("关闭 · Esc", 1.27, .661, .40, self.hide, parent=self.root)
        self.groups = app.option(list(GROUP_LABELS.values()), -1.37, .486, .76,
                                 self.choose_group, parent=self.root)
        self.buttons = [app.button("", -.99, .365 - i * .09, .76,
                                   lambda index=i: self.choose_item(index), parent=self.root)
                        for i in range(8)]
        app.button("‹", -1.20, -.434, .24, lambda: self.turn(-1), parent=self.root)
        app.button("›", -.78, -.434, .24, lambda: self.turn(1), parent=self.root)
        self.page_label = app.text("", -1.33, -.525, .035, MUTED, parent=self.root)
        self.title = app.text("", -.45, .507, .043, parent=self.root, font=app.heading_font)
        self.details = OnscreenText(parent=self.root, font=app.font, text="", fg=theme.INK,
                                   pos=(-.45, .408), scale=.035, align=TextNode.ALeft,
                                   wordwrap=53, mayChange=True)
        self.notes = OnscreenText(parent=self.root, font=app.font, text="", fg=theme.INK,
                                 pos=(-.45, 0), scale=.033, align=TextNode.ALeft,
                                 wordwrap=57, mayChange=True)
        self.equations = self.root.attachNewNode("typeset-equations")
        self.asset_dir = resource_root() / "assets/game/ui/formulas"
        self.formula_manifest = json.loads((self.asset_dir / "manifest.json").read_text(encoding="utf-8"))
        self.formula_nodes = []
        app.text("名称悬停 / 输入框聚焦 → F1\n左侧可浏览完整模型参数", -1.35, -.658,
                 .035, MUTED, parent=self.root)
        self.refresh_list()
        self.root.hide()

    def hide(self):
        self.root.hide()

    def choose_group(self, label):
        self.group = next(key for key, value in GROUP_LABELS.items() if value == label)
        self.page = 0
        self.refresh_list()

    def refresh_list(self):
        fields = group_parameters(self.group)
        for index, button in enumerate(self.buttons):
            position = self.page * 8 + index
            if position < len(fields):
                info = explanation(fields[position])
                title = BROWSER_LABELS.get(fields[position],info.title)
                button["text"] = title[:13] + ("…" if len(title) > 13 else "")
                button.show()
            else:
                button.hide()
        self.page_label.setText(f"{self.page + 1} / {(len(fields) + 7) // 8}")

    def turn(self, direction):
        last = (len(group_parameters(self.group)) - 1) // 8
        self.page = max(0, min(last, self.page + direction))
        self.refresh_list()

    def choose_item(self, index):
        self.show(group_parameters(self.group)[self.page * 8 + index], switch_group=False)

    def context(self, key):
        app = self.app
        if key in METRIC_INFO:
            record = app.active_record()
            if record is None:
                return "尚无真实试验", "指标值：—"
            summary = record.metadata["summary"]
            analysis = engineering_analysis(record.samples, record.snapshots, summary["options"], summary["reason"])
            item = next(item for item in (*analysis["metrics"], *analysis["ride"]["metrics"])
                        if "metric."+item["key"] == key)
            value = f"{item['value']:.5g}" if item["value"] is not None else "— 未满足工况条件"
            return "已完成试验记录；"+item["note"], "当前指标："+value
        if app.record is not None:
            config = app.record.metadata["vehicle_config"]
            options = app.record.metadata["summary"]["options"]
            basis = "已保存试验配置（说明使用当前源码，不改旧记录）"
            design_id = options["vehicle_id"]
            parameter_metadata = app.record.metadata.get("parameter_metadata")
        elif app.run_state is not None:
            config, options = asdict(app.run_state.config), asdict(app.run_state.options)
            basis = "当前试验的实际配置"
            design_id = options["vehicle_id"]
            parameter_metadata = app.run_state.parameter_metadata
        else:
            design = DESIGN_VEHICLES[app.vehicle_menu.selectedIndex]
            config = asdict(design.config if app.engineered_config is None else app.engineered_config)
            options = {}
            basis = "选中车型的工程配置；尚未试验"
            design_id = design.id
            parameter_metadata = app.parameter_metadata
        field = ALIASES.get(key, key)
        current = str(config[field]) if field in config else "旧记录未保存此字段"
        if "." in field and not field.startswith("manual."):
            parent, child = field.split(".")
            current = str(config[parent][child])
        if field in config:
            fit = parameter_metadata["tire_calibration"] if parameter_metadata is not None and "tire_calibration" in parameter_metadata else None
            fitted = fit is not None and field in fit["parameters"]
            if fit is not None and field == "rear_lateral_stiffness":
                fitted = True
                fitted_value = fit["linked_rear_lateral_stiffness"]
            elif fitted:
                fitted_value = fit["parameters"][field]
            if fitted:
                if config[field] == fitted_value:
                    source = "合成算法恢复值，非实测" if fit["conditions"]["source_kind"] == "synthetic" else "按文件声明：台架数据拟合"
                    conditions = fit["conditions"]
                    basis += f"\n{source}；{conditions['pressure_kpa']:g}kPa / {conditions['temperature_c']:g}°C / {conditions['speed_mps']:g}m/s"
                    if "data_domain" in fit:
                        minimum, maximum = fit["data_domain"]["train"]["fz_N"]
                        basis += f"\n拟合轮荷 {minimum:g}～{maximum:g} N；不覆盖速度/胎压/温度变化"
                    else:
                        basis += "\n旧报告未保存轮荷范围，不能据此声明区间覆盖"
                    basis += "\n计算来源：纯滑移序列最小二乘拟合，独立留出验证"
                    if field == "road_friction":
                        basis += "\nμ为指定轮胎/表面条件下的有效峰值系数"
                else:
                    basis += "\n已覆盖拟合值，不沿用其标定来源"
            elif design_id == "gr86-2022-premium-6mt":
                ledger = json.loads(GR86_PROFILE_PATH.read_text(encoding="utf-8"))["metadata"]["vehicle_fields"][field]
                if json.loads(json.dumps(config[field])) == ledger["value"]:
                    statuses = {"measured": "实测", "oem": "原厂", "derived": "推导",
                                "engineering_prior": "工程初值", "model_mechanism": "模型机制"}
                    basis += f"\n当前车型账本分类：{statuses.get(ledger['status'], ledger['status'])}"
                else:
                    basis += "\n该值已覆盖车型原值，不沿用原来源分类"
            else:
                basis += "\n设计参考值，未作为实车测量数据"
        if key in ALIASES and field not in config:
            current = "旧记录未保存此字段"
        if key in app.entries:
            pending = app.entries[key].get().strip() or "留空，采用车型值"
            if key in OPTION_FIELDS:
                current = str(options.get(OPTION_FIELDS[key], "旧记录未保存此字段")) if options else "尚未试验"
            return basis, f"待运行编辑值：{pending}\n已运行 / 配置值：{current}"
        if key.startswith("manual."):
            return basis, f"手动编辑值：{app.manual_entries[key.split('.')[1]].get()}（按应用输入后生效）"
        if key in EDITOR_INFO:
            menus = {"vehicle": app.vehicle_menu, "maneuver": app.maneuver_menu,
                     "abs": app.abs_menu, "esc": app.esc_menu, "plot": app.plot_menu}
            return basis, f"当前选项：{menus[key].get()}（未运行的选项不代表旧结果配置）"
        value = current if len(current) <= 95 else current[:95] + "…（完整值见工程JSON）"
        return basis, f"配置值：{value}"

    def show(self, key, *, switch_group=True):
        info = explanation(key)
        self.key = key
        if switch_group:
            self.group, self.page = parameter_group(key), 0
            field = ALIASES.get(key, key)
            fields = group_parameters(self.group)
            if field in fields:
                self.page = fields.index(field)//8
            self.groups.set(list(GROUP_LABELS).index(self.group), fCommand=0)
            self.refresh_list()
        basis, values = self.context(key)
        self.title.setText(BROWSER_LABELS.get(ALIASES.get(key,key),info.title))
        unit = info.unit.replace("s⁻¹", "1/s").replace("s⁻²", "1/s²")
        self.details.setText(f"{info.role}  /  {unit}\n{values}")
        for node in self.formula_nodes:
            node.removeNode()
        self.formula_nodes.clear()
        bottom = self.details.getTightBounds(self.root)[0].z - .035
        math_key = formula_key(key)
        if math_key is not None:
            # 图片保留数学字形比例；长公式只缩小到面板宽度，不拉伸或压扁。
            for entry in self.formula_manifest["formulas"][math_key]:
                factor = min(.069 / 80, 1.85 / entry["width"])
                width, height = entry["width"] * factor, entry["height"] * factor
                card = CardMaker("formula")
                card.setFrame(0, width, 0, height)
                card.setUvRange(Point2(0, 1-entry["height"]/entry["texture_height"]),
                                Point2(entry["width"]/entry["texture_width"], 1))
                node = self.equations.attachNewNode(card.generate())
                texture = self.app.loader.loadTexture(Filename.fromOsSpecific(str(self.asset_dir / entry["file"])))
                if texture is None:
                    raise OSError(f"无法读取公式图片：{entry['file']}")
                texture.setFormat(Texture.FSrgbAlpha)
                texture.setMinfilter(Texture.FTLinearMipmapLinear)
                texture.setMagfilter(Texture.FTLinear)
                node.setTexture(texture)
                node.setTransparency(TransparencyAttrib.MAlpha)
                node.setPos(-.45, 0, bottom-height)
                self.formula_nodes.append(node)
                bottom -= height + .018
            algorithm = FORMULAS[math_key][1]
        else:
            algorithm = info.formula
        if ALIASES.get(key,key) in ("suspension_spring_rates","suspension_compression_damping","suspension_extension_damping"):
            algorithm += "\n参数按轮心行程等效；台架原始参数须按安装运动比换算。"
        self.notes.setPos(-.45, bottom-.023)
        self.notes.setText(f"{algorithm}\n{info.use}\n\n数值来源\n{basis}\n\n对应源码\n{info.source}")
        self.root.show()
