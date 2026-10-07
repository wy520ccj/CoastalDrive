"""同一子步内复用联合雅可比的割线更新；只作未接入生产的速度试验。"""
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=Path(__file__).resolve().parent
source=(folder/'probe-coupled-correction.py').read_text(encoding='utf-8')
body=(folder/'coupled-correction-body.py').read_text(encoding='utf-8')
body=body.replace('    def correct_coupled(', '    coupled_matrix = coupled_previous = None\n\n    def correct_coupled(',1)
body=body.replace('nonlocal suspension, normal_forces, frames','nonlocal suspension, normal_forces, frames, coupled_matrix, coupled_previous',1)
start=body.index('        columns = []');end=body.index('        delta = _solve(',start)
block=body[start:end]
block=block.replace('        columns = []','            columns = []',1)
block='\n'.join('    '+line if index>0 else line for index,line in enumerate(block.split('\n')))
replacement='''        if coupled_matrix is None:
'''+block+'''            coupled_matrix = tuple(tuple(columns[j][a] for j in range(14)) for a in range(14))
        else:
            old_errors = residual(coupled_previous)
            change = tuple(values[i] - coupled_previous[i] for i in range(14))
            squared = sum(value * value for value in change)
            if squared:
                predicted = tuple(sum(row[j] * change[j] for j in range(14)) for row in coupled_matrix)
                defect = tuple(errors[i] - old_errors[i] - predicted[i] for i in range(14))
                coupled_matrix = tuple(tuple(row[j] + defect[i] * change[j] / squared for j in range(14))
                                       for i, row in enumerate(coupled_matrix))
'''
body=body[:start]+replacement+body[end:]
body=body.replace('                coupled_matrix = tuple(tuple(columns[j][a] for j in range(14)) for a in range(14))',
                  '            coupled_matrix = tuple(tuple(columns[j][a] for j in range(14)) for a in range(14))',1)
body=body.replace('_solve(tuple(tuple(columns[j][a] for j in range(14)) for a in range(14)),','_solve(coupled_matrix,',1)
body=body.replace('            if max(abs(value) for value in after) < before:\n                return','            if max(abs(value) for value in after) < before:\n                coupled_previous = candidate\n                return',1)
body=body.replace('        suspension, normal_forces, frames = original_system', '        coupled_previous = values\n        suspension, normal_forces, frames = original_system',1)
(folder/'broyden-correction-body.py').write_text(body,encoding='utf-8')
source=source.replace('coupled-correction-body.py','broyden-correction-body.py').replace('coupled-correction-snapshots.json','broyden-correction-snapshots.json')
exec(compile(source,str(folder/'probe-coupled-correction.py'),'exec'),{'__file__':str(folder/'probe-coupled-correction.py'),'__name__':'__main__'})
