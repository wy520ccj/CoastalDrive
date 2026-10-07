from pathlib import Path

folder = Path(__file__).resolve().parent
source = (folder/'profile-current.py').read_text(encoding='utf-8')
source = source.replace('/ "profile-current"','/ "profile-wheel"').replace('"head": "0afe6b1"','"head": "15457d7 + uncommitted wheel kernels"')
exec(compile(source, str(__file__), 'exec'), {'__file__':str(__file__),'__name__':'__main__'})
