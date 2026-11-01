from pathlib import Path
import shutil,math,json,itertools
R=Path(__file__).resolve().parents[1];src=R/'experiments/vacuum_engineering_v2_media';dst=R/'experiments/vacuum_engineering_v4_fullfront'
if dst.exists():raise SystemExit('Already exists')
shutil.copytree(src,dst,ignore=shutil.ignore_patterns('benchmark_results','videos','__pycache__','stacking.world','last_run.json','run_*.json','vacuum_analysis.json','fault_check_results.json'))
p=dst/'sim/run_sim.py';p.write_text(p.read_text().replace('sukethon-vacuum-engineering-v2-media-build','sukethon-vacuum-engineering-v4-fullfront-build'))
# Gazebo camera optical forward is local +X: aim with yaw atan2(dy,dx), pitch atan2(-dz,hypot(dx,dy)).
eye=(17.,-6.,9.);target=(0.,0.,3.1)
yaw=math.atan2(target[1]-eye[1],target[0]-eye[0]);pitch=math.atan2(eye[2]-target[2],math.hypot(eye[0],eye[1]))
p=dst/'sim/generate_world.py';s=p.read_text();s=s.replace('<pose>8 -11 4.2 0 0.08 2.2</pose>',f'<pose>17 -6 9 0 {pitch} {yaw}</pose>');s=s.replace('<width>960</width><height>600</height>','<width>1536</width><height>960</height>');p.write_text(s)
# Project conservative bounding volume, including initial silk height and all permitted decorative X motion.
f=1536/(2*math.tan(1.05/2));cp,sp,cy,sy=math.cos(pitch),math.sin(pitch),math.cos(yaw),math.sin(yaw)
uv=[]
for x,y,z in itertools.product((-3.2,3.2),(-3.05,3.05),(0.,7.1)):
    dx,dy,dz=x-eye[0],y-eye[1],z-eye[2]
    forward=cp*cy*dx+cp*sy*dy-sp*dz;left=-sy*dx+cy*dy;up=sp*cy*dx+sp*sy*dy+cp*dz
    uv.append((768-f*left/forward,480-f*up/forward))
margins=[min(u for u,v in uv)/1536,1-max(u for u,v in uv)/1536,min(v for u,v in uv)/960,1-max(v for u,v in uv)/960]
assert min(margins)>=.08,margins
(dst/'sim/camera_framing.json').write_text(json.dumps({'eye':eye,'target':target,'pitch':pitch,'yaw':yaw,'resolution':[1536,960],'hfov_rad':1.05,'conservative_bounds':[[-3.2,-3.05,0],[3.2,3.05,7.1]],'projected_margin_fractions_left_right_top_bottom':margins,'passes_8_percent':True},indent=2))
print(margins)
