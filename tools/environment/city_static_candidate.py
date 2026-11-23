"""城市周边静态合批实验：原追车收益未证实，不接入默认装配。"""

from panda3d.core import GeomNode


def batch_static_steps(root, lamp_name):
    """只合并本段城市静态表面，住宅/树灌的共享LOD与地块根节点保留。"""
    from environment.surface_mesh import flatten_steps

    for group in root.findAllMatches('**/mainland-city'):
        # 长街原本就是200米条带；庭院则保留四个相邻地块的小范围裁剪边界。
        batches = [group.attachNewNode('city-static-surfaces')]
        batches.extend(group.attachNewNode('city-static-surfaces-garden-'+str(number)) for number in range(4))
        for child in tuple(group.getChildren()):
            if isinstance(child.node(), GeomNode) or child.getName() == lamp_name:
                child.wrtReparentTo(batches[0])
            elif child.getName() in ('city-garden', 'city-foundation'):
                batch = batches[1+int(child.getTag('city-lot')) % 4]
                for part in tuple(child.getChildren()):
                    if isinstance(part.node(), GeomNode):
                        part.wrtReparentTo(batch)
            yield 'city-static-collect'
        for batch in batches:
            batch.clearModelNodes()
            yield from flatten_steps(batch)
        yield 'city-static-complete'
