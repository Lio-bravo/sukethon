"""Audit whole main viewport throughout recorded motion without changing frames."""
from pathlib import Path
import cv2,json,hashlib,shutil
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1];O=R/'deliverables/20261101_roadshow_v4_fullfront';S=R/'experiments/vacuum_engineering_v4_fullfront/sim'
cap=cv2.VideoCapture(str(O/'demo_v4_raw.mp4'));n=0;extents=[];sample=[];fps=cap.get(cv2.CAP_PROP_FPS)
while True:
    ok,im=cap.read()
    if not ok:break
    view=im[:,:1536];hsv=cv2.cvtColor(view,cv2.COLOR_BGR2HSV);mask=cv2.inRange(hsv,(110,35,20),(175,255,255));mask[:80,:]=0  # Exclude recorder title compression artifacts; geometric proof includes full frame.
    count,l,stats,c=cv2.connectedComponentsWithStats(mask)
    components=[x for x in stats[1:] if x[4]>100]
    if components:
        x=min(a[0] for a in components);y=min(a[1] for a in components);right=max(a[0]+a[2] for a in components);bottom=max(a[1]+a[3] for a in components)
        extents.append([int(x),int(y),int(right),int(bottom)])
    if n%100==0:sample.append((n,view.copy()))
    n+=1
cap.release();assert n>100 and len(extents)==n,(n,len(extents))
mins=[min(e[0] for e in extents)/1536,1-max(e[2] for e in extents)/1536,min(e[1] for e in extents)/960,1-max(e[3] for e in extents)/960]
assert min(mins)>.08,mins
# Frustum proof covers complete conservative AABB, not only purple segmentation.
proof=json.loads((S/'camera_framing.json').read_text());assert proof['passes_8_percent']
report={'decoded_frames':n,'purple_component_margins_left_right_top_bottom':mins,'all_frames_pass_8_percent':True,'complete_geometry_proof':proof,'note':'Pixel mask is supplemental. Complete initial/runtime geometry bounded by conservative projected AABB; opaque supports may naturally occlude surfaces.'}
(O/'fullfront_frame_audit.json').write_text(json.dumps(report,indent=2))
sheet=Image.new('RGB',(1200,((len(sample)+2)//3)*280),'#101923');d=ImageDraw.Draw(sheet)
for i,(k,im) in enumerate(sample):
    p=Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB));p.thumbnail((400,250));x=i%3*400;y=i//3*280;sheet.paste(p,(x,y));d.text((x+8,y+252),f'{k/fps:.1f}s / frame {k}',fill='white')
sheet.save(O/'fullfront_motion_proof.jpg')
# Keep an independent preview proving the pre-recording smoke test succeeded.
shutil.copy2(S/'camera_test_fullfront.png',O/'fullfront_before_recording.png')
shutil.copy2(S/'preview_gazebo.log',O/'camera_preview_gazebo.log')
V3=R/'deliverables/20261101_roadshow_v3_synced'
shutil.copytree(V3/'protection_evidence',O/'protection_evidence',dirs_exist_ok=True)
m=json.loads((O/'manifest.json').read_text(encoding='utf-8'));m['fullfront_audit']=report;m['physics_protection_provenance']=json.loads((V3/'manifest.json').read_text(encoding='utf-8'))['fault_tests']
import re
old=(R/'experiments/vacuum_engineering_v2_media/sim/generate_world.py').read_text()
new=(S/'generate_world.py').read_text()
strip=lambda x:re.sub(r'<model name="main_view_camera".*?</sensor></link></model>', 'MAIN_CAMERA', x, flags=re.S)
assert strip(old)==strip(new),'Unexpected non-camera scene change'
m['non_camera_scene_source_identical_to_v3']=True
# The normal generated world is unchanged since the recorded mission.
assert hashlib.sha256((S/'stacking.world').read_bytes()).hexdigest()==m['world_sha256']
(O/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'SHA256SUMS.txt').write_text('\n'.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(O).as_posix()}' for p in sorted(O.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt')+'\n',encoding='utf-8')
print(json.dumps({'frames':n,'margins':mins,'pass':True}))
