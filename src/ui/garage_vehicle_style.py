"""落日海岸工坊统一展车材质风格：仅作用于工坊展示节点，不修改硬盘模型或任何物理参数。"""

from panda3d.core import Material


def _clone_material(material: Material) -> Material:
    return Material(material)


def apply_atelier_vehicle_style(car_root, wheels, design_id: str) -> None:
    """将全车系在落日工坊中的车窗、碳纤饰件、内饰与轮胎统一至暗调写实摄影质感。"""
    nodes = (car_root, *wheels)
    for root in nodes:
        for material in root.findAllMaterials():
            name = material.getName().lower()
            updated = _clone_material(material)
            changed = False

            # 1. 全车系车窗统一为深烟熏写实玻璃（避免浅蓝塑料座椅透出破坏真实感，增强落日环境倒影）
            if any(token in name for token in ("glass", "wind", "verre")) and "headlight" not in name and "lamp" not in name:
                updated.setBaseColor((0.015, 0.022, 0.032, 0.86))
                updated.setRoughness(0.05)
                updated.setMetallic(0.16)
                changed = True

            # 2. 内饰统一为深炭黑麂皮/织物，避免浅白内饰在暗车库中发亮
            elif any(token in name for token in ("upholstery", "interior", "int00")):
                updated.setBaseColor((0.10, 0.11, 0.13, 1.0))
                updated.setRoughness(0.78)
                updated.setMetallic(0.0)
                changed = True

            # 3. BRZ Varis 等纯白外饰套件/塑料件统一转为哑光缎面碳纤炭黑，彻底消除“白色塑料贴片感”
            elif name == "exterior lamps and trim":
                updated.setBaseColor((0.20, 0.21, 0.24, 1.0))
                updated.setRoughness(0.32)
                updated.setMetallic(0.14)
                changed = True
            elif any(token in name for token in ("plastics", "bumperr005", "cabin and exterior")):
                updated.setBaseColor((0.22, 0.23, 0.26, 1.0))
                updated.setRoughness(0.38)
                updated.setMetallic(0.10)
                changed = True

            # 4. 修正轮胎金属度过高或发灰的问题，让胎壁呈深沉橡胶质感、轮毂呈枪灰金属反光
            elif name == "source wheel and tire":
                updated.setBaseColor((0.56, 0.57, 0.60, 1.0))
                updated.setRoughness(0.42)
                updated.setMetallic(0.28)
                changed = True
            elif "tire" in name and "alloy" not in name and "rim" not in name:
                updated.setBaseColor((0.035, 0.037, 0.042, 1.0))
                updated.setRoughness(0.76)
                updated.setMetallic(0.0)
                changed = True

            # 5. 黄昏车库暖琥珀示宽灯/转向灯微光，呼应参考图点亮的琥珀前灯
            elif any(token in name for token in ("amber", "lamp-arr-orange", "fari", "930_lights")):
                if "refraction" not in name:
                    updated.setEmission((0.95, 0.44, 0.08, 1.0))
                    changed = True

            # 6. 车漆保持深润清漆金属度，最大化映射落日工坊 HDRI 顶棚暗部与右侧暖金落日高光
            elif "body paint" in name or name == "paint":
                updated.setRoughness(0.13)
                updated.setMetallic(0.68)
                changed = True

            if changed:
                root.replaceMaterial(material, updated)
