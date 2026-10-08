"""仅独立失败输入试验：线搜索使用与接受条件相同的逐坐标精度。"""
from pathlib import Path
root=Path.cwd();p=root/'logs/physics/PHYS-DESIGN-01-wall/replay-shared.py'
s=p.read_text(encoding='utf-8')
old='''        if not torque_bias:
            return max(abs(a - b) for a, b in zip(state, target))
'''
s=s.replace("body=textwrap.dedent(source[start:end]).replace('nonlocal ','global ')",
    "body=textwrap.dedent(source[start:end]).replace('nonlocal ','global ')\nassert "+repr(old)+" in body\nbody=body.replace("+repr(old)+",'')\nbody=body.replace('            before = residual_size(state, end)', '            before = residual_size(state, end)\\n            print(\"NEWTON\",iteration,before,delta)')\nbody=body.replace('                if residual_size(candidate, target) < before:', '                print(\"LINE\",iteration,attempt,residual_size(candidate,target), tuple(a-b for a,b in zip(candidate,target)))\\n                if residual_size(candidate, target) < before:')")
s=s.replace("'replay-original.json'","'replay-angular-merit.json'")
exec(compile(s,__file__,'exec'))
