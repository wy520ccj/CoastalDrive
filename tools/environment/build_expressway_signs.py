"""中国高速标志的尺寸化网格源；单层牌面与独立支撑结构。"""

import hashlib
import json
import math

from build_expressway_kit import OUT, STEEL, beam, box
from panda3d.core import Filename, NodePath

from environment.expressway_signs import SIGN_NAMES, face, image, panel


def backing(root, points, y, thickness=.10):
    """薄板只有背面和周边，正面交给唯一纹理面。"""
    from panda3d.core import Vec4

    from scene import make_mesh

    vertices = [(x, y, z) for x,z in points] + [(x, y+thickness, z) for x,z in points]
    count = len(points)
    faces = [(count, count+i+1, count+i) for i in range(1,count-1)]
    for i in range(count):
        j = (i+1) % count
        faces.extend(((i,j,j+count), (i,j+count,i+count)))
    make_mesh("plate-back-and-edge", vertices, faces, Vec4(.40,.45,.43,1)).reparentTo(root)


def rectangle(root, name, x, y, z, w, h):
    points = [(x-w/2,z-h/2),(x+w/2,z-h/2),(x+w/2,z+h/2),(x-w/2,z+h/2)]
    backing(root, points, y)
    panel(root, name, x, y, z, w, h, image(name))


def build_models():
    assets = {}
    for name in SIGN_NAMES + ("advance-sign",):
        root = NodePath(name)
        if name in ("route-direction", "bridge-advance", "advance-sign"):
            height = 4.8 if name == "bridge-advance" else 3.4
            for x in (-1.25,1.25):
                box(root,"post",(x,0,height/2),(.12,.16,height),STEEL)
            rectangle(root,name,0,-.20,4.5 if name == "bridge-advance" else 3.3,4.7,1.9)
        else:
            box(root,"post",(0,0,1.65),(.12,.16,3.3),STEEL)
            if name == "speed-limit":
                points = [(math.cos(i*math.tau/64)*.8,3.1+math.sin(i*math.tau/64)*.8)
                          for i in range(64)]
            else:
                points = [(-.98,2.5),(.98,2.5),(0,4.2)]
            backing(root,points,-.14)
            face(root,name,points,-.14,image(name))
        assets[name] = root
    root = NodePath("gantry")
    for x in (-9.5,9.5):
        box(root,"foundation",(x,0,.30),(1,1.3,.6))
        for y in (-.4,.4):
            box(root,"upright",(x,y,4.5),(.22,.22,9),STEEL)
    for y in (-.4,.4):
        for z in (8,9):
            box(root,"cross-member",(0,y,z),(19.4,.16,.16),STEEL)
        for x in range(-9,9,2):
            beam(root,(x,y,8),(x+2,y,9))
    # 三个下箭头分别对齐-4.5、0、4.5m车道中心，单一版面表达同向直行。
    rectangle(root,"gantry",0,-.80,7.1,14.4,2.7)
    assets["gantry"] = root
    root = NodePath("kilometer")
    box(root,"post",(0,0,.65),(.09,.12,1.3),STEEL)
    backing(root,[(-.32,.875),(.32,.875),(.32,1.725),(-.32,1.725)],-.13)
    assets["kilometer"] = root
    return assets


def build():
    assets = build_models()
    hashes = {}
    for name, root in assets.items():
        root.clearModelNodes()
        root.flattenStrong()
        path = OUT/f"{name}.bam"
        root.writeBamFile(Filename.fromOsSpecific(str(path)))
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT/"sign-manifest.json").write_text(json.dumps({
        "source":"tools/environment/build_expressway_signs.py",
        "face_source":"tools/environment/make_expressway_sign_faces.py",
        "reference":"GB 5768.2-2022; Hubei expressway traffic sign guidelines 2023",
        "route":"S18 / 海滨高速: game fictional route, no real-world route survey claim",
        "font":"Source Han Sans SC Heavy, SIL OFL; game approximation of sign lettering",
        "sha256":hashes},ensure_ascii=False,indent=2),encoding="utf-8")
    kit_path = OUT/"source-manifest.json"
    if kit_path.is_file():
        kit = json.loads(kit_path.read_text(encoding="utf-8"))
        for entry in kit["assets"]:
            if entry["name"] in hashes:
                entry["sha256"] = hashes[entry["name"]]
        kit_path.write_text(json.dumps(kit,indent=2),encoding="utf-8")


if __name__ == "__main__":
    build()
