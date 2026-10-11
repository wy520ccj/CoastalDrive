from pathlib import Path
import shutil

root = Path.cwd()
out = root/'logs/performance/hard-drive-r1/road-revision/src'
shutil.copytree(root/'src',out,ignore=shutil.ignore_patterns('__pycache__'))
p = out/'streamed_road.py'
s = p.read_text(encoding='utf-8')
s = s.replace('self.segments = {}','self.segments = {}\n        self.geometry_revision = 0',1)
s = s.replace('self.meshes.pop(index, None)','self.meshes.pop(index, None)\n            self.geometry_revision += 1',1)
s = s.replace('self.segments[index] = bodies','self.segments[index] = bodies\n        self.geometry_revision += 1',1)
s = s.replace('    def shift(self, amount):','    def shift(self, amount):\n        self.geometry_revision += 1',1)
p.write_text(s,encoding='utf-8')
p = out/'simulation.py'
s = p.read_text(encoding='utf-8')
s = s.replace('self._static_support_packet = {}','self._static_support_packet = {}\n        self._road_support_revision = None\n        self._road_support_shapes = None',1)
s = s.replace('        advance_world(self._world, cars, substeps=', '''        road_shapes = None
        if self.stream is not None:
            revision = self.stream.geometry_revision
            if self._road_support_revision != revision:
                self._road_support_shapes = static_support_shapes(self._world,None,BitMask32.bit(0),
                    cache=self._static_support_cache,packet_cache=self._static_support_packet)
                self._road_support_revision = revision
            road_shapes = self._road_support_shapes
        advance_world(self._world, cars, static_shapes=road_shapes, substeps=''',1)
p.write_text(s,encoding='utf-8')
p = out/'world_step.py'
s = p.read_text(encoding='utf-8')
s = s.replace('packet_cache=None, workers=None','packet_cache=None, static_shapes=None, workers=None',1)
s = s.replace('    static_shapes = (static_support_shapes(', '    static_shapes = static_shapes or (static_support_shapes(',1)
p.write_text(s,encoding='utf-8')
