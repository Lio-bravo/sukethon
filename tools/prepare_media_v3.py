"""Export committed experiment into a new isolated directory; retain user deletions."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
src='experiments/vacuum_engineering_v1/'
dst=ROOT/'experiments/vacuum_engineering_v2_media'
if dst.exists():
    raise SystemExit('Refusing to overwrite existing experiment')
files=subprocess.check_output(['git','ls-tree','-r','--name-only','HEAD',src],cwd=ROOT,text=True).splitlines()
for name in files:
    out=dst/name[len(src):]
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(subprocess.check_output(['git','show',f'HEAD:{name}'],cwd=ROOT))
print(dst)
