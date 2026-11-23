"""固定镜头记录海岸环境；仅移动相机，不修改物理世界。"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import AlphaTestAttrib, Filename, PNMImage, Shader, Texture, TextureAttrib, Vec3

from application import CoastalDrive
from coastal_map import offset_point, point_at


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--distances", type=float, nargs="+", default=(0, 65, 140, 225, 315))
    parser.add_argument('--sky-candidate',type=Path,help='只在本次取景替换海岸天空/照明目录，不修改默认入口')
    parser.add_argument('--meadow-candidate',type=Path,help='只在本次取景挂接离线短草样段，不改默认入口')
    parser.add_argument('--inspect-grass',action='store_true',help='仅诊断：低机位查看原草叶，不作追车成品对照')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    if args.sky_candidate is not None:
        from environment import expressway_materials

        original_assets = expressway_materials.daylight_assets

        def candidate_assets(folder=None):
            target = (args.sky_candidate.resolve() if folder==ROOT/'assets/game/environment/coastal-sunset'
                      else folder)
            return original_assets(target)

        expressway_materials.daylight_assets = candidate_assets
    app = CoastalDrive(
        smoke=True, output=args.output, render_size=(args.width, args.width * 9 // 16)
    )
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.aspect2d.hide()
    records = []
    try:
        if args.meadow_candidate is not None:
            from simplepbr._shaderutils import _load_shader_str

            from environment.foundation import coastal_shadow_shader

            meadow = app.loader.loadModel(Filename.fromOsSpecific(str(args.meadow_candidate.resolve())))
            meadow.reparentTo(app.scene.render)
            defines = {'MAX_LIGHTS':1,'ENABLE_SHADOWS':True,'USE_330':True,'USE_NORMAL_MAP':True}
            vertex = _load_shader_str('simplepbr.vert',defines.copy())
            fragment = _load_shader_str('simplepbr.frag',defines.copy())
            fragment = fragment.replace('void main() {', '''
uniform sampler2D meadow_alpha;
void main() {
if (texture(meadow_alpha,v_texcoord).r < .5) discard;''')
            vertex = vertex.replace('void main() {', '''
in vec3 meadow_root;
uniform vec3 camera_world_position;
void main() {''')
            vertex = vertex.replace('vec4 model_position = p3d_Vertex;', '''
vec4 model_position = p3d_Vertex;
float coverage = 1. - smoothstep(65.,105.,length(meadow_root.xy-camera_world_position.xy));
model_position.z = meadow_root.z + (model_position.z-meadow_root.z)*coverage;''')
            meadow.setShader(coastal_shadow_shader(Shader.make(Shader.SLGLSL,vertex,fragment)),2)
            alpha = Texture('bermuda-original-alpha')
            assert alpha.read(Filename.fromOsSpecific(str(ROOT/'art/expressway/sources/grass-bermuda-01/textures/grass_bermuda_01_alpha_1k.png')))
            alpha.setMinfilter(Texture.FTLinearMipmapLinear)
            meadow.setShaderInput('meadow_alpha',alpha)
            # 原草图集的独立遮罩同时进入深度通道，不能让整张叶片多边形投黑影。
            albedo = PNMImage()
            mask = PNMImage()
            folder = ROOT/'art/expressway/sources/grass-bermuda-01/textures'
            assert albedo.read(Filename.fromOsSpecific(str(folder/'grass_bermuda_01_diff_1k.jpg')))
            assert mask.read(Filename.fromOsSpecific(str(folder/'grass_bermuda_01_alpha_1k.png')))
            # 本源图的copyChannel结果全零；离线按归一化值合并16位遮罩。
            albedo.addAlpha()
            for y in range(albedo.getYSize()):
                for x in range(albedo.getXSize()):
                    albedo.setAlpha(x,y,mask.getGray(x,y))
            cutout = Texture('bermuda-albedo-with-original-alpha')
            assert cutout.load(albedo)
            cutout.setFormat(Texture.FSrgbAlpha)
            cutout.setMinfilter(Texture.FTLinearMipmapLinear)
            cutout.setAnisotropicDegree(8)
            for path in meadow.findAllMatches('**/+GeomNode'):
                node = path.node()
                for index in range(node.getNumGeoms()):
                    state = node.getGeomState(index)
                    textures = state.getAttrib(TextureAttrib)
                    for stage in textures.getOnStages():
                        if stage.getMode() == stage.MModulate:
                            textures = textures.addOnStage(stage,cutout)
                    node.setGeomState(index,state.setAttrib(textures))
            meadow.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MGreaterEqual,.5),2)
        app.scene.apply(app.session.current)
        for distance in args.distances:
            p, q = point_at(distance), point_at(distance + 26)
            eye = Vec3(*offset_point(p, -1.0, 3.8))
            if args.inspect_grass:
                from environment.terrain import ground_height

                x,y,_z = offset_point(p,-8)
                eye = Vec3(x,y,ground_height(x,y)+.25)
            app.camera.setPos(eye)
            if args.inspect_grass:
                x,y,_z = offset_point(point_at(distance+1),-9)
                app.camera.lookAt(Vec3(x,y,ground_height(x,y)+.08))
            else:
                app.camera.lookAt(Vec3(*offset_point(q, 0, 2)))
            app.scene.sky.setPos(eye)
            app.scene.update_lighting(eye)
            app.camLens.setFov(68)
            app.taskMgr.step()
            for _ in range(12):
                app.graphicsEngine.renderFrame()
            path = args.output / f"coast-{distance:03g}.png"
            assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
            samples = []
            for _ in range(45):
                start = time.perf_counter()
                app.graphicsEngine.renderFrame()
                app.graphicsEngine.syncFrame()
                samples.append((time.perf_counter() - start) * 1000)
            records.append(
                {
                    "distance_m": distance,
                    "eye": list(eye),
                    "screenshot": path.name,
                    "render_mean_ms": sum(samples) / len(samples),
                    "render_p95_ms": sorted(samples)[int(len(samples) * 0.95)],
                }
            )
        report = {
            "kind": "static camera rendering, not full gameplay performance gate",
            "inspect_grass": args.inspect_grass,
            "meadow_candidate": str(args.meadow_candidate) if args.meadow_candidate else None,
            "sky_candidate": str(args.sky_candidate) if args.sky_candidate else None,
            "renderer": app.win.getGsg().getDriverRenderer(),
            "views": records,
        }
        (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    main()
