from pathlib import Path

folder=Path(__file__).resolve().parent
source=(folder/'native-package-check.py').read_text(encoding='utf-8')
source=source.replace("'mechanical_kernels.pyd',", "'mechanical_kernels.pyd', 'wheel_contact_kernels.pyd', 'licenses/CPython-LICENSE.txt',")
exec(compile(source,str(__file__),'exec'),{'__file__':str(__file__)})
