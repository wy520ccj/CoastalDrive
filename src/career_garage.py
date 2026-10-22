"""生涯车库的车型目录与逐车保存；当前工程车在换车前完整留存。"""

import json
from dataclasses import dataclass

from skins import SKINS
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


@dataclass(frozen=True)
class GarageCar:
    design_id: str
    model_id: str
    name: str
    category: str
    description: str
    unlock: int


GARAGE_CARS = (
    GarageCar('game-tuned', 'sports', 'Subaru BRZ', '双门 / 后轮驱动', 'BRZ Varis开放车模，保留熟悉的项目后驱调校。', 0),
    GarageCar('coastal-hatch', 'coastal-hatch', 'Hyundai i20', '掀背 / 前轮驱动', '开放车模；沿用项目轻型前驱调校，适合入门与绕桩。', 0),
    GarageCar('coastal-roadster', 'coastal-roadster', 'Lotus Elise', '敞篷 / 后轮驱动',
              '开放的Elise车模，沿用项目轻量后驱调校。', 3),
    GarageCar('gr86-2022-premium-6mt', 'gr86-2022', 'GR86 Premium', '跑车 / 后轮驱动', '六速手动硬件设计，体验另一种驾驶节奏。', 5),
    GarageCar('coastal-gt', 'coastal-gt', '远航 GT', 'GT / 四轮驱动', '更强动力与四驱，迎接海岸杯。', 9),
    GarageCar('club-coupe', 'club-coupe', 'BMW 1M Coupé', '双门 / 后轮驱动', '开放车模；项目通用后驱调校，非原厂参数。', 3),
    GarageCar('subaru-wrx-sti', 'subaru-wrx-sti', 'Subaru WRX STI', '掀背 / 四轮驱动', '开放的Impreza WRX STI车模，搭配项目四驱调校。', 5),
)
CAR_BY_DESIGN = {car.design_id: car for car in GARAGE_CARS}
DEFAULT_PAINT = {'coastal-hatch': 4, 'coastal-roadster': 2, 'coastal-gt': 2, 'gr86-2022-premium-6mt': 4,
                 'subaru-wrx-sti': 1}


def garage_cars(current, folder=None):
    retained = {current.design_id}
    if folder is not None:
        retained.update(path.stem for path in folder.glob('*.json'))
    extra = []
    for design_id in sorted(retained-CAR_BY_DESIGN.keys()):
        design = vehicle_design(design_id)
        extra.append(GarageCar(design.id, design.id if design.id.startswith('reference-') else 'sports',
            design.name, '已保存工程车辆', '完整保留原配置与改装，可以随时换回。', 0))
    return (*extra, *GARAGE_CARS)


def saved_vehicle(current, design_id, folder):
    """只读预览；新车使用目录配置，旧车恢复各自的完整配置。"""
    if design_id == current.design_id:
        return current
    vehicle = WorkspaceVehicle.load(folder/(design_id+'.json'))
    if vehicle is not None:
        if vehicle.design_id != design_id:
            raise ValueError('车库存档与车型不一致')
        return vehicle
    design = vehicle_design(design_id)
    return WorkspaceVehicle(design.id, design.config)


def select_vehicle(current, candidate, folder, workspace_path):
    """保存旧车后才切换主文件；主文件失败时调用方仍持有原车。"""
    current.save(folder/(current.design_id+'.json'))
    candidate.save(workspace_path)
    return candidate


def saved_paint(folder, design_id, default=None):
    try:
        value = json.loads((folder/(design_id+'.paint')).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return DEFAULT_PAINT.get(design_id, 0) if default is None else default
    if type(value) is not int or not 0 <= value < len(SKINS):
        raise ValueError('车库颜色编号无效')
    return value


def save_paint(folder, design_id, index):
    if type(index) is not int or not 0 <= index < len(SKINS):
        raise ValueError('请选择有效车身颜色')
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/(design_id+'.paint')
    temporary = path.with_suffix('.paint.tmp')
    temporary.write_text(json.dumps(index)+'\n', encoding='utf-8')
    temporary.replace(path)
