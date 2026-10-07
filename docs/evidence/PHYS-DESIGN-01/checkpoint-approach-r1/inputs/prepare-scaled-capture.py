from pathlib import Path
folder=Path(__file__).resolve().parent
s=(folder/'capture.py').read_text(encoding='utf-8')
for name in ('config','rear-config','input'):s=s.replace("folder/'"+name+".json'","folder/'"+name+"-scaled.json'")
(folder/'capture-scaled.py').write_text(s,encoding='utf-8')
