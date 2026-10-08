from pathlib import Path

folder=Path(__file__).resolve().parent
source=(folder/'replay-original.py').read_text(encoding='utf-8')
source=source.replace("root=Path(__file__).resolve().parents[3]", "root=Path('C:/Users/15120/.codex/worktrees/gr86-physics/CoastalDrive')")
source=source.replace("replay-original.json", "replay-latest.json").replace("diagnostic-original.json", "diagnostic-latest.json")
source=source.replace("original Python equations and arithmetic", "latest isolated kernels and analytic shaft Jacobian")
exec(compile(source,str(__file__),'exec'),{'__file__':str(__file__)})
