import importlib.util
from pathlib import Path
root=Path.cwd();out=root/'logs/validation/GARAGE-DESIGN-02-paint-normals'
spec=importlib.util.spec_from_file_location('prepare_brz_candidate',root/'tools/vehicles/prepare_brz.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.SOURCE=out/'candidate-authored.glb';module.OUTPUT=out/'subaru_brz.bam';module.prepare()
