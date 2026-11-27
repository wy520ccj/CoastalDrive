"""就地参数说明与分组浏览；只读取配置和已有试验输入。"""

import json
from dataclasses import asdict

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectScrolledFrame, OnscreenText
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
from suspension_bench import source_note as suspension_source_note
from ui.lab_widgets import (
    BORDER,
    LAB_ACCENT_B,
    LAB_CARD,
    LAB_SURFACE,
    LAB_TEXT,
    MUTED,
    rounded_panel,
)
from vehicle_designs import DESIGN_VEHICLES, GR86_PROFILE_PATH, vehicle_design
from vehicle_parameters import config_from_document

GROUP_LABELS = {"chassis": "底盘与转向", "tires": "轮胎", "suspension": "悬架",
                "powertrain": "动力与传动", "electronics": "制动与控制"}
BROWSER_LABELS = {"suspension_spring_rates":"轮心等效弹簧率",
                  "suspension_installation_curves":"部件安装位移曲线",
                  "suspension_damper_curves":"减振器力速曲线",
                  "suspension_spring_preloads":"轮心等效安装预载","suspension_coil_enabled":"压缩螺旋弹簧",
                  "suspension_compression_damping":"轮心等效压缩阻尼","suspension_extension_damping":"轮心等效伸张阻尼",
                  "suspension_stiffness":"质量归一化弹簧率",
                  "suspension_compression":"质量归一化压缩阻尼","suspension_relaxation":"质量归一化伸张阻尼"}
OPTION_FIELDS = {"speed": "speed_kph", "duration": "duration", "steer": "steering_deg",
                 "onset": "onset", "radius": "radius_m", "bump_height": "bump_height_m",
                 "bump_length": "bump_length_m", "bump_distance": "bump_distance_m",
                 "sweep_end": "sweep_end_kph"}


def display_value(value):
    """只格式化读数，保留工程文件和物理输入的完整精度。"""
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, (tuple, list)):
        return "("+", ".join(display_value(item) for item in value)+")"
    return str(value)


class ParameterHelp:
    def __init__(self, app):
        self.app = app
        self.group, self.page, self.key = "chassis", 0, "speed"
        self.root = DirectFrame(parent=app.root, frameColor=(.06, .08, .11, .45),
                               frameSize=(-1.78, 1.78, -1, 1), sortOrder=110, state=DGG.NORMAL)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        rounded_panel(self.root, "parameter-help-edge", (-1.484, 1.484, -.764, .744), BORDER, .028)
        rounded_panel(self.root, "parameter-help-card", (-1.48, 1.48, -.76, .74), LAB_CARD, .026)
        rounded_panel(self.root, "parameter-browser", (-1.40, -.56, -.58, .565), LAB_SURFACE, .018)
        DirectFrame(parent=self.root, frameColor=LAB_ACCENT_B,
                    frameSize=(-1.39, -1.38, .626, .684))
        app.text("参数计算说明", -1.34, .641, .048, parent=self.root, font=app.heading_font)
        app.button("关闭 · Esc", 1.19, .655, .36, self.hide, parent=self.root)
        self.groups = app.option(list(GROUP_LABELS.values()), -1.36, .490, .76,
                                 self.choose_group, parent=self.root)
        self.buttons = [app.button("", -.98, .372 - i * .092, .76,
                                   lambda index=i: self.choose_item(index), parent=self.root)
                        for i in range(8)]
        app.button("上一页", -1.21, -.438, .30, lambda: self.turn(-1), parent=self.root)
        app.button("下一页", -.75, -.438, .30, lambda: self.turn(1), parent=self.root)
        self.page_label = app.text("", -.98, -.532, .032, MUTED, parent=self.root, align=TextNode.ACenter)
        self.title = app.text("", -.47, .507, .043, parent=self.root, font=app.heading_font)
        self.content_scroll = DirectScrolledFrame(parent=self.root,
            frameSize=(-.50, 1.40, -.58, .46), canvasSize=(-.50, 1.35, -.58, .46),
            frameColor=(0, 0, 0, 0), relief=None, scrollBarWidth=.035,
            horizontalScroll_scrollSize=.05, verticalScroll_scrollSize=.08)
        self.content = self.content_scroll.getCanvas()
        self.details = OnscreenText(parent=self.content, font=app.font, text="", fg=LAB_TEXT,
                                   pos=(-.47, .408), scale=.035, align=TextNode.ALeft,
                                   wordwrap=50, mayChange=True)
        self.notes = OnscreenText(parent=self.content, font=app.font, text="", fg=LAB_TEXT,
                                 pos=(-.47, 0), scale=.033, align=TextNode.ALeft,
                                 wordwrap=54, mayChange=True)
        self.equations = self.content.attachNewNode("typeset-equations")
        self.asset_dir = resource_root() / "assets/game/ui/formulas"
        self.formula_manifest = json.loads((self.asset_dir / "manifest.json").read_text(encoding="utf-8"))
        self.formula_nodes = []
        app.text("名称悬停 / 输入框聚焦 → F1  ·  左侧可浏览完整模型参数", -1.36, -.676,
                 .031, MUTED, parent=self.root)
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

    def configuration(self):
        """公式与数值来源共同读取同一已运行记录或待运行配置。"""
        app = self.app
        if app.record is not None:
            config = app.record.metadata["vehicle_config"]
            options = app.record.metadata["summary"]["options"]
            basis = "已保存试验记录的配置"
            design_id = options["vehicle_id"]
            parameter_metadata = app.record.metadata.get("parameter_metadata")
        elif app.run_state is not None:
            config, options = asdict(app.run_state.config), asdict(app.run_state.options)
            basis = "当前试验运行配置"
            design_id = options["vehicle_id"]
            parameter_metadata = app.run_state.parameter_metadata
        else:
            design = DESIGN_VEHICLES[app.vehicle_menu.selectedIndex]
            config = asdict(design.config if app.engineered_config is None else app.engineered_config)
            options = {}
            basis = "当前选中车型的预设工程配置"
            design_id = design.id
            parameter_metadata = app.parameter_metadata
        return config,options,basis,design_id,parameter_metadata

    def context(self, key):
        app = self.app
        if key in METRIC_INFO:
            record = app.active_record()
            if record is None:
                return "尚未运行试验", "指标值：—"
            summary = record.metadata["summary"]
            opts = summary["options"]
            cfg = config_from_document(record.metadata["vehicle_config"], vehicle_design(opts["vehicle_id"]).config)
            analysis = engineering_analysis(record.samples, record.snapshots, opts, summary["reason"], config=cfg)
            item = next(item for item in (*analysis["metrics"], *analysis["ride"]["metrics"],
                                          *analysis["iso_ride"]["metrics"], *analysis["theory"]["metrics"])
                        if "metric."+item["key"] == key)
            value = f"{item['value']:.5g}" if item["value"] is not None else "— 当前工况不适用"
            return "试验记录统计结果；"+item["note"], "当前指标："+value
        config,options,basis,design_id,parameter_metadata = self.configuration()
        field = ALIASES.get(key, key)
        current = display_value(config[field]) if field in config else "记录未包含此字段"
        if field=="suspension_installation_curves" and field in config:
            current = ("未配置，采用常运动比" if config[field] is None else
                       "四角节点数 "+" / ".join(str(len(rows)) for rows in config[field])+"（完整坐标见工程 JSON）")
        if field=="suspension_damper_curves" and field in config:
            current=("未配置，采用常阻尼系数" if config[field] is None else
                     "四角节点数 "+" / ".join(str(len(rows)) for rows in config[field])+"（完整力速表见工程 JSON）")
        if "." in field and not field.startswith("manual."):
            parent, child = field.split(".")
            current = str(config[parent][child])
        if field in config:
            suspension_basis = suspension_source_note(parameter_metadata, field, config[field], config)
            fit = parameter_metadata["tire_calibration"] if parameter_metadata is not None and "tire_calibration" in parameter_metadata else None
            fitted = fit is not None and field in fit["parameters"]
            if fit is not None and field == "rear_lateral_stiffness":
                fitted = True
                fitted_value = fit["linked_rear_lateral_stiffness"]
            elif fitted:
                fitted_value = fit["parameters"][field]
            if fitted:
                if config[field] == fitted_value:
                    source = "合成基准数据拟合（算法验证）" if fit["conditions"]["source_kind"] == "synthetic" else "台架试验数据拟合"
                    conditions = fit["conditions"]
                    basis += f"\n{source}（{conditions['pressure_kpa']:g} kPa / {conditions['temperature_c']:g} °C / {conditions['speed_mps']:g} m/s）"
                    if "data_domain" in fit:
                        minimum, maximum = fit["data_domain"]["train"]["fz_N"]
                        basis += f"\n标定轮荷区间：{minimum:g}–{maximum:g} N"
                    else:
                        basis += "\n标定记录未附带轮荷区间信息"
                    basis += "\n辨识方法：纯滑移序列最小二乘拟合（独立留出集验证）"
                    if field == "road_friction":
                        basis += "\n附着系数 μ 对应标定工况下的路面—轮胎峰值附着特性"
                else:
                    basis += "\n当前值已手动修改，偏离原台架标定结果"
            elif suspension_basis is not None:
                basis += "\n"+suspension_basis
            elif design_id == "gr86-2022-premium-6mt":
                ledger = json.loads(GR86_PROFILE_PATH.read_text(encoding="utf-8"))["metadata"]["vehicle_fields"]
                if field not in ledger:
                    basis += "\n车型参数表未单独收录，沿用通用工程默认值"
                elif json.loads(json.dumps(config[field])) == ledger[field]["value"]:
                    statuses = {"measured": "实测数据", "oem": "原厂规格", "manufacturer": "原厂规格", "derived": "工程推导",
                                "engineering_prior": "工程先验", "model_mechanism": "模型机制",
                                "literature_prior": "文献先验", "calibrated_train": "试验标定"}
                    status = ledger[field]["status"]
                    basis += f"\n参数来源分类：{statuses.get(status, status)}"
                    basis += "\n依据说明："+ledger[field]["basis"]
                else:
                    basis += "\n当前值已手动修改，偏离车型原始配置"
            else:
                basis += "\n工程设计参数（基准模型配置）"
        if key in ALIASES and field not in config:
            current = "记录未包含此字段"
        if key in app.entries:
            pending = app.entries[key].get().strip() or "留空（沿用模型默认值）"
            if key in OPTION_FIELDS:
                current = str(options.get(OPTION_FIELDS[key], "记录未包含此字段")) if options else "未运行"
            return basis, f"待运行输入值：{pending}\n当前配置值：{current}"
        if key.startswith("manual."):
            return basis, f"手动输入值：{app.manual_entries[key.split('.')[1]].get()}（点击确认输入后生效）"
        if key in EDITOR_INFO:
            menus = {"vehicle": app.vehicle_menu, "maneuver": app.maneuver_menu,
                     "abs": app.abs_menu, "esc": app.esc_menu, "plot": app.plot_menu,
                     "road_class": app.road_class_menu, "feedback_source": app.feedback_menu}
            return basis, f"当前选项：{menus[key].get()}"
        value = current if len(current) <= 95 else current[:95] + "…（完整数值见工程 JSON）"
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
        bottom = self.details.getTightBounds(self.content)[0].z - .035
        math_key = formula_key(key)
        if math_key=="suspension_spring_rates":
            config = self.configuration()[0]
            if config.get("suspension_coil_enabled",False):
                math_key = "suspension_spring_preloads"
        field = ALIASES.get(key,key)
        if field in ("suspension_spring_rates","suspension_spring_preloads","suspension_coil_enabled",
                     "suspension_compression_damping","suspension_extension_damping"):
            config=self.configuration()[0]
            if config.get("suspension_installation_curves") is not None:
                math_key="installation_damping" if field.endswith("damping") else "suspension_installation_curves"
                if field=="suspension_spring_rates":self.title.setText("参考轮心材料刚度")
        if (field in ("suspension_compression_damping","suspension_extension_damping")
            and self.configuration()[0].get("suspension_damper_curves") is not None):
            math_key="suspension_damper_curves"
            self.title.setText("零速参考斜率 · 力速表生效")
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
                texture = self.app.engine.loader.loadTexture(Filename.fromOsSpecific(str(self.asset_dir / entry["file"])))
                if texture is None:
                    raise OSError(f"无法读取公式图片：{entry['file']}")
                texture.setFormat(Texture.FSrgbAlpha)
                texture.setMinfilter(Texture.FTLinearMipmapLinear)
                texture.setMagfilter(Texture.FTLinear)
                node.setTexture(texture)
                node.setTransparency(TransparencyAttrib.MAlpha)
                node.setPos(-.47, 0, bottom-height)
                self.formula_nodes.append(node)
                bottom -= height + .018
            algorithm = FORMULAS[math_key][1]
        else:
            algorithm = info.formula
        if math_key in ("suspension_spring_preloads","suspension_installation_curves"):
            algorithm += "\nq = 0 对应悬架设计参考位置；x0 为该位置处弹簧相对自由长度的安装压缩量。"
        if ALIASES.get(key,key) in ("suspension_spring_rates","suspension_compression_damping","suspension_extension_damping"):
            algorithm += "\n参数定义为 q = 0 参考位置处的轮心等效值；配置安装位移曲线时按瞬时运动比换算。"
        use=info.use
        if math_key=="suspension_installation_curves" and field=="suspension_spring_preloads":
            use="安装预载 F0 定义于 q = 0 处，不改变弹簧本体刚度 ks；变运动比机构下，总切线刚度包含受载几何项，弹簧松弛、防倾杆与限位止挡分别计算。"
        if math_key=="suspension_damper_curves" and field.endswith("damping"):
            use="当前数值表示力速曲线在零速处的切线斜率；仿真阻尼力由完整分段力速表确定。"
        self.notes.setPos(-.47, bottom-.023)
        self.notes.setText(f"{algorithm}\n{use}\n\n数值来源\n{basis}\n\n对应源码\n{info.source}")
        lower = min(-.58, self.notes.getTightBounds(self.content)[0].z-.04)
        self.content_scroll["canvasSize"] = (-.50, 1.35, lower, .46)
        self.content_scroll.verticalScroll["value"] = 0
        self.root.show()
