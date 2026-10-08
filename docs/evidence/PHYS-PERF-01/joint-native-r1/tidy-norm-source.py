import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[4]
folder = Path(__file__).resolve().parent
path = root / 'src/mechanical_kernels.c'
before = path.read_bytes()
audit = json.loads((folder / 'audit.json').read_text(encoding='utf-8'))
assert hashlib.sha256(before).hexdigest() == audit['source_sha_end']['src/mechanical_kernels.c']
(folder / 'tested-final-mechanical_kernels.c').write_bytes(before)
source = before.decode('utf-8')
start = source.index('/* CPython 3.14.2 vector_norm')
end = source.index('static int tire_norm(', start)
body = source[start:end]
clean = []
for line in body.splitlines(keepends=True):
    ending = '\r\n' if line.endswith('\r\n') else '\n' if line.endswith('\n') else ''
    clean.append(line.removesuffix(ending).rstrip() + ending)
after = (source[:start] + ''.join(clean) + source[end:]).encode('utf-8')
assert before.split() == after.split()
path.write_bytes(after)
(folder / 'format-source-chain.json').write_text(json.dumps({
    'tested_sha256': hashlib.sha256(before).hexdigest(),
    'committed_sha256': hashlib.sha256(after).hexdigest(),
    'only_imported_norm_body_trailing_whitespace_removed': True,
    'tokens_and_line_count_equal': before.split() == after.split() and before.count(b'\n') == after.count(b'\n'),
    'native_sha_unchanged': audit['source_sha_end']['src/mechanical_kernels.cp314-win_amd64.pyd'],
    'scope': '纯行尾空白，不重新运行测试/物理或重建已测PYD。'
}, ensure_ascii=False, indent=2), encoding='utf-8')
