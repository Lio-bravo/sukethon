from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=R/'tools/build_roadshow_v3.py';s=p.read_text(encoding='utf-8').replace('vacuum_engineering_v2_media','vacuum_engineering_v4_fullfront').replace('20261101_roadshow_v3_synced','20261101_roadshow_v4_fullfront').replace('demo_v3_raw','demo_v4_raw').replace('5页同步版','5页完整正面版')
s=s.replace("hero=last[45:h,0:main_width]","hero=last[:,0:main_width]")
s=s.replace("'hero_crop_pixels':[0,45,main_width,h]","'hero_crop_pixels':[0,0,main_width,h]")
s=s.replace("'主视窗，'","'主视窗，'")
s=s.replace("'robot_main_view_raw_viewport.png'),last[:,0:main_width])","'robot_main_view_raw_viewport.png'),last[:,0:main_width])")
s=s.replace("faultfile=SIM/'fault_check_results.json'","shutil.copy2(SIM/'camera_framing.json',OUT/'camera_framing.json')\nshutil.copy2(SIM/'camera_test_fullfront.png',OUT/'camera_test_fullfront.png')\nfaultfile=ROOT/'deliverables/20261101_roadshow_v3_synced/fault_check_results.json'")
s=s.replace("'Camera framing changed only; configuration is not hardware measured'","'Camera framing changed only; configuration is not hardware measured'")
s=s.replace("(OUT/'manifest.json').write_text", "manifest['camera_framing']=json.loads((SIM/'camera_framing.json').read_text())\nmanifest['protection_provenance']={'source_delivery':'20261101_roadshow_v3_synced','source_fault_runs':['20261101_130208','20261101_130246'],'reused_same_physics':True,'model_sha256_equal':sha(SIM/'vacuum_model.hh')==sha(ROOT/'experiments/vacuum_engineering_v2_media/sim/vacuum_model.hh'),'plugin_sha256_equal':sha(SIM/'gantry_plugin.cpp')==sha(ROOT/'experiments/vacuum_engineering_v2_media/sim/gantry_plugin.cpp')}\nassert manifest['protection_provenance']['model_sha256_equal'] and manifest['protection_provenance']['plugin_sha256_equal']\n(OUT/'manifest.json').write_text",1)
s=s.replace("text(s,'另附：机器人尺寸 / FOV / 点云密度", "text(s,'另附：机器人尺寸 / FOV / 点云密度")
s=s.replace('两项脱附中止均通过，非实体加重。','同物理 v3 两项通过，非实体加重。')
(R/'tools/build_roadshow_v4.py').write_text(s,encoding='utf-8')
for source,target in [('render_roadshow_v3.ps1','render_roadshow_v4.ps1'),('verify_roadshow_v3.py','verify_roadshow_v4.py')]:
    s=(R/'tools'/source).read_text(encoding='utf-8').replace('20261101_roadshow_v3_synced','20261101_roadshow_v4_fullfront').replace('roadshow_v3.pdf','roadshow_v4.pdf')
    (R/'tools'/target).write_text(s,encoding='utf-8')
print('v4 scripts prepared')
