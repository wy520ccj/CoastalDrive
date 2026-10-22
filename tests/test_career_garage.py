"""车库的逐车配置与保存失败，不修改工程历史或已有车型。"""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from panda3d.core import Filename, MaterialAttrib, NodePath, PNMImage

from career_garage import (
    CAR_BY_DESIGN,
    garage_cars,
    save_paint,
    saved_paint,
    saved_vehicle,
    select_vehicle,
)
from skins import vehicle_for_design
from vehicle_designs import vehicle_design
from vehicle_visual import load_vehicle
from vehicle_workspace import WorkspaceVehicle


def test_switch_back_and_reload_preserves_complete_modified_vehicle(tmp_path):
    original = WorkspaceVehicle('reference-awd', replace(vehicle_design('reference-awd').config,
        lateral_stiffness=62000.), parameter_metadata={'basis': '已有工程参数'}, report_path='old-report.json')
    path, folder = tmp_path/'vehicle.json', tmp_path/'garage'
    original.save(path)
    candidate = saved_vehicle(original, 'coastal-hatch', folder)
    assert WorkspaceVehicle.load(path) == original
    assert candidate.config.front_drive_share == 1.
    select_vehicle(original, candidate, folder, path)
    tuned = replace(candidate, config=replace(candidate.config, lateral_stiffness=70000.))
    tuned.save(path)
    previous = saved_vehicle(tuned, original.design_id, folder)
    select_vehicle(tuned, previous, folder, path)
    assert WorkspaceVehicle.load(path) == original
    assert saved_vehicle(original, tuned.design_id, folder) == tuned
    assert garage_cars(original)[0].design_id == original.design_id


def test_failed_selection_keeps_active_vehicle_and_old_archive(tmp_path, monkeypatch):
    current = WorkspaceVehicle('game-tuned', vehicle_design('game-tuned').config)
    candidate = WorkspaceVehicle('coastal-roadster', vehicle_design('coastal-roadster').config)
    path, folder = tmp_path/'vehicle.json', tmp_path/'garage'
    current.save(path)
    before = path.read_bytes()
    save = WorkspaceVehicle.save

    def failing(self, target=None):
        if target == path:
            raise OSError('主文件暂不可写')
        return save(self, target)

    monkeypatch.setattr(WorkspaceVehicle, 'save', failing)
    with pytest.raises(OSError, match='不可写'):
        select_vehicle(current, candidate, folder, path)
    assert path.read_bytes() == before
    assert WorkspaceVehicle.load(folder/'game-tuned.json') == current


def test_each_car_paint_is_saved_separately_without_creating_fake_vehicle_slots(tmp_path):
    save_paint(tmp_path, 'coastal-hatch', 1)
    save_paint(tmp_path, 'coastal-gt', 2)
    assert saved_paint(tmp_path, 'coastal-hatch') == 1
    assert saved_paint(tmp_path, 'coastal-gt') == 2
    current = WorkspaceVehicle('game-tuned', vehicle_design('game-tuned').config)
    assert garage_cars(current, tmp_path) == garage_cars(current)


@pytest.mark.parametrize('design_id', ['coastal-hatch', 'coastal-roadster', 'coastal-gt', 'club-coupe', 'subaru-wrx-sti'])
def test_new_models_load_with_configured_body_and_four_independent_wheels(design_id):
    config = vehicle_design(design_id).config
    parent = NodePath('asset-check')
    definition = vehicle_for_design(design_id, 'sports')
    body, wheels = load_vehicle(parent, definition, config=config)
    assert len(wheels) == 4 and len({wheel.getName() for wheel in wheels}) == 4
    assert not body.find('**/paint').isEmpty()
    if design_id == 'subaru-wrx-sti':
        # 源后灯是独立贴图分区，转换材质时不能把它归到内饰图上。
        names = {state.getAttrib(MaterialAttrib).getMaterial().getName()
                 for part in body.findAllMatches('**/+GeomNode') for state in part.node().getGeomStates()}
        assert 'Rear lamps' in names
    low, high = body.getTightBounds(parent)
    if definition.id in ('coastal-hatch', 'coastal-roadster', 'coastal-gt', 'club-coupe', 'subaru-wrx-sti'):
        # 外购低矮车身按轮拱装配，后视镜允许伸出不含镜片的车身碰撞盒。
        assert high.x-low.x <= config.collision_half_width*2+.12
        assert high.y-low.y <= config.collision_half_length*2
        assert high.z-low.z <= config.collision_half_height*2
        assert body.getChild(0).getTag('authored-proportions') == 'wheel-hubs'
    else:
        assert tuple(high-low) == pytest.approx((config.collision_half_width*2,
            config.collision_half_length*2, config.collision_half_height*2), abs=1e-5)
    assert CAR_BY_DESIGN[design_id].model_id == definition.id
    parent.removeNode()


def test_elise_retains_source_vehicle_geometry_and_current_author_license():
    root = Path(__file__).resolve().parents[1]
    source = root/'art/vehicles/sources/lotus-elise'
    metadata = json.loads((source/'sketchfab-metadata.json').read_text(encoding='utf-8'))
    assert metadata['uid'] == '75e9045ac1af4cdbb69318108c81edfd'
    assert metadata['license']['slug'] == 'by' and metadata['user']['username'] == 'sa3d'
    manifest = json.loads((root/'assets/game/vehicles/elise-manifest.json').read_text(encoding='utf-8'))
    extraction = json.loads((root/'art/vehicles/elise-source.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((source/'lotus-elise-original.glb').read_bytes()).hexdigest() == extraction['source_sha256']
    assert hashlib.sha256((root/'art/vehicles/lotus_elise.glb').read_bytes()).hexdigest() == manifest['source_sha256']
    assert hashlib.sha256((root/'assets/game/vehicles/lotus_elise.bam').read_bytes()).hexdigest() == manifest['output_sha256']
    parent = NodePath('elise-source-check')
    car, wheels = load_vehicle(parent, vehicle_for_design('coastal-roadster', 'sports'),
                              config=vehicle_design('coastal-roadster').config)
    triangles = sum(primitive.decompose().getNumPrimitives() for part in car.findAllMatches('**/+GeomNode')
        for geom in part.node().getGeoms() for primitive in geom.getPrimitives())
    triangles += sum(primitive.decompose().getNumPrimitives() for wheel in wheels
        for part in wheel.findAllMatches('**/+GeomNode') for geom in part.node().getGeoms()
        for primitive in geom.getPrimitives())
    assert triangles == manifest['triangles'] == extraction['triangles']
    assert 350000 < triangles < metadata['faceCount']
    names = {part.getName() for part in car.findAllMatches('**/+GeomNode')}
    assert not any('NANA' in name or 'SOL' in name or 'Layer11_' in name for name in names)
    materials = {state.getAttrib(MaterialAttrib).getMaterial().getName()
        for part in car.findAllMatches('**/+GeomNode') for state in part.node().getGeomStates()}
    assert {'Body Paint', 'Elise cabin upholstery', 'Elise clear glass',
            'Elise red tail lamps', 'Elise headlamp lenses', 'Elise mirrors'} <= materials
    assert CAR_BY_DESIGN['coastal-roadster'].name == 'Lotus Elise'
    assert (root/'assets/game/vehicles/Lotus-Elise-License.txt').is_file()
    parent.removeNode()


@pytest.mark.parametrize('design_id', list(CAR_BY_DESIGN))
def test_catalog_thumbnail_keeps_the_whole_car_inside_its_frame(design_id):
    root = Path(__file__).resolve().parents[1]
    thumbnail = PNMImage()
    path = root/'assets/game/ui/garage-v2'/('car-'+design_id+'.png')
    assert thumbnail.read(Filename.fromOsSpecific(str(path)))
    width, height = thumbnail.getXSize(), thumbnail.getYSize()
    assert max(thumbnail.getAlpha(x, y) for x in range(width) for y in (0, height-1)) < .01
    assert max(thumbnail.getAlpha(x, y) for y in range(height) for x in (0, width-1)) < .01
