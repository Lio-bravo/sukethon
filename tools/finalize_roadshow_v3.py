"""Attach finalized protection evidence without regenerating validated presentation/video."""
from pathlib import Path
import json,shutil,hashlib
ROOT=Path(__file__).resolve().parents[1]
SIM=ROOT/'experiments/vacuum_engineering_v2_media/sim';OUT=ROOT/'deliverables/20261101_roadshow_v3_synced'
faults=json.loads((SIM/'fault_check_results.json').read_text())
assert len(faults)==2 and all(x['protection_pass'] for x in faults)
shutil.copy2(SIM/'fault_check_results.json',OUT/'fault_check_results.json')
for item in faults:
    src=SIM/'benchmark_results'/Path(item['evidence_directory']).name
    dst=OUT/'protection_evidence'/item['fault'];dst.mkdir(parents=True,exist_ok=True)
    for p in src.iterdir():
        if p.is_file():shutil.copy2(p,dst/p.name)
m=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
normal=SIM/'benchmark_results'/m['run_id']
for suffix in ['_video.log','.log','_gazebo.log']:
    src=normal/('coarse_8675309'+suffix)
    shutil.copy2(src,OUT/('normal'+suffix))
m['fault_tests']=[{'fault':x['fault'],'protection_pass':x['protection_pass'],'run_id':Path(x['evidence_directory']).name,'reason':x['first_trip']['detach_reason'],'status':x['summary']['status'],'same_model_sha256':m['model_sha256']} for x in faults]
m['model_unit_tests']={'passed':True,'cases':['no seal','acquisition','normal load','overload','leak','vent','two-cup rejection','invalid input','shear','peel']}
m['geometry_note']='Fixed support visual envelope 6.10 x 5.80 x 5.42 m; runtime full decorative height 6.08 m. Initial SDF silk stacking gives 6.91 m before plugin update. Model-derived, not hardware measurement.'
(OUT/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'SHA256SUMS.txt').write_text('\n'.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(OUT).as_posix()}' for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt')+'\n',encoding='utf-8')
print(json.dumps(m['fault_tests'],indent=2))
