"""Generate the reviewable PowerPoint and preserve a hashed project snapshot."""
from pathlib import Path
import hashlib
import json
import zipfile
from datetime import datetime
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'deliverables' / '20261101_roadshow'
OUT.mkdir(parents=True, exist_ok=True)
VIDEO = ROOT / 'sim/videos/sensor_20261101_093856.mp4'
PHOTO = VIDEO.with_suffix('.png')
SUMMARY = ROOT / 'sim/benchmark_results/20261101_093846/summary.json'
result = json.loads(SUMMARY.read_text(encoding='utf-8-sig'))[0]
assert result['passed'] == 8 and VIDEO.is_file() and PHOTO.is_file()
# Preserve the source state, evidence and movie before creating presentation assets.
archive = OUT / 'sukethon_verified_20261101.zip'
exclude = {'.git', '__pycache__', '.pytest_cache', '.venv', 'deliverables'}
files = sorted(p for p in ROOT.rglob('*') if p.is_file() and not any(x in exclude or x.endswith('.egg-info') for x in p.relative_to(ROOT).parts))
manifest = []
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=4) as z:
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        manifest.append({'path': rel, 'bytes': p.stat().st_size, 'sha256': digest})
        z.write(p, rel)
    z.writestr('SNAPSHOT_MANIFEST.json', json.dumps({'created': datetime.now().isoformat(), 'run_id': '20261101_093846_coarse_8675309', 'files': manifest}, ensure_ascii=False, indent=2))
(OUT / 'snapshot_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'snapshot.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n', encoding='utf-8')

# Crop the genuine final recording into its two viewports for slide placement.
im = Image.open(PHOTO)
w, h = im.size
im.crop((0, 0, 1536, h)).save(OUT / 'robot_main.png')
im.crop((1536, 0, 2496, h)).save(OUT / 'robot_overhead.png')
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BG = '101923'; FG = 'EAF0F5'; MUTED = '9CABBC'; CYAN = '44D6CE'; PANEL = '1B2937'

def rgb(h): return RGBColor.from_string(h)
def rect(s, x,y,w,h, color):
    q=s.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
    q.fill.solid(); q.fill.fore_color.rgb=rgb(color); q.line.fill.background()
    return q

def text(s, content, x,y,w,h, size=22, color=FG, bold=False):
    q=s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf=q.text_frame; tf.word_wrap=True
    for i,line in enumerate(content.split('\n')):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.text=line; p.font.name='Microsoft YaHei'; p.font.size=Pt(size)
        p.font.bold=bold; p.font.color.rgb=rgb(color); p.space_after=Pt(12)
    return q

def slide(title, subtitle='', note=''):
    s=prs.slides.add_slide(prs.slide_layouts[6]); s.background.fill.solid(); s.background.fill.fore_color.rgb=rgb(BG)
    rect(s,.5,.45,.08,.48,CYAN)
    text(s,title,.75,.35,12,.65,30,bold=True)
    if subtitle: text(s,subtitle,.78,1.08,11.9,.6,15,MUTED)
    text(s,'蜘蛛智能工业搬运机器人  /  仿真验证版',.6,7.08,10,.25,10,MUTED)
    text(s,f'{len(prs.slides):02}',12.1,7.02,.6,.35,12,CYAN)
    s.notes_slide.notes_text_frame.text=note
    return s

def pic(s,p,x,y,w): s.shapes.add_picture(str(p), Inches(x), Inches(y), width=Inches(w))
def bullets(s, lines, x=.85,y=1.9,w=11.7,size=24): text(s,'\n'.join('• '+l for l in lines),x,y,w,4.7,size)
def metric(s,x,value,label):
    rect(s,x,1.95,3.82,1.6,PANEL); text(s,value,x+.22,2.13,3.4,.7,38,CYAN,True);text(s,label,x+.22,2.91,3.4,.4,15,MUTED)

s=slide('蜘蛛智能工业搬运机器人','SPIDER  /  从混放识别到分区码垛的视觉闭环', '开场：我们面向混放纸箱搬运，完成了一套可以复现、可以逐箱验收的工业机器人仿真系统。当前展示为Gazebo仿真原型，非已量产设备。')
text(s,'看得清 · 搬得稳 · 放得准',.85,2.0,5.1,1.5,38,CYAN,True)
text(s,'双箱型识别 / XYZ＋Yaw 龙门搬运\n四路吸盘 / 两层码垛 / 全过程遥测',.85,4.1,5.0,1.4,22)
pic(s,OUT/'robot_main.png',6.1,1.9,6.5)

s=slide('01  场景：从混放料箱到可验收的码垛','目标是完成整条作业链，而不只是单次抓取', '用任务约束描述需求，不引用未经验证的行业市场数据。两类箱体总计八箱，每类四箱，分区两层堆放。')
bullets(s,['输入：A / B 两类纸箱随机生成，位置与朝向存在扰动','过程：识别箱型与位姿，接触确认抓取，搬运并调整朝向','输出：按类别分区，每区每层 2 箱、共 2 层','验收：中心误差 ≤10 mm，偏航误差 ≤5°'])

s=slide('02  产品形态：蜘蛛式外观，工业龙门执行','四条支撑腿＋可锁定脚轮；单条矩形赛博面罩', '外观与工业运动机构结合。脚轮作业期间刚性锁定。外观管路与支撑主要是视觉模型；不要把它们描述为完整结构强度与气动系统仿真。')
pic(s,OUT/'robot_main.png',.8,1.85,7.4)
text(s,'XYZ＋Yaw 四轴\n四路吸盘与分配歧管\n连续支撑与可见气路\n完整机器人主视角',8.55,2.0,4,3.8,23)

s=slide('03  系统架构：感知、执行与验收形成闭环','Gazebo 11 / ROS Noetic / Python 任务控制 / C++ 力控制插件', '控制器使用RGB-D和关节反馈，不读取箱体model_states真值来规划。接触插件通过碰撞对象确认吸附约束。')
for i,(a,b) in enumerate([('感知','RGB-D 图像\n箱型 / 中心 / 朝向'),('任务规划','按类别分区\n层间先后与槽位预约'),('运动执行','平滑轨迹\n反馈力控制 / 接触抓取'),('释放验收','独立视觉复测\n超差触发有界恢复')]):
    x=.8+i*3.16;rect(s,x,2.1,2.95,2.5,PANEL);text(s,a,x+.2,2.32,2.55,.5,25,CYAN,True);text(s,b,x+.2,3.1,2.6,1.2,20)
text(s,'全过程时间戳 → 关节遥测 → 逐箱误差 → 可追溯结果',1,5.35,11.5,.7,25)

s=slide('04  稳与快：粗定位直达，视觉负责验收','采用已跑通方案：粗定位＋逐箱验收＋超差恢复', '这里的粗定位不意味着取消感知；取放前感知、接触确认、放后验证仍然保留。最后一轮没有触发恢复。')
bullets(s,['提前知道码垛槽位，减少放置前反复等待与微调','运动中采用平滑速度曲线，接近放置位置时减速','吸附确认后立即下发抬升目标，缩短接触后等待','每箱释放后独立视觉复测，超差时重新抓取并精定位恢复'])

s=slide('05  传感器与执行参数：配置可追溯','以下为模型配置值；实际消息时序与关节状态另存原始遥测', '目标频率不同于测得频率。主相机15Hz，俯视10Hz，接触200Hz是配置，不是性能保证。')
rect(s,.8,1.85,5.7,4.6,PANEL);text(s,'传感器',1.05,2.05,5,.5,26,CYAN,True)
text(s,'俯视 RGB-D：960×960 / 10 Hz\n水平视场：1.2 rad；深度：0.1–8 m\n主视角：960×600 / 15 Hz\n接触传感器：200 Hz\nRGB / 深度允许时间差：<60 ms',1.05,2.8,5.2,3.2,21)
rect(s,6.75,1.85,5.7,4.6,PANEL);text(s,'运动与验收',7,2.05,5,.5,26,CYAN,True)
text(s,'X / Y 行程：各 −2 至 2 m\n空载 / 带载轨迹速度：1.0 / 0.9 m/s\n轴速度模型上限：1 m/s（转轴 1 rad/s）\n放置合格：≤10 mm / ≤5°\n阈值来自当前任务配置',7,2.8,5.2,3.2,21)

s=slide('06  吸盘与控制：把模型边界说清楚','关节施加力 ≠ 吸盘吸力；接触约束 ≠ 真空气动系统', '吸盘为接触门控固定约束。目前没有吸力上限，不能利用本轮10kg载荷推导实机承载能力。详细PID和力限制见附录。')
bullets(s,['四个吸盘：杯体半径 34 mm，唇边半径 38 mm','吸附逻辑：真空使能且接触确认后建立固定约束','已记录：关节目标 / 实际位姿 / 速度 / 控制力 / 接触与吸附状态','未建模：真空压力、泄漏、吸力上限、剥离与过载脱附'],size=23)

s=slide('07  最新整轮实测：八箱通过，无重抓','运行 ID：20261101_093846_coarse_8675309；均为仿真结果', '任务耗时不含场景生成与录像尾部。视频214.7秒，搬运任务195.008秒，二者统计区间不同。偏航0是视觉估计读数，不意味着连续真值完全无误差。')
metric(s,.8,'8 / 8','逐箱最终验收通过');metric(s,4.77,f'{result["elapsed_seconds"]:.2f} s','搬运任务耗时');metric(s,8.74,f'{result["max_center_mm"]:.2f} mm','最大视觉中心误差')
text(s,'最大视觉偏航误差：0°    /    重抓恢复：0 次',1,4.1,11.7,.8,27)
text(s,'9,967 条全过程遥测；36 项软件测试通过\n单轮成功用于说明本次场景表现，不外推实机可靠率。',1,5.25,11.5,1.1,21,MUTED)

s=slide('08  随机场景复测：区分首次成功与恢复成功','历史粗定位批测 / 3 个种子 / 每轮 8 箱', '三组数据来自之前版本的仿真复测；新版墨镜外观另有单轮验证，不把不同外观版本的结果混成同一组。纯精定位曾在第3箱观测失败，因此不作为提交模式。')
bullets(s,['三轮耗时：200.35 s / 236.79 s / 226.04 s','最终验收：24 / 24；首次放置通过：22 / 24','两箱首次超差，均通过精定位重抓恢复','三轮最大中心误差：9.21 mm；最大偏航误差：1.06°','纯精定位对照曾因箱顶观测失败保护停止，仍需改进'],size=22)

s=slide('09  演示：完整机器人与俯视画面同步呈现','214.7 秒 / 10 fps / 2,147 帧 / 3086×960', '点击视频入口。视频与PPT放在同一交付文件夹中；链接是相对路径。视频包含场景生成、任务作业与最后计分。')
pic(s,PHOTO,.75,1.85,11.8)
q=text(s,'点击播放完整演示视频  →',.9,6.12,10,.5,24,CYAN,True)
q.text_frame.paragraphs[0].runs[0].hyperlink.address='demo.mp4'

s=slide('10  落地路径：从可复现仿真走向实机验证','下一阶段是验证工程能力，而非直接宣称量产就绪', '不编造融资、客户、团队信息或商业收入。路线是工程验证计划，不是已承诺交付日期。')
bullets(s,['第一步：补齐真空压力 / 承载 / 泄漏模型和结构碰撞检查','第二步：增强箱顶遮挡识别与失败恢复，扩大随机扰动测试','第三步：接入实机驱动、压力开关与安全互锁，验证急停和掉电行为','第四步：在真实纸箱与载荷条件下复测节拍、定位和吸附裕量'])

s=slide('蜘蛛智能工业搬运机器人','让每一次搬运，都有感知、有反馈、有验收。', '结束：我们交付的是可追溯的仿真原型、演示视频和原始参数数据；期望下一步围绕实机接口、真空系统和真实工况开展验证。')
text(s,'可复现的仿真闭环\n可追溯的全过程数据\n可观看的完整作业演示',1,2.2,7,3,35,CYAN,True)
text(s,'已交付：模型 / 代码 / 参数 / 遥测 / 视频\n本版定位：工业搬运机器人仿真验证原型',1,5.35,11.5,1,22)

s=slide('附录  控制参数与证据索引','用于技术问答；增益与力限制为仿真模型配置', 'PID采用Kp误差减Kd速度加Ki积分项。转轴限制单位N·m，其余轴N；Z行程为关节相对量，不是世界坐标工具高度。')
text(s,'X / Y：Kp 3500，Ki 5000，Kd 100；施加力限制 1800 N\nZ：Kp 5000，Ki 5000，Kd 160；施加力限制 2200 N\nYaw：Kp 120，Ki 1500，Kd 8；力矩限制 150 N·m\nZ 关节行程：−1.5 至 0.7 m；Yaw：−6.3 至 6.3 rad',.85,1.9,11.8,2.6,23)
text(s,'参数：sim/parameter_report.json\n本轮：sim/benchmark_results/20261101_093846/\n历史：sim/benchmark_results/20261101_075837/\n冻结版本：sukethon_verified_20261101.zip ＋ snapshot.sha256',.85,4.8,11.8,1.8,17,MUTED)

ppt=OUT/'蜘蛛智能工业搬运机器人.pptx'
prs.save(ppt)
# Place companion video next to the deck so the relative link works.
import shutil
shutil.copy2(VIDEO, OUT/'demo.mp4')
with zipfile.ZipFile(ppt) as z:
    assert z.testzip() is None
check=Presentation(ppt)
assert len(check.slides)==13
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
print(json.dumps({'pptx':str(ppt),'slides':len(check.slides),'snapshot':str(archive),'snapshot_files':len(files),'video':str(OUT/'demo.mp4')},ensure_ascii=False,indent=2))
