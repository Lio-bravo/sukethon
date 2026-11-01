"""Run isolated Gazebo leak and injected-demand protection scenarios, preserving evidence."""
import os
from pathlib import Path
import subprocess
import sys
import json
import time
root=Path(__file__).resolve().parent
results=[]
for mode in ('leak','overload'):
    env=os.environ.copy();env['SUKETHON_VACUUM_FAULT']=mode
    start=time.time()
    process=subprocess.run([sys.executable,str(root/'benchmark.py'),'--seeds','8675309','--no-video','--timeout','120'],env=env)
    dirs=sorted((root/'benchmark_results').glob('*'), key=lambda p:p.stat().st_mtime)
    latest=dirs[-1]
    assert latest.stat().st_mtime>=start-1
    telemetry=latest/'coarse_8675309_telemetry.jsonl'
    rows=[json.loads(line) for line in telemetry.read_text().splitlines()]
    reason='leak_capacity_loss' if mode=='leak' else 'load_capacity_exceeded'
    injection_time = 2.0
    tripped=[r for r in rows if r.get('vacuum_fault') and r.get('detach_reason')==reason
             and not r['attached'] and r.get('t', 0) >= injection_time]
    summary=json.loads((latest/'summary.json').read_text())[0]
    ok=bool(tripped) and summary['status']!='complete' and summary.get('passed',0)<8
    results.append({'fault':mode,'protection_pass':ok,'benchmark_return_code':process.returncode,'summary':summary,'evidence_directory':str(latest),'first_trip':tripped[0] if tripped else None})
    (root/'fault_check_results.json').write_text(json.dumps(results,indent=2))
    if not ok: raise SystemExit('Fault check failed: '+mode)
print('PASS: leak and injected overload cause constraint release and mission abort')
