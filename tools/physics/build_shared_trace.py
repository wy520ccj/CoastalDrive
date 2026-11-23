"""在独立原生源码副本中记录失败求根的末十轮，生产模块不变。"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build(output):
    output.mkdir(parents=True, exist_ok=False)
    source = output/'src'
    source.mkdir()
    hashes = {}
    for path in [*(ROOT/'src').glob('*.h'), ROOT/'src/mechanical_kernels.c', ROOT/'src/wheel_contact_kernels.c']:
        shutil.copy2(path, source/path.name)
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    path = source/'joint_iteration_helpers.h'
    code = path.read_text(encoding='utf-8')
    old = '    if (data->bias) {state[9]=ports[0]; state[10]=ports[1];}'
    if code.count(old) != 1:
        raise ValueError('共同求根入口已变化')
    code = code.replace(old, '    char trace[60000]; int trace_used=0;\n'+old)
    old = '        if (angular_converged && ports_converged) {'
    trace = '''        if (iteration>=20) {
            trace_used+=snprintf(trace+trace_used,sizeof(trace)-trace_used,
                "iteration=%d branch=%d port=%d bias=%d error=%.17g\\n",iteration,branch_index,port_index,data->bias,error);
            for(int a=0;a<variables;++a) trace_used+=snprintf(trace+trace_used,sizeof(trace)-trace_used,
                "a=%d state=%.17g end=%.17g residual=%.17g tol=%.17g\\n",a,state[a],end[a],residual[a],a<9?angular_tolerance(state[a],end[a]):PORT_TOLERANCE);
        }
'''
    if code.count(old) != 1:
        raise ValueError('共同求根停止条件已变化')
    code = code.replace(old, trace+old)
    old = next(line for line in code.splitlines() if 'if (shared_residual_size(data,candidate,target)<before' in line)
    trace = '''                if(iteration>=20) {
                    double normalized=0.; int worst=-1;
                    for(int a=0;a<variables;++a) {
                        double value=fabs(candidate[a]-target[a])/(a<9?angular_tolerance(candidate[a],target[a]):PORT_TOLERANCE);
                        if(value>normalized){normalized=value;worst=a;}
                    }
                    trace_used+=snprintf(trace+trace_used,sizeof(trace)-trace_used,
                        "candidate attempt=%d raw=%.17g normalized=%.17g worst=%d before=%.17g\\n",attempt,shared_residual_size(data,candidate,target),normalized,worst,before);
                }
'''
    if code.count(old) != 1:
        raise ValueError('共同求根线搜索已变化')
    code = code.replace(old, trace+old)
    old = '    PyGILState_STATE error_gil=PyGILState_Ensure();'
    code = code.replace(old, '    fprintf(stderr,"SHARED_FAILURE_TRACE\\n%s",trace); fflush(stderr);\n'+old, 1)
    path.write_text(code, encoding='utf-8')
    setup = '''import os
from setuptools import Extension, setup
args = ["/fp:strict", "/utf-8"] if os.name=="nt" else ["-fno-fast-math", "-ffp-contract=off"]
setup(name="shared-failure-trace", ext_modules=[Extension(name,["src/"+name+".c"],extra_compile_args=args) for name in ("mechanical_kernels","wheel_contact_kernels")])
'''
    (output/'setup_trace.py').write_text(setup, encoding='utf-8')
    (output/'source-sha256.json').write_text(json.dumps(hashes, indent=2)+'\n', encoding='utf-8')
    with (output/'build.log').open('w', encoding='utf-8') as stream:
        result = subprocess.run([sys.executable, 'setup_trace.py', 'build_ext', '--build-lib', 'modules',
                                 '--build-temp', 'objects'], cwd=output, stdout=stream, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f'独立模块编译失败：{output / "build.log"}')
    print(output/'modules')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.output.resolve())
