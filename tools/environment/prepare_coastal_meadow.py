"""将原始CC0短草叶片按设计38合成离线样段；默认游戏入口不加载。"""

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

import gltf
import numpy as np
from panda3d.core import (
    Filename,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexArrayFormat,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexReader,
    InternalName,
    NodePath,
    TextureAttrib,
    TextureStage,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))

from coastal_map import offset_point, point_at
from environment.terrain import existing_roots, ground_height


def source_leaves():
    folder = ROOT/'art/expressway/sources/grass-bermuda-01'
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    for row in manifest['files']:
        assert hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest() == row['sha256']
    model = NodePath(gltf.load_model(Filename.fromOsSpecific(str(folder/'grass_bermuda_01_1k.gltf'))))
    leaves = []
    for path in model.findAllMatches('**/+GeomNode'):
        if '_medium_' not in path.getParent().getName():
            continue
        geom = path.node().getGeom(0)
        data = geom.getVertexData()
        arrays = []
        for column, width in (('vertex', 3), ('normal', 3), (InternalName.getTexcoordName('0'), 2), ('tangent',4)):
            reader = GeomVertexReader(data, column)
            rows = []
            while not reader.isAtEnd():
                rows.append(tuple(reader.getData4f() if width == 4 else reader.getData3f() if width == 3 else reader.getData2f()))
            arrays.append(np.asarray(rows, dtype=np.float32))
        triangles = []
        for primitive in geom.getPrimitives():
            primitive = primitive.decompose()
            triangles.extend(primitive.getVertex(i) for i in range(primitive.getNumVertices()))
        state = path.node().getGeomState(0)
        textures = state.getAttrib(TextureAttrib)
        rebound = TextureAttrib.make()
        for stage in textures.getOnStages():
            target = TextureStage(stage)
            target.setTexcoordName(InternalName.getTexcoord())
            rebound = rebound.addOnStage(target,textures.getOnTexture(stage))
        leaves.append((*arrays, np.asarray(triangles, dtype=np.uint32), state.setAttrib(rebound)))
    assert len(leaves) == 6
    return leaves, manifest


def build(output, spacing):
    output.mkdir(parents=True, exist_ok=False)
    leaves, source = source_leaves()
    array = GeomVertexArrayFormat()
    for name, count in (('vertex',3), ('normal',3), ('color',4), ('texcoord',2), ('meadow_root',3), ('tangent',4)):
        numeric = Geom.NTUint8 if name == 'color' else Geom.NTFloat32
        contents = Geom.CColor if name == 'color' else Geom.CPoint if name in ('vertex','meadow_root') else Geom.CNormal if name == 'normal' else Geom.CTexcoord
        array.addColumn(name, count, numeric, contents)
    fmt = GeomVertexFormat()
    fmt.addArray(array)
    fmt = GeomVertexFormat.registerFormat(fmt)
    dtype = np.dtype([('vertex','f4',3),('normal','f4',3),('color','u1',4),('uv','f4',2),('root','f4',3),('tangent','f4',4)])
    assert dtype.itemsize == fmt.getArray(0).getStride()
    root = NodePath('coastal-meadow-candidate')
    roots = np.asarray(existing_roots())
    reports = []
    total = 0
    for start in range(0, 225, 12):
        rng = random.Random(3800+start)
        vertices, indices, count = [], [], 0
        for s in np.arange(start, min(start+12,225), spacing):
            pose = point_at(float(s+rng.uniform(0,spacing*.9)))
            for lateral in np.arange(7, 23, spacing):
                d = float(lateral+rng.uniform(0,spacing*.9))
                x,y,_z = offset_point(pose,-d)
                # 保留树根露头；不向道路/碰撞物上种植，株位只离线生成一次。
                if np.min(np.sum((roots-(x,y))**2,axis=1)) < .75**2:
                    continue
                z = ground_height(x,y)-.006
                positions,normals,uv,tangents,triangles,_state = rng.choice(leaves)
                height = rng.uniform(.065,.13)
                scale = height/float(positions[:,2].max())
                angle = rng.uniform(0,math.tau)
                c,sine = math.cos(angle),math.sin(angle)
                rotation = np.asarray(((c,-sine,0),(sine,c,0),(0,0,1)),dtype=np.float32)
                rows = np.empty(len(positions),dtype=dtype)
                rows['vertex'] = (positions*scale)@rotation.T+(x,y,z)
                rows['normal'] = normals@rotation.T
                rows['color'] = (255,255,255,255)
                rows['uv'] = uv
                rows['root'] = (x,y,z)
                rows['tangent'][:,:3] = tangents[:,:3]@rotation.T
                rows['tangent'][:,3] = tangents[:,3]
                vertices.append(rows)
                indices.append(triangles+count)
                count += len(rows)
        rows = np.concatenate(vertices)
        triangles = np.concatenate(indices)
        data = GeomVertexData('coastal-meadow',fmt,Geom.UHStatic)
        data.setNumRows(len(rows))
        data.modifyArray(0).modifyHandle().setData(rows.tobytes())
        primitive = GeomTriangles(Geom.UHStatic)
        primitive.setIndexType(Geom.NTUint32)
        primitive.modifyVertices().modifyHandle().setData(triangles.tobytes())
        geom = Geom(data)
        geom.addPrimitive(primitive)
        node = GeomNode(f'coastal-meadow-{start:03d}')
        node.addGeom(geom, leaves[0][-1])
        root.attachNewNode(node)
        total += len(vertices)
        reports.append({'start_m':start,'plants':len(vertices),'vertices':len(rows),'triangles':len(triangles)//3})
    assert root.writeBamFile(Filename.fromOsSpecific(str(output/'coastal-meadow.bam')))
    report = {'source':source,'target':'design38; explicit offline visual candidate only',
              'spacing_m':spacing,'height_m':[.065,.13],'plants':total,'cells':reports,
              'limits':'原草叶/UV/几何法线保留；纹理仍引用原CC0源文件，不作可发布打包资源。',
              'sha256':hashlib.sha256((output/'coastal-meadow.bam').read_bytes()).hexdigest()}
    (output/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('MEADOW',total,'plants',sum(row['triangles'] for row in reports),'triangles',flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--spacing',type=float,default=.18)
    args = parser.parse_args()
    if not .1 <= args.spacing <= .5:
        parser.error('样段株距须在0.1–0.5米内')
    build(args.output.resolve(),args.spacing)
