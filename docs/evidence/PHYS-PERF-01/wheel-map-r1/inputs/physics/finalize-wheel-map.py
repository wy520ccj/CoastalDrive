from pathlib import Path
root=Path.cwd();p=root/'src/mechanical_kernels.c';s=p.read_text(encoding='utf-8')
begin=s.index('        double projected[9];',s.index('static PyObject *shared_map_state('))
end=s.index('        double port_free[4]',begin)
body=s[begin:end]
helper='static void shared_branch_free(const SharedMap *data,const SharedBranch *branch,\n                               const double free[9],const double active[3],double projected[9]) {\n'
helper+=body.replace('        double projected[9];\n','')+'}\n'
first=s.index('        int feasible=1;',s.index('static PyObject *shared_map_state('))
last=s.index('        if (feasible)',first)
feasible=s[first:last]
helper+='static int shared_branch_feasible(const SharedMap *data,const SharedBranch *branch,\n                                  const double end[9],const double active[3]) {\n    double terms[9];\n'
helper+=feasible+'    return feasible;\n}\n'
s=s.replace(body,'        double projected[9];\n        shared_branch_free(data,branch,free,active,projected);\n')
s=s.replace(feasible,'        int feasible=shared_branch_feasible(data,branch,end,active);\n')
s=s.replace('static int shared_port_state(',helper+'static int shared_port_state(',1)
s=s.replace('            if (!matrix_values(PyTuple_GET_ITEM(responses,w),&local->port_response[0][0],n, n)) goto failed;\n            /* 三端口矩阵的行距仍为四，按原行逐一保存。 */\n            if (n==3) for (int j=0; j<3; ++j)', '            for (int j=0; j<n; ++j)',1).replace('local->port_response[j],3)) goto failed;', 'local->port_response[j],n)) goto failed;',1)
p.write_text(s,encoding='utf-8')
p=root/'src/tire_drivetrain.py';s=p.read_text(encoding='utf-8');begin=s.index('                if shaft:',s.index('        def local_state('));end=s.index('                elif ratio:',begin)
s=s[:begin]+'                if ratio:'+s[end+len('                elif ratio:'):]
s=s.replace('                local_gear = 0.\n','',1)
s=s.replace('+ brake * local_rb[a] + (local_gear * mg[a] if shaft else 0.)) for a in range(dimensions))', '+ brake * local_rb[a] + 0.) for a in range(dimensions))',1)
p.write_text(s,encoding='utf-8')
