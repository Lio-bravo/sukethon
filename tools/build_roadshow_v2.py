"""Build a compact five-slide engineering roadshow without touching the baseline deck."""
from pathlib import Path
import json
import shutil
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "vacuum_engineering_v1" / "sim"
OUT = ROOT / "deliverables" / "20261101_roadshow_v2_5pages"
OUT.mkdir(parents=True, exist_ok=True)
RUN = EXP / "benchmark_results" / "20261101_100944"
SUMMARY = json.loads((RUN / "summary.json").read_text(encoding="utf-8"))[0]
ANALYSIS_RUNS = json.loads((EXP / "vacuum_analysis.json").read_text(encoding="utf-8"))
ANALYSIS = ANALYSIS_RUNS[0]
VIDEO = EXP / "videos" / "sensor_20261101_100954.mp4"
PHOTO = EXP / "videos" / "sensor_20261101_100954.png"
FAULTS = EXP / "fault_check_results.json"
PARAMS = json.loads((EXP / "vacuum_parameters.json").read_text(encoding="utf-8"))
assert SUMMARY["status"] == "complete" and SUMMARY["passed"] == 8
assert VIDEO.is_file() and PHOTO.is_file()
shutil.copy2(VIDEO, OUT / "demo_v2.mp4")
shutil.copy2(PHOTO, OUT / "robot_product_front_view.png")
shutil.copy2(RUN / "summary.json", OUT / "normal_run_summary.json")
shutil.copy2(EXP / "vacuum_analysis.json", OUT / "vacuum_analysis.json")
if FAULTS.exists():
    shutil.copy2(FAULTS, OUT / "fault_check_results.json")

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BG, FG, MUTED, CYAN, AMBER, PANEL = "101923", "EEF4F7", "A5B6C3", "48D8D0", "F4B24A", "1B2A37"

def rgb(value): return RGBColor.from_string(value)
def box(slide, x, y, w, h, color=PANEL):
    shape = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid(); shape.fill.fore_color.rgb = rgb(color); shape.line.fill.background(); return shape
def txt(slide, value, x, y, w, h, size=20, color=FG, bold=False):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = shape.text_frame; frame.word_wrap = True; frame.margin_left = Inches(.04); frame.margin_right = Inches(.04)
    for i, line in enumerate(value.split("\n")):
        p = frame.paragraphs[0] if i == 0 else frame.add_paragraph(); p.text = line
        p.font.name = "Microsoft YaHei"; p.font.size = Pt(size); p.font.bold = bold; p.font.color.rgb = rgb(color); p.space_after = Pt(5)
    return shape
def slide(title, subtitle):
    s = prs.slides.add_slide(prs.slide_layouts[6]); s.background.fill.solid(); s.background.fill.fore_color.rgb = rgb(BG)
    box(s, .5, .45, .08, .48, CYAN); txt(s, title, .75, .34, 12, .55, 27, FG, True); txt(s, subtitle, .78, 1.02, 11.8, .42, 13, MUTED)
    txt(s, "蜘蛛智能工业搬运机器人  /  工程验证版", .6, 7.08, 8, .22, 9, MUTED); txt(s, f"{len(prs.slides):02}", 12.2, 7.02, .5, .3, 11, CYAN, True)
    return s
def metric(s, x, value, label, width=2.65):
    box(s, x, 1.73, width, 1.15); txt(s, value, x+.18, 1.87, width-.3, .48, 29, CYAN, True); txt(s, label, x+.18, 2.43, width-.3, .27, 12, MUTED)

s = slide("蜘蛛智能工业搬运机器人", "完整产品视角 · RGB-D 感知闭环 · 四杯真空工程近似 · 可追溯验收")
# The image is a genuine Gazebo camera frame from the new experiment, not an illustration.
s.shapes.add_picture(str(OUT / "robot_product_front_view.png"), Inches(6.0), Inches(1.55), width=Inches(6.75))
txt(s, "看得清\n搬得稳\n放得准", .86, 1.82, 4.4, 1.65, 34, CYAN, True)
txt(s, "蜘蛛式四腿支撑 + 锁定脚轮\n矩形单带 visor + 可见气路\n四轴自由度：X / Y / Z / Yaw\n四个仿真执行通道，不等于已选实机电机\n\n目标：混放箱体识别、分区码垛、逐箱验收", .9, 3.72, 4.65, 2.38, 17)
txt(s, "DOF 标签：X=横向移动梁 · Y=正交滑台 · Z=垂直升降 · Yaw=末端旋转", 6.1, 6.08, 6.4, .28, 12, AMBER, True)
txt(s, "主视角来自 20261101_100954.mp4 最终画面，包含完整腿部、脚轮、面罩与气路。", 6.1, 6.43, 6.4, .33, 11, MUTED)

s = slide("01  仿真环境与机器人自由度", "WSL Ubuntu 20.04 · ROS Noetic · Gazebo 11 · 四轴龙门运动")
box(s, .82, 1.62, 5.9, 4.95); txt(s, "运行环境与执行通道", 1.08, 1.9, 5.0, .4, 22, CYAN, True)
txt(s, "C++14 gantry plugin + Python 任务控制\n独立编译：/tmp/sukethon-vacuum-engineering-v1-build\n\n四个仿真 joint actuator channels：\nX / Y / Z / Yaw\n不代表已选实机电机品牌、功率或额定值", 1.08, 2.55, 5.1, 3.45, 18)
box(s, 6.98, 1.62, 5.5, 4.95); txt(s, "轴位置、边界与非运动部件", 7.22, 1.9, 4.9, .4, 22, AMBER, True)
txt(s, "X：横向移动桥 / carriage\nY：与 X 正交的滑台\nZ：垂直升降 slide\nYaw：tool 末端旋转 joint\n\n速度上限：1 m/s；Yaw 1 rad/s\nX/Y：−2 至 2 m；Z：−1.5 至 0.7 m\n四腿支撑、脚轮锁定且被动；泵独立；四杯不是四台电机。", 7.22, 2.55, 4.85, 3.55, 16)

s = slide("02  感知优化 + 速度控制：快而准的闭环", "先稳定观测，再用直达转运换节拍；接近放置点才减速")
for i, (title, body) in enumerate([("同步观测", "RGB-D\n<60 ms\n10 Hz"), ("目标提取", "A/B 箱型\n中心/高度/Yaw"), ("平滑转运", "已知槽位\n直达轨迹\n带载 0.9 m/s"), ("慢速验收", "接触确认\n释放复测\n超差才重抓")]):
    x = .82 + i * 3.1; box(s, x, 1.75, 2.82, 2.55); txt(s, title, x+.2, 2.0, 2.4, .42, 21, CYAN, True); txt(s, body, x+.2, 2.67, 2.4, 1.3, 18)
txt(s, "为什么快：槽位已由任务规划确定，视觉只在抓取、释放和异常时介入；为什么准：每箱释放后独立复测，观测不可用则停，不读取 model truth。", .9, 4.78, 11.4, .7, 18, AMBER, True)
metric(s, .9, "≤10 mm", "中心验收", 2.65); metric(s, 3.83, "≤5°", "偏航验收", 2.65); metric(s, 6.76, "0 次", "新模型重抓", 2.65); metric(s, 9.69, "8 / 8", "正常通过", 2.65)
txt(s, "历史三种子批测：最终 24/24，首次通过 22/24；不同版本结果分开呈现。", .95, 6.3, 11.2, .4, 15, MUTED)

s = slide("03  真空工程近似：用容量、泄漏与负载门控吸附", "保留固定约束作为执行层，新增压力动态与脱附保护，不宣称完整气动数字孪生")
box(s, .85, 1.65, 5.8, 4.65); txt(s, "已实现的可验证逻辑", 1.1, 1.93, 5.2, .42, 23, CYAN, True)
txt(s, "• 4 杯独立密封与压力状态\n• 吸力 = Δp × A_effective\n• 负载：法向 m(g+a)；剪切受摩擦限制\n• CoG 偏心形成剥离力矩，均需过门限\n• 安全系数配置 1.3；不足则禁止吸附\n• 过载脱附后故障锁存并中止任务", 1.1, 2.65, 5.0, 3.15, 17)
box(s, 6.9, 1.65, 5.6, 4.65); txt(s, "本轮真实遥测证据", 7.15, 1.93, 5.0, .42, 23, AMBER, True)
txt(s, f"• 正常：8/8；容量峰值 {ANALYSIS['max_held_capacity_n']:.0f} N\n• 法向峰值 {ANALYSIS['max_normal_demand_n']:.0f} N；剪切 {ANALYSIS['max_shear_demand_n']:.0f} N\n• 保护判定持续 {PARAMS['trip_persistence_seconds']*1000:.0f} ms\n• Leak：容量损失脱附；Overload：+1000 N 软件注入脱附\n• 两项均中止并报告；不是实体加重测试\n\n命令 vent 是正常释放；fault detach 是保护动作。未实现自动安全落地，实机需报警/减速/受控下放、机械保持与止回阀。\n\n边界：固定约束仍在；参数需硬件标定。", 7.15, 2.65, 4.95, 3.45, 15)

s = slide("04  结果、保护与演示证据", "新模型正常搬运通过；泄漏与超载注入均按预期中止，原始证据随附")
metric(s, .85, "8 / 8", "正常逐箱验收", 2.8); metric(s, 3.9, f"{SUMMARY['elapsed_seconds']:.2f} s", "新模型任务耗时", 2.8); metric(s, 6.95, f"{SUMMARY['max_center_mm']:.2f} mm", "最大中心误差", 2.8); metric(s, 10.0, "0 次", "重抓恢复", 2.4)
s.shapes.add_picture(str(OUT / "robot_product_front_view.png"), Inches(.85), Inches(3.18), width=Inches(7.35))
txt(s, "播放完整演示 →", 8.65, 3.32, 3.5, .5, 22, CYAN, True).text_frame.paragraphs[0].runs[0].hyperlink.address = "demo_v2.mp4"
txt(s, f"正常：8/8，最大偏心 {SUMMARY['max_center_mm']:.2f} mm\n峰值容量 {ANALYSIS['max_held_capacity_n']:.0f} N；需求 {ANALYSIS['max_normal_demand_n']:.0f} N\n泄漏：容量损失脱附并停机\n超载：+1000 N 软件注入，超容量脱附\n工程边界：固定约束；参数待硬件标定", 8.65, 4.0, 3.9, 2.0, 16)
txt(s, "视频：demo_v2.mp4（同目录） · 正常遥测、真空分析、fault_check_results.json 随附；不将注入载荷描述为实体试验。", .95, 6.42, 11.4, .38, 13, MUTED)

ppt = OUT / "蜘蛛智能工业搬运机器人_5页工程版.pptx"
prs.save(ppt)
check = Presentation(ppt)
assert len(check.slides) == 5
assert check.slides[0].shapes.__len__() >= 6
print(json.dumps({"pptx": str(ppt), "slides": len(check.slides), "video": str(OUT / "demo_v2.mp4"), "image": str(OUT / "robot_product_front_view.png"), "normal_run": SUMMARY, "fault_checks": json.loads(FAULTS.read_text(encoding="utf-8")) if FAULTS.exists() else []}, ensure_ascii=False, indent=2))
