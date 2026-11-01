"""Isolate the vacuum engineering experiment without changing the baseline."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
dst=root/'experiments/vacuum_engineering_v1'
if dst.exists(): raise SystemExit('Experiment exists; refusing to overwrite')
dst.mkdir(parents=True)
for name in ('sim','sukethon','config','tests'):
    shutil.copytree(root/name,dst/name,ignore=shutil.ignore_patterns('__pycache__','videos','benchmark_results','*.jsonl','*.log'))
for name in ('pyproject.toml',): shutil.copy2(root/name,dst/name)
p=dst/'sim/run_sim.py'
s=p.read_text();s=s.replace('/tmp/sukethon-gazebo-build','/tmp/sukethon-vacuum-engineering-v1-build');p.write_text(s)
print(dst)
