from pathlib import Path

folder=Path(__file__).resolve().parent
source=(folder/'compare_ticks.py').read_text(encoding='utf-8')
source=source.replace("for p in (root / 'src').glob('*.py')", "for p in (root / 'src').rglob('*') if p.suffix in ('.py','.c','.pyd')")
exec(compile(source,str(__file__),'exec'),{'__file__':str(__file__)})
