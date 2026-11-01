"""Five-page synchronized media delivery. Raw video remains untouched and hashed."""
from pathlib import Path
import hashlib,json,shutil,subprocess
import cv2
from PIL import Image,ImageDraw
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
ROOT=Path(__file__).resolve().parents[1]
SIM=ROOT/'experiments/vacuum_engineering_v2_media/sim'
OUT=ROOT/'deliverables/20261101_roadshow_v3_synced'
OUT.mkdir(parents=True,exist_ok=True)
runs=[]
for p in (SIM/'benchmark_results').glob('*/summary.json'):
    data=json.loads(p.read_text())[0]
    if data.get('status')=='complete' and data.get('video_return_code')==0:runs.append((p,data))
if not runs:raise SystemExit('No completed fresh run with finalized video')
runfile,S=sorted(runs)[-1]; RUN=runfile.parent; run_id=RUN.name
videos=sorted((SIM/'videos').glob('sensor_*.mp4'))
video=next((v for v in videos if v.with_suffix('.png').exists()),None)
if video is None:raise SystemExit('Missing final recorded frame')
# Recorder log is authoritative video/run association.
log=(RUN/'coarse_8675309_video.log').read_text()
assert video.name in log, 'Selected video is not associated with chosen run'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
model_id=sha(SIM/'vacuum_model.hh')[:12]
raw=OUT/'demo_v3_raw.mp4';shutil.copy2(video,raw)
cap=cv2.VideoCapture(str(raw)); fps=cap.get(cv2.CAP_PROP_FPS);count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));w=int(cap.get(3));h=int(cap.get(4))
assert cap.isOpened() and fps>0 and count>100
# Decode every frame: container success alone does not establish usable evidence.
decoded=0; samples=[];last=None
while True:
    ok,frame=cap.read()
    if not ok:break
    if decoded in [0,count//4,count//2,3*count//4,count-1]:samples.append((decoded,frame.copy()))
    last=frame;decoded+=1
cap.release();assert decoded==count,(decoded,count)
cv2.imwrite(str(OUT/'video_final_frame.png'),last)
main_width=int(h*1.6)
# Extract only the actual camera viewport, never the overhead/HUD composite.
hero=last[45:h,0:main_width]
cv2.imwrite(str(OUT/'robot_main_view.png'),hero)
cv2.imwrite(str(OUT/'robot_main_view_raw_viewport.png'),last[:,0:main_width])
sheet=Image.new('RGB',(1200,5*260),'#101923');draw=ImageDraw.Draw(sheet)
for i,(n,frame) in enumerate(samples):
    im=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));im.thumbnail((1200,235));sheet.paste(im,(0,i*260));draw.text((8,i*260+238),f'Frame {n} / {count} | t={n/fps:.1f}s',fill='white')
sheet.save(OUT/'video_contactsheet.jpg')
shutil.copy2(runfile,OUT/'normal_run_summary.json')
shutil.copy2(RUN/'coarse_8675309.json',OUT/'normal_run_details.json')
shutil.copy2(RUN/'coarse_8675309_telemetry.jsonl',OUT/'normal_run_telemetry.jsonl')
subprocess.run(['wsl','-d','Ubuntu-20.04','--','python3','/mnt/e/Project/sukethon/experiments/vacuum_engineering_v2_media/sim/analyze_vacuum.py'],check=True)
A=next(x for x in json.loads((SIM/'vacuum_analysis.json').read_text()) if Path(x['run_directory']).name==run_id)
shutil.copy2(SIM/'vacuum_analysis.json',OUT/'vacuum_analysis.json')
shutil.copy2(SIM/'vacuum_parameters.json',OUT/'vacuum_parameters.json')
for doc in ['ROBOT_SENSOR_SPECIFICATIONS.md','robot_sensor_specifications.json']:
    source=ROOT/'docs'/doc
    if source.exists():shutil.copy2(source,OUT/doc)
for name in ['vacuum_model.hh','generate_world.py','record_camera.py','stacking.world']:
    evidence=OUT/'model_evidence'/name;evidence.parent.mkdir(exist_ok=True);shutil.copy2(SIM/name,evidence)
faultfile=SIM/'fault_check_results.json'
if faultfile.exists():shutil.copy2(faultfile,OUT/'fault_check_results.json')
P=Presentation();P.slide_width=Inches(13.333);P.slide_height=Inches(7.5)
BG='101923';FG='EEF4F7';MUT='A5B6C3';CY='48D8D0';AM='F4B24A';PANEL='1B2A37'
def box(s,x,y,w,h,col=PANEL):
    a=s.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h));a.fill.solid();a.fill.fore_color.rgb=RGBColor.from_string(col);a.line.fill.background();return a
def text(s,value,x,y,w,h,size=20,color=FG,bold=False):
    a=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));tf=a.text_frame;tf.word_wrap=True;tf.margin_left=Inches(.02);tf.margin_right=Inches(.02)
    for i,line in enumerate(value.split('\n')):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph();p.text=line;p.font.name='Microsoft YaHei';p.font.size=Pt(size);p.font.color.rgb=RGBColor.from_string(color);p.font.bold=bold;p.space_after=Pt(7)
    return a
def slide(title,sub):
    s=P.slides.add_slide(P.slide_layouts[6]);s.background.fill.solid();s.background.fill.fore_color.rgb=RGBColor.from_string(BG)
    box(s,.55,.4,.07,.5,CY);text(s,title,.8,.32,12,.55,28,FG,True);text(s,sub,.8,1.02,12,.44,16,MUT)
    text(s,f'RUN {run_id}   |   MODEL {model_id}   |   仿真工程验证',.65,7.03,11,.25,10,MUT);text(s,f'{len(P.slides):02}',12.1,6.98,.6,.32,12,CY)
    s.notes_slide.notes_text_frame.text=f'Run: {run_id}\nVacuum model SHA256: {sha(SIM/"vacuum_model.hh")}\nVideo SHA256: {sha(raw)}\nNormal metrics source: {runfile}\nCamera framing only; no physics strategy change.'
    return s
def pic(s,path,x,y,w,h):
    iw,ih=Image.open(path).size;k=min(w/iw,h/ih);s.shapes.add_picture(str(path),Inches(x+(w-iw*k)/2),Inches(y+(h-ih*k)/2),width=Inches(iw*k),height=Inches(ih*k))
def metric(s,x,value,label,width=2.9,y=1.68):
    box(s,x,y,width,1.05);text(s,value,x+.15,y+.08,width-.3,.48,27,CY,True);text(s,label,x+.15,y+.63,width-.3,.32,16,MUT)
s=slide('蜘蛛智能工业搬运机器人','真实仿真主视角 · 全身结构可见 · 视觉闭环搬运 · 容量门控吸附')
box(s,.75,1.65,7.5,4.95);pic(s,OUT/'robot_main_view.png',.8,1.7,7.4,4.8)
text(s,'看得清，搬得稳，放得准',8.55,1.8,4.0,.9,26,CY,True)
text(s,'四腿支撑 + 锁定脚轮\nX / Y / Z / Yaw 四自由度\n单带 visor、气路与四杯末端\n\n本图直接裁取本轮视频主视窗，\n不将双画面合成图标成正视图。',8.55,2.95,4.0,2.8,20)
text(s,'固定支撑 6.10 × 5.80 × 5.42 m；运行可视高度 6.08 m（含装饰）；模型派生，非实测。',.9,6.62,11.7,.3,16,AM)
s=slide('01  环境、四轴执行器与传感器','WSL Ubuntu 20.04 / ROS Noetic / Gazebo 11 · 独立运行与独立编译')
box(s,.75,1.7,6.0,4.95);box(s,6.95,1.7,5.6,4.95)
text(s,'4 DOF / 4 joint actuator channels',1,1.95,5.6,.5,22,CY,True)
text(s,'X：横向移动桥；Y：正交滑台\nZ：垂直升降；Yaw：末端旋转\nX/Y：−2～2 m；Z：−1.5～0.7 m\nYaw：−6.3～6.3 rad\n速度上限：1 m/s；Yaw 1 rad/s\n仿真 effort 上限：3000 N / N·m\n四腿被动支撑；泵独立于四轴。',1,2.65,5.5,3.75,20)
text(s,'顶置 RGB-D（配置值）',7.2,1.95,5.0,.5,22,AM,True)
text(s,'位置 (0, 0, 4.8) m，向下观测\n960 × 960；10 Hz\n水平 / 垂直 FOV：68.75°\n深度裁剪：0.1～8 m\n稠密上限：921,600 点/帧\n有效点数受遮挡、无效深度影响。\n不是硬件实测点云密度。',7.2,2.65,5.0,3.75,20)
s=slide('02  感知与速度：逐箱闭环，把时间用在搬运','RGB-D 同步门限 <60 ms · 释放后独立复测 · 不以模型真值替代视觉验收')
for i,(title,body) in enumerate([('同步观测','10 Hz RGB-D\n中心 / 高度 / Yaw\n观测失效则停止'),('目标与槽位','A / B 箱型\n规划已知目标槽位\n视觉抓取与放后复测'),('直达转运','带载速度 0.9 m/s\n轨迹平滑与接近减速\n避免全程低速爬行'),('逐箱验收','中心 ≤10 mm\nYaw ≤5°\n超差才进入重抓')]):
    x=.75+i*3.13;box(s,x,1.75,2.95,2.55);text(s,title,x+.15,1.95,2.65,.45,22,CY,True);text(s,body,x+.15,2.65,2.65,1.5,18)
metric(s,.8,f'{S["passed"]}/8','本轮正常验收',2.85,4.68);metric(s,3.9,f'{S["elapsed_seconds"]:.2f} s','任务时间',2.85,4.68);metric(s,7,f'{S["max_center_mm"]:.2f} mm','最大中心误差',2.85,4.68);metric(s,10.1,str(S['regrasp_count'])+' 次','重抓',2.4,4.68)
text(s,'任务时间为控制器计时；视频包含启动等待与结束保留画面，二者时长不同。',.9,6.15,11.5,.5,18,AM)
s=slide('03  真空容量门控与过载保护','固定约束作为吸附执行层；压力、泄漏和负载门控为工程近似，参数待硬件标定')
box(s,.75,1.7,6,4.95);box(s,6.95,1.7,5.6,4.95)
text(s,'四杯独立状态 + 压力动态',1,1.95,5.5,.5,22,CY,True)
text(s,'泵目标负压：65 kPa\n4 杯，杯半径 34 mm\n有效面积系数 0.8；安全系数 1.3\n吸力 = Δp × 有效面积\n校核法向 m(g+a)、摩擦剪切、\n重心偏置剥离力矩；持续 40 ms\n不满足门限：拒吸 / 脱附 / 锁存。',1,2.65,5.5,3.75,20)
text(s,'真实遥测与安全边界',7.2,1.95,5,.5,22,AM,True)
text(s,f'容量峰值：{A["max_held_capacity_n"]:.0f} N\n法向峰值：{A["max_normal_demand_n"]:.0f} N\n剪切峰值：{A["max_shear_demand_n"]:.0f} N\nLeak 与 +1000 N 软件需求注入\n两项脱附中止均通过，非实体加重。\n未实现自动安全落地；实机仍需\n止回阀、机械保持与受控下放。',7.2,2.65,5,3.75,20)
s=slide('04  同一运行：视频、结果、模型可追溯','本轮正常结果与视频逐帧核验；原始录像、逐箱数据和哈希清单同目录交付')
pic(s,OUT/'video_final_frame.png',.75,1.7,8,3.0)
text(s,f'{S["passed"]}/8 通过   |   {S["elapsed_seconds"]:.2f} s\n最大中心 {S["max_center_mm"]:.2f} mm\n最大偏航 {S["max_yaw_deg"]:.2f}°；重抓 {S["regrasp_count"]} 次',9,1.95,3.7,2,20,CY,True)
a=text(s,'播放本轮完整演示 →',9,4.0,3.6,.6,22,AM,True);a.text_frame.paragraphs[0].runs[0].hyperlink.address='demo_v3_raw.mp4'
text(s,f'RUN  {run_id}\nMODEL  {model_id}\n原视频 {w}×{h} / {fps:g} fps / {count} 帧\n录像时长 {count/fps:.1f} s（原速）',.9,5.0,7.4,1.55,18)
text(s,'另附：机器人尺寸 / FOV / 点云密度\n正常结果、真空遥测、保护测试\nmanifest.json / SHA256SUMS.txt',8.4,5.05,4.2,1.5,18)
ppt=OUT/'蜘蛛智能工业搬运机器人_5页同步版.pptx';P.save(ppt)
assert len(Presentation(ppt).slides)==5
manifest={'run_id':run_id,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'normal_summary':S,'video':{'path':raw.name,'fps':fps,'frame_count':count,'decoded_frames':decoded,'width':w,'height':h,'duration_seconds':count/fps,'sha256':sha(raw),'speed':'1x original recorder wall clock','run_association':str(RUN/'coarse_8675309_video.log')},'model_sha256':sha(SIM/'vacuum_model.hh'),'world_sha256':sha(SIM/'stacking.world'),'generator_sha256':sha(SIM/'generate_world.py'),'parameters_sha256':sha(SIM/'vacuum_parameters.json'),'hero_crop_pixels':[0,45,main_width,h],'limitations':['Rigid fixed constraint attachment with vacuum capacity gating; no soft-body/full pneumatic model','Overload is +1000N software demand injection, not physical added mass','No controlled safe landing','Camera framing changed only; configuration is not hardware measured']}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'SHA256SUMS.txt').write_text('\n'.join(f'{sha(p)}  {p.name}' for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt')+'\n',encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
