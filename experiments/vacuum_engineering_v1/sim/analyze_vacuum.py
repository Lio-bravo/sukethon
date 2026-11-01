"""Summarize measured engineering-model pressure/capacity and mission results."""
import json
from pathlib import Path
root=Path(__file__).resolve().parent
rows=[]
for directory in sorted((root/'benchmark_results').glob('*')):
    for file in directory.glob('*_telemetry.jsonl'):
        data=[json.loads(x) for x in file.read_text().splitlines()]
        held=[x for x in data if x.get('attached') and x['vacuum_enabled']]
        if not held: continue
        item={'run_directory':str(directory),'samples':len(data),'min_held_capacity_n':min(x['suction_capacity_n'] for x in held),'max_held_capacity_n':max(x['suction_capacity_n'] for x in held),'max_normal_demand_n':max(x['normal_demand_n'] for x in held),'max_shear_demand_n':max(x['shear_demand_n'] for x in held),'max_peel_moment_nm':max(x['peel_moment_nm'] for x in held),'max_tank_vacuum_pa':max(x['tank_vacuum_pa'] for x in data),'detach_reasons':sorted(set(x['detach_reason'] for x in data))}
        if (directory/'summary.json').exists():item['summary']=json.loads((directory/'summary.json').read_text())
        rows.append(item)
(root/'vacuum_analysis.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows,indent=2))
