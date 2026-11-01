from pathlib import Path
import json,hashlib,shutil
R=Path(__file__).resolve().parents[1];O=R/'deliverables/20261101_roadshow_v4_fullfront';S=R/'experiments/vacuum_engineering_v4_fullfront/sim'
m=json.loads((O/'manifest.json').read_text(encoding='utf-8'));run=S/'benchmark_results'/m['run_id']
for suffix in ['_video.log','.log','_gazebo.log']:
    shutil.copy2(run/('coarse_8675309'+suffix),O/('normal'+suffix))
m['fullfront_verification_status']={'actual_preview_before_recording':True,'raw_main_viewport_retained':[0,0,1536,960],'geometry_margin_pass':m['camera_framing']['passes_8_percent'],'video_all_frame_pixel_audit_pass':m['fullfront_audit']['all_frames_pass_8_percent'],'whole_geometry_proof':'Conservative projected bounding volume including all supports, wheels, and initial 7.1 m height; fixed camera throughout run'}
(O/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
files=sorted(p for p in O.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt')
(O/'SHA256SUMS.txt').write_text('\n'.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(O).as_posix()}' for p in files)+'\n',encoding='utf-8')
for line in (O/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
    h,n=line.split('  ',1);assert hashlib.sha256((O/n).read_bytes()).hexdigest()==h
print('Verified checksums',len(files));print(json.dumps(m['normal_summary'],indent=2));print(json.dumps(m['fullfront_verification_status'],indent=2))
