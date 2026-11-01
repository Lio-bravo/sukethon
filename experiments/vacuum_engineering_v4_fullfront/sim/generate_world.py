"""Generate deterministic scene assets; task runtime never reads these poses."""
from pathlib import Path
import math


def geometry(size):
    return '<geometry><box><size>{}</size></box></geometry>'.format(size)


def link(name, size, color, mass=1, pose='0 0 0 0 0 0', extra=''):
    dims = [float(v) for v in size.split()]
    inertia = [mass*(dims[1]**2+dims[2]**2)/12, mass*(dims[0]**2+dims[2]**2)/12, mass*(dims[0]**2+dims[1]**2)/12]
    return '''<link name="{name}"><pose>{pose}</pose><inertial><mass>{mass}</mass><inertia>
    <ixx>{ix}</ixx><iyy>{iy}</iyy><izz>{iz}</izz></inertia></inertial>
    <collision name="collision">{geom}<surface><friction><ode><mu>0.8</mu><mu2>0.8</mu2></ode></friction></surface></collision>
    <visual name="visual">{geom}<material><ambient>{color}</ambient><diffuse>{color}</diffuse></material></visual>{extra}</link>'''.format(
        name=name,pose=pose,mass=mass,ix=inertia[0],iy=inertia[1],iz=inertia[2],geom=geometry(size),color=color,extra=extra)


def visual(name, size, color, pose):
    return f'<visual name="{name}"><pose>{pose}</pose>{geometry(size)}<material><ambient>{color}</ambient><diffuse>{color}</diffuse></material></visual>'


def rounded(name, radius, color, pose):
    return f'<visual name="{name}"><pose>{pose}</pose><geometry><sphere><radius>{radius}</radius></sphere></geometry><material><ambient>{color}</ambient><diffuse>{color}</diffuse></material></visual>'


def wheel(name, pose):
    return f'<visual name="{name}"><pose>{pose}</pose><geometry><cylinder><radius>.16</radius><length>.12</length></cylinder></geometry><material><ambient>.06 .07 .08 1</ambient><diffuse>.06 .07 .08 1</diffuse></material></visual>'


def limb(name, start, end, radius, color):
    dx,dy,dz=[b-a for a,b in zip(start,end)]
    length=math.sqrt(dx*dx+dy*dy+dz*dz)
    pitch=math.acos(dz/length); yaw=math.atan2(dy,dx)
    center=[(a+b)/2 for a,b in zip(start,end)]
    return f'<visual name="{name}"><pose>{center[0]} {center[1]} {center[2]} 0 {pitch} {yaw}</pose><geometry><cylinder><radius>{radius}</radius><length>{length}</length></cylinder></geometry><material><ambient>{color}</ambient><diffuse>{color}</diffuse></material></visual>'


def generate():
    parts=['''<sdf version="1.6"><world name="stacking"><gravity>0 0 -9.81</gravity>
    <physics type="ode"><max_step_size>0.001</max_step_size><real_time_update_rate>1000</real_time_update_rate>
    <ode><solver><iters>100</iters></solver></ode></physics>
    <scene><ambient>0.65 0.65 0.65 1</ambient><background>0.16 0.19 0.24 1</background><shadows>false</shadows></scene>
    <light name="sun" type="directional"><pose>0 0 5 0 0 0</pose><diffuse>0.8 0.8 0.8 1</diffuse><direction>-0.3 0.2 -1</direction></light>
    <gui><camera name="overview"><pose>6 -7 6 0 0.5 2.28</pose></camera></gui>''']
    parts.append('<model name="table"><static>true</static>'+link('table','4.4 4.2 0.15','0.4 0.43 0.48 1',pose='0 0 0.625 0 0 0')+'</model>')
    for name,y,size,col in [('A',1.05,'1.3 0.9 0.02','0.6 0.35 0.12 1'),('B',-1.05,'0.9 0.7 0.02','0.1 0.35 0.65 1')]:
        marks=''; length,width=(.6,.4) if name=='A' else (.4,.3)
        for row in range(1):
            for column in range(2):
                cx=1+(column-.5)*(length+.02); cy=y
                for index,(sx,sy,dx,dy) in enumerate([(length,.008,0,-width/2),(length,.008,0,width/2),(.008,width,-length/2,0),(.008,width,length/2,0),(.10,.008,0,0),(.008,.10,0,0)]):
                    marks+=visual(f'mark_{row}_{column}_{index}',f'{sx} {sy} .002','0.95 0.95 0.95 1',f'{cx} {cy} .7215 0 0 0')
        parts.append('<model name="zone_'+name+'"><static>true</static>'+link('pad',size,col,pose='1 '+str(y)+' 0.71 0 0 0')+'<link name="reference_marks">'+marks+'</link></model>')
    import random, os, json
    seed=int(os.environ.get('SUKETHON_SEED',str(random.SystemRandom().randrange(2**31))))
    rng=random.Random(seed); manifest=[]
    for i in range(8):
        kind='A' if i%2==0 else 'B'
        length,width,height,mass=(.6,.4,.28,10) if kind=='A' else (.4,.3,.23,6)
        x=-1.25+(i//4)*.8+rng.uniform(-.035,.035); y=-1.1+(i%4)*.72+rng.uniform(-.025,.025); yaw=rng.uniform(-.3,.3)
        color='0.9 0.45 0.08 1' if kind=='A' else '0.08 0.5 0.9 1'
        box='<sdf version="1.6"><model name="box_{}"><pose>{} {} {} 0 0 {}</pose>{}</model></sdf>'.format(i,x,y,.7+height/2+.003,yaw,link('body',f'{length} {width} {height}',color,mass))
        manifest.append({'name':f'box_{i}','sdf':box})
    (Path(__file__).parent/'spawn_scene.json').write_text(json.dumps({'seed':seed,'boxes':manifest},indent=2))
    contact='''<gravity>false</gravity><sensor name="vacuum_contact" type="contact"><always_on>true</always_on><update_rate>200</update_rate><contact><collision>collision</collision></contact></sensor>'''
    parts.append('<model name="gantry">')
    parts.append(link('base','.1 .1 .1','0.2 0.2 0.2 1',pose='0 0 3 0 0 0'))
    parts.append('<joint name="anchor" type="fixed"><parent>world</parent><child>base</child></joint>')
    # Frame and upper carriages are above the overhead sensor's optical plane.
    # Cosmetic geometry is attached to physical links; it follows measured joint motion.
    steel='0.09 0.10 0.16 1'; yellow='0.30 0.16 0.42 1'
    frame=[]
    for x in (-2.35,2.35):
        for y in (-2.35,2.35):
            side=1 if x>0 else -1
            sy=1 if y>0 else -1
            hip=(side*1.45,sy*1.6,5.2); knee=(side*2.85,sy*2.7,3.6); ankle=(x,y,.32)
            # Continuous visual load path: rail collar -> hip bracket -> upper/lower leg -> wheel fork.
            rail_point=(x,y,5.18)
            frame.append(limb(f'spider_frame_support_{x}_{y}',rail_point,hip,.14,steel))
            frame.append(rounded(f'frame_collar_{x}_{y}','.24',yellow,f'{rail_point[0]} {rail_point[1]} {rail_point[2]} 0 0 0'))
            frame.append(visual(f'hip_bracket_{x}_{y}','.34 .30 .24',yellow,f'{hip[0]} {hip[1]} {hip[2]} 0 0 0'))
            frame.append(rounded(f'hip_collar_{x}_{y}','.18',steel,f'{hip[0]} {hip[1]} {hip[2]} 0 0 0'))
            frame.append(limb(f'spider_upper_leg_{x}_{y}',hip,knee,.12,yellow))
            frame.append(rounded(f'knee_{x}_{y}','.20',steel,f'{knee[0]} {knee[1]} {knee[2]} 0 0 0'))
            frame.append(limb(f'spider_lower_leg_{x}_{y}',knee,ankle,.085,steel))
            frame.append(visual(f'caster_fork_{x}_{y}','.30 .22 .15',yellow,f'{x} {y} .30 0 0 0'))
            frame.append(limb(f'wheel_axle_{x}_{y}',(x,y,.30),(x,y,.16),.055,steel))
            frame.append(rounded(f'wheel_collar_{x}_{y}','.12',yellow,f'{x} {y} .30 0 0 0'))
            # Wheels are rigid members of the world-anchored frame: no rolling
            # or caster joints are enabled during operation. Red clamp is engaged.
            frame.append(wheel(f'locked_wheel_{x}_{y}',f'{x} {y} .16 1.57079632679 0 0'))
            frame.append(visual(f'engaged_wheel_clamp_{x}_{y}','.24 .16 .06','0.85 .08 .06 1',f'{x} {y} .29 0 0 0'))
            frame.append(visual(f'locked_indicator_{x}_{y}','.08 .08 .04','0.1 .9 .2 1',f'{x} {y} .36 0 0 0'))
            frame.append(visual(f'brake_{x}_{y}','.22 .10 .04','0.85 0.12 0.1 1',f'{x+.19} {y} .28 0 0 0'))
    # Pneumatic equipment is cosmetic; attachment remains contact-confirmed.
    frame.append(limb('vacuum_reservoir',(-2.35,-1.3,1.25),(-2.35,-.4,1.25),.20,'0.65 0.69 0.74 1'))
    for y in (-1.3,-.4):
        frame.append(rounded(f'reservoir_end_{y}',.20,'0.65 0.69 0.74 1',f'-2.35 {y} 1.25 0 0 0'))
    frame.append(visual('vacuum_pump','.42 .32 .28',steel,'-2.35 -.85 .80 0 0 0'))
    frame.append(visual('solenoid_manifold','.25 .22 .14','0.65 0.65 0.68 1','-2.35 -.85 1.62 0 0 0'))
    frame.append(limb('pressure_gauge',(-2.35,-.9,1.77),(-2.35,-1.,1.77),.09,'0.92 0.92 0.88 1'))
    frame.append(limb('air_hose',(-2.35,-.85,1.65),(-2.35,-.85,5.18),.025,'0.08 0.08 0.10 1'))
    for index,y in enumerate((-.70,-.95)):
        frame.append(limb(f'filter_bowl_{index}',(-2.12,y,1.38),(-2.12,y,1.58),.055,'0.52 0.70 0.78 1'))
        frame.append(visual(f'filter_head_{index}', '.14 .14 .06', steel, f'-2.12 {y} 1.61 0 0 0'))
        frame.append(limb(f'regulator_knob_{index}',(-2.12,y,1.64),(-2.12,y,1.72),.035,steel))
        frame.append(limb(f'filter_feed_{index}',(-2.35,y,1.62),(-2.12,y,1.62),.014,'0.12 0.18 0.24 1'))
    # High-contrast pneumatic route: tank -> manifold -> gantry rail -> moving carriage.
    hose='0.05 0.12 0.16 1'; hose_highlight='0.90 0.62 0.10 1'
    frame.append(limb('overhead_supply',(-2.35,-.85,5.18),(-2.35,-2.35,5.18),.035,hose))
    frame.append(limb('overhead_supply_riser',(-2.35,-2.35,5.18),(-2.35,-2.35,5.35),.035,hose))
    for y in (-2.35,2.35):
        frame.append(visual(f'rail_{y}','4.9 0.2 0.22',steel,f'0 {y} 5.18 0 0 0'))
    frame.append(limb('gantry_cross_feed',(-2.35,-2.35,5.35),(2.35,-2.35,5.35),.035,hose))
    frame.append(limb('gantry_feed_drop',(0,-2.35,5.35),(0,-2.35,3.48),.045,hose_highlight))
    frame.append(rounded('gantry_feed_joint',.085,hose_highlight,'0 -2.35 3.48 0 0 0'))
    parts.append('<link name="frame">'+''.join(frame)+'</link><joint name="frame_mount" type="fixed"><parent>base</parent><child>frame</child></joint>')
    for name in ('x','y','z'):
        import re
        axis_link=link('slide_'+name,'.08 .08 .08',steel,pose='0 0 2.1 0 0 0',extra='<gravity>false</gravity>')
        axis_link=re.sub(r'<collision.*?</collision>|<visual.*?</visual>','',axis_link,flags=re.S)
        if name=='x':
            skin=visual('moving_bridge','.24 4.9 .28',yellow,'0 0 3.25 0 0 0')
            # The supply hose visibly lands on the moving bridge carriage.
            skin+=visual('carriage_manifold','.34 .42 .20',steel,'0 -2.35 3.48 0 0 0')
            skin+=rounded('carriage_hose_fitting',.09,'0.90 0.62 0.10 1','0 -2.35 3.48 0 0 0')
            skin+=limb('carriage_supply_run',(0,-2.35,3.48),(0,0,3.48),.035,'0.90 0.62 0.10 1')
            skin+=rounded('carriage_center_fitting',.075,'0.90 0.62 0.10 1','0 0 3.48 0 0 0')
            skin+=rounded('spider_head','.48',yellow,'0 0 3.50 0 0 0')
            # Single industrial cyber visor, one framed rectangular optical band.
            skin+=visual('visor_frame','.075 1.02 .30',steel,'.425 0 3.66 0 0 0')
            skin+=visual('visor_lens','.018 .91 .19','0.05 0.72 0.76 1','.469 0 3.66 0 0 0')
            skin+=visual('visor_glint','.008 .68 .018','0.70 0.94 0.90 1','.481 0 3.715 0 0 0')
        elif name=='y':
            skin=rounded('spider_abdomen','.46',yellow,'0 0 3.12 0 0 0')
            skin+=visual('spinneret','.12 .12 .18',steel,'0 0 2.70 0 0 0')
        else:
            skin=visual('spider_silk','.012 .012 4.75','0.92 0.94 0.98 1','0 0 2.435 0 0 0')
        parts.append(axis_link.replace('</link>',skin+'</link>'))
    tool=link('tool','.24 .20 .12','0.15 0.18 0.22 1',pose='0 0 2.1 0 0 0',extra=contact)
    cups=''
    for x in (-.075,.075):
        for y in (-.055,.055):
            cups+=f'<visual name="cup_{x}_{y}"><pose>{x} {y} -.052 0 0 0</pose><geometry><cylinder><radius>.034</radius><length>.016</length></cylinder></geometry><material><ambient>0.05 0.06 0.07 1</ambient><diffuse>0.05 0.06 0.07 1</diffuse></material></visual>'
            cups+=f'<visual name="cup_lip_{x}_{y}"><pose>{x} {y} -.062 0 0 0</pose><geometry><cylinder><radius>.038</radius><length>.006</length></cylinder></geometry><material><ambient>0.16 0.18 0.20 1</ambient><diffuse>0.16 0.18 0.20 1</diffuse></material></visual>'
    cups+=visual('vacuum_distribution_block','.13 .11 .045','0.68 0.70 0.73 1','0 0 -.018 0 0 0')
    for index,(x,y) in enumerate([(-.075,-.055),(-.075,.055),(.075,-.055),(.075,.055)]):
        cups+=rounded(f'push_in_fitting_{index}',.014,'0.82 0.60 0.18 1',f'{x} {y} -.028 0 0 0')
        cups+=limb(f'cup_branch_{index}',(x,y,-.025),(x,y,-.047),.008,'0.12 0.14 0.16 1')
        cups+=limb(f'branch_supply_{index}',(x*.45,y*.45,.065),(x,y,.065),.006,'0.12 0.30 0.48 1')
        cups+=limb(f'branch_elbow_{index}',(x,y,.065),(x,y,-.025),.006,'0.12 0.30 0.48 1')
    # Clear branch plumbing from the distribution block to every suction cup,
    # plus the umbilical that reaches the carriage manifold above.
    branch_color='0.90 0.62 0.10 1'; hose_color='0.05 0.12 0.16 1'
    cups+=limb('tool_supply_stem',(0,0,.10),(0,0,.27),.018,branch_color)
    cups+=limb('tool_supply_elbow',(0,0,.27),(-.13,0,.27),.018,branch_color)
    cups+=limb('tool_umbilical',(-.13,0,.27),(-.13,0,1.95),.022,hose_color)
    cups+=limb('tool_umbilical_top',(-.13,0,1.95),(0,0,2.08),.022,hose_color)
    for index,(x,y) in enumerate([(-.075,-.055),(-.075,.055),(.075,-.055),(.075,.055)]):
        cups+=limb(f'cup_branch_riser_{index}',(x,y,-.025),(x,y,-.010),.012,branch_color)
        cups+=limb(f'cup_branch_feed_{index}',(0,0,-.010),(x,y,-.010),.010,branch_color)
    parts.append(tool.replace('</link>',cups+'</link>'))
    for name,parent,child,axis,typ,lo,hi in [('x','base','slide_x','1 0 0','prismatic',-2,2),('y','slide_x','slide_y','0 1 0','prismatic',-2,2),('z','slide_y','slide_z','0 0 1','prismatic',-1.5,.7),('yaw','slide_z','tool','0 0 1','revolute',-6.3,6.3)]:
        parts.append(f'<joint name="axis_{name}" type="{typ}"><parent>{parent}</parent><child>{child}</child><axis><xyz>{axis}</xyz><limit><lower>{lo}</lower><upper>{hi}</upper><effort>3000</effort><velocity>1</velocity></limit><dynamics><damping>5</damping></dynamics></axis></joint>')
    parts.append('<plugin name="gantry_control" filename="libsukethon_gantry.so"/></model>')
    parts.append('''<model name="camera"><static>true</static><pose>0 0 4.8 0 1.57079632679 0</pose><link name="camera_link">
    <sensor name="overhead" type="depth"><always_on>true</always_on><update_rate>10</update_rate><camera><horizontal_fov>1.2</horizontal_fov><image><width>960</width><height>960</height><format>R8G8B8</format></image><clip><near>0.1</near><far>8</far></clip></camera>
    <plugin name="rgbd" filename="libgazebo_ros_openni_kinect.so"><cameraName>overhead</cameraName><imageTopicName>rgb/image_raw</imageTopicName><depthImageTopicName>depth/image_raw</depthImageTopicName><cameraInfoTopicName>rgb/camera_info</cameraInfoTopicName><frameName>overhead_optical</frameName><pointCloudCutoff>0.1</pointCloudCutoff><pointCloudCutoffMax>8</pointCloudCutoffMax></plugin>
    </sensor></link></model>
    <model name="main_view_camera"><static>true</static><pose>17 -6 9 0 0.3162864788267089 2.8023000391357487</pose><link name="main_view_link">
    <sensor name="main_view" type="camera"><always_on>true</always_on><update_rate>15</update_rate><camera><horizontal_fov>1.05</horizontal_fov><image><width>1536</width><height>960</height><format>R8G8B8</format></image><clip><near>0.1</near><far>30</far></clip></camera>
    <plugin name="main_view_ros" filename="libgazebo_ros_camera.so"><cameraName>main_view</cameraName><imageTopicName>image_raw</imageTopicName><cameraInfoTopicName>camera_info</cameraInfoTopicName><frameName>main_view_optical</frameName></plugin>
    </sensor></link></model></world></sdf>''')
    output=Path(__file__).parent/'stacking.world'
    output.write_text('\n'.join(parts),encoding='utf-8')
    print(output)

if __name__=='__main__':
    generate()
