"""RGB-D driven Gazebo gantry demo. No model/link-state subscriptions."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import time
import json
import math
import threading
import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CameraInfo, JointState
from std_msgs.msg import Float64MultiArray, Bool, String
from sukethon.task import Pallet, Pose, Zone
from sukethon.supervisor import Detection, Supervisor
from sukethon.servo import corrected_tool, placement_error, trajectory_duration, smooth_target, clearance_height


class GazeboAdapter:
    def __init__(self,placement_mode='precise'):
        self.placement_mode=placement_mode; self.recovering=False; self.grasp_offset=None
        self.lock=threading.Lock(); self.rgb=None; self.depth=None; self.info=None
        self.positions=None; self.velocities={}; self.attached=False; self.selected=None; self.expected=None
        self.attachment_received=0.; self.frame_after=-1.; self.corrections=[]
        self.bridge=CvBridge(); self.targets={}; self.next_id=0; self.placed=set()
        self.status_pub=rospy.Publisher('/demo/status',String,queue_size=1,latch=True)
        self.run_started=None; self.cycle_started=None; self.records=[]; self.phase='READY'
        self.obstacles=[]; self.transit_z=1.65; self.routes=[]
        self.pick_timings=[]; self.attached_at=None

        self.cmd=rospy.Publisher('/gantry/target',Float64MultiArray,queue_size=1)
        self.vac=rospy.Publisher('/gantry/vacuum',Bool,queue_size=1,latch=True)
        rospy.Subscriber('/overhead/rgb/image_raw',Image,self.image)
        rospy.Subscriber('/overhead/depth/image_raw',Image,self.depth_image)
        rospy.Subscriber('/overhead/rgb/camera_info',CameraInfo,self.camera_info)
        rospy.Subscriber('/gantry/joint_states',JointState,self.joints)
        rospy.Subscriber('/gantry/attached',Bool,self.attachment)

    def report(self,phase):
        self.phase=phase
        self.status_pub.publish(String(data=json.dumps({'phase':phase,'started':self.run_started,
                                                       'records':self.records,'clock':'wall_monotonic'})))

    def image(self,msg):
        with self.lock: self.rgb=self.bridge.imgmsg_to_cv2(msg,'bgr8'); self.rgb_stamp=msg.header.stamp.to_sec()
    def depth_image(self,msg):
        with self.lock: self.depth=self.bridge.imgmsg_to_cv2(msg,'32FC1'); self.depth_stamp=msg.header.stamp.to_sec()
    def camera_info(self,msg): self.info=msg
    def joints(self,msg):
        self.positions=dict(zip(msg.name,msg.position)); self.velocities=dict(zip(msg.name,msg.velocity))
        self.joint_received=time.monotonic()
        if self.pick_timings and self.pick_timings[-1].get('up_motion_delay_ms') is None:
            record=self.pick_timings[-1]
            if self.velocities.get('axis_z',0)>.005:
                record['up_motion_delay_ms']=(self.joint_received-record['attached_at'])*1000
    def attachment(self,msg):
        self.attached=msg.data; self.attachment_received=time.monotonic()

    def actual(self):
        if not self.positions or time.monotonic()-self.joint_received>1:
            raise RuntimeError('Fresh joint feedback unavailable')
        return [self.positions[n] for n in ['axis_x','axis_y','axis_z','axis_yaw']]

    def loaded(self):
        if time.monotonic()-self.attachment_received>1:
            raise RuntimeError('Vacuum attachment feedback stale')
        return self.attached

    def move(self,x,y,z,yaw,tolerance=.003,speed=None,loaded=None,settle=True,velocity_limit=.015):
        target=[x,y,z,yaw]; start=self.actual(); started=time.monotonic()
        carrying=self.attached if loaded is None else loaded
        duration=trajectory_duration(start,target,speed or (.9 if carrying else 1.0),1.2 if carrying else 1.5)
        stable=None
        while time.monotonic()-started<duration+25 and not rospy.is_shutdown():
            elapsed=time.monotonic()-started
            if carrying and not self.loaded(): raise RuntimeError('Load attachment lost during motion')
            self.cmd.publish(Float64MultiArray(data=smooth_target(start,target,elapsed/duration)))
            actual=self.actual()
            stopped=max(abs(v) for v in self.velocities.values())<velocity_limit if self.velocities else False
            if not settle and elapsed>=duration and max(abs(a-b) for a,b in zip(actual,target))<.008:
                self.frame_after=rospy.Time.now().to_sec(); return
            if elapsed>=duration and max(abs(a-b) for a,b in zip(actual,target))<tolerance and stopped:
                stable=stable or time.monotonic()
                if time.monotonic()-stable>.15:
                    self.frame_after=rospy.Time.now().to_sec(); return
            else: stable=None
            time.sleep(.02)
        raise RuntimeError('Joint target timeout: target='+str(target)+' actual='+str(self.positions)+' velocity='+str(self.velocities))

    def detect(self,roi=None):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            with self.lock:
                ready=self.rgb is not None and self.depth is not None and self.info is not None
                if ready:
                    age=rospy.Time.now().to_sec()-min(self.rgb_stamp,self.depth_stamp)
                    ready=0<=age<.5 and abs(self.rgb_stamp-self.depth_stamp)<.06 and min(self.rgb_stamp,self.depth_stamp)>self.frame_after
                if ready:
                    rgb=self.rgb.copy(); depth=self.depth.copy(); info=self.info
                    self.frame_after=min(self.rgb_stamp,self.depth_stamp)
                    break
            time.sleep(.05)
        else: raise RuntimeError('Fresh synchronized RGB-D unavailable')
        hsv=cv2.cvtColor(rgb,cv2.COLOR_BGR2HSV)
        output=[]
        for kind,lo,hi in [('A',(5,120,80),(30,255,255)),('B',(90,110,60),(125,255,255))]:
            mask=cv2.inRange(hsv,np.array(lo),np.array(hi))
            mask[~np.isfinite(depth) | (depth>3.95) | (depth<2.8)]=0
            if roi is not None:
                uu,vv=np.meshgrid(np.arange(depth.shape[1]),np.arange(depth.shape[0]))
                wx=-(vv-info.K[5])*depth/info.K[4]
                wy=-(uu-info.K[2])*depth/info.K[0]
                half_x,half_y=(.3,.2) if kind=='A' else (.2,.15)
                mask[(np.abs(wx-roi.x)>half_x+.008)|(np.abs(wy-roi.y)>half_y+.008)]=0
            contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            if roi is not None and contours:
                # The carriage/tool can split a visible box top into multiple components.
                # Merge only within this box's local ROI, never across the source scene.
                contours=[cv2.convexHull(np.concatenate(contours))]
            for contour in contours:
                if cv2.contourArea(contour)<100: continue
                rect=cv2.minAreaRect(contour); (u,v),(w,h),angle=rect
                patch=np.zeros(mask.shape,np.uint8); cv2.drawContours(patch,[contour],-1,255,-1)
                valid=depth[(patch>0)&(mask>0)&np.isfinite(depth)&(depth>0)]
                if valid.size<30: continue
                d=float(np.percentile(valid,10))
                top_mask=((patch>0)&(mask>0)&np.isfinite(depth)&(np.abs(depth-d)<.004)).astype(np.uint8)*255
                top_contours,_=cv2.findContours(top_mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                if not top_contours: continue
                top_contour=cv2.convexHull(np.concatenate(top_contours)) if roi is not None else max(top_contours,key=cv2.contourArea)
                if cv2.contourArea(top_contour)<100: continue
                (u,v),(w,h),angle=cv2.minAreaRect(top_contour)
                # Fixed calibrated downward camera: optical x -> world -y, optical y -> world -x.
                x=-(v-info.K[5])*d/info.K[4]; y=-(u-info.K[2])*d/info.K[0]; top=4.8-d
                # Dimensions are measured, color is only a segmentation aid for this initial scene.
                long_side=max(w,h)*d/info.K[0]; short_side=min(w,h)*d/info.K[0]
                expected=(.6,.4,.28) if kind=='A' else (.4,.3,.23)
                if abs(long_side-expected[0])>.08 or abs(short_side-expected[1])>.08:
                    if roi is not None: print('ROI rejected dimensions',kind,long_side,short_side,'depth',d,flush=True)
                    continue
                pixel_angle=math.radians(angle+(90 if h>w else 0))
                yaw=math.atan2(-math.cos(pixel_angle),-math.sin(pixel_angle))
                # Rectangle symmetry permits 180-degree equivalent orientations.
                yaw=(yaw+math.pi/2)%math.pi-math.pi/2
                output.append((kind,Pose(x,y,top-expected[2]/2,yaw)))
        return output

    def observe(self):
        observed=[]
        scene=self.detect()
        self.obstacles=[(pose.x,pose.y,pose.z+(.14 if kind=='A' else .115),
                         math.hypot(.3,.2) if kind=='A' else math.hypot(.2,.15)) for kind,pose in scene]
        for kind,pose in scene:
            if pose.x>0: continue  # Known source-table workspace, not object ground truth.
            matches=[(math.hypot(pose.x-p.x,pose.y-p.y),identity) for identity,(k,p) in self.targets.items() if k==kind and identity not in self.placed]
            if matches and min(matches)[0]<.12: identity=min(matches)[1]
            else: identity='observed-{}'.format(self.next_id); self.next_id+=1
            self.targets[identity]=(kind,pose)
            observed.append(Detection(identity,kind,pose,.99))
        return observed

    def grasp(self,target):
        if self.cycle_started is None: self.cycle_started=time.monotonic()
        self.report('PICK '+target.identity)
        refreshed=[d for d in self.observe() if d.identity==target.identity and d.kind==target.kind]
        if len(refreshed)!=1: raise RuntimeError('Pre-grasp visual reacquisition failed')
        return self.grasp_observed(refreshed[0])

    def grasp_observed(self,target):
        self.selected=target
        height=.28 if target.kind=='A' else .23
        top=target.pose.z+height/2
        current=Pose(*self.actual())
        empty_z=clearance_height(current,target.pose,self.obstacles,.17,.06)
        self.move(current.x,current.y,max(current.z,empty_z),current.yaw)
        self.move(target.pose.x,target.pose.y,max(empty_z,top+.10),target.pose.yaw)
        self.move(target.pose.x,target.pose.y,top+.10,target.pose.yaw,speed=.18)
        self.vac.publish(Bool(data=True))
        deadline=time.monotonic()+6
        contact_start=self.actual()
        while time.monotonic()<deadline:
            # Allow depth noise and small support compression on upper-layer regrasp.
            z=max(top+.025,contact_start[2]-.025*(6-(deadline-time.monotonic())))
            self.cmd.publish(Float64MultiArray(data=[target.pose.x,target.pose.y,z,target.pose.yaw]))
            if self.loaded():
                self.attached_at=time.monotonic()
                current=self.actual()
                self.grasp_offset=current[2]-target.pose.z
                # Cancel descent and issue upward motion in this same control iteration.
                self.cmd.publish(Float64MultiArray(data=[current[0],current[1],current[2]+.004,current[3]]))
                self.pick_timings.append({'box':target.identity,'attached_at':self.attached_at,
                                          'up_command_delay_ms':(time.monotonic()-self.attached_at)*1000})
                return True
            time.sleep(.01)
        self.vac.publish(Bool(data=False))
        self.move(target.pose.x,target.pose.y,2.1,target.pose.yaw)
        return False

    def lift(self):
        # Only lift clear of the source here. Transfer knows the destination layer.
        height=.28 if self.selected.kind=='A' else .23
        tool=self.actual()
        self.move(tool[0],tool[1],self.selected.pose.z+height/2+.06+.035,tool[3],loaded=True,settle=False)
        return self.loaded()
    def transfer(self,pose):
        self.report('TRANSFER '+self.selected.identity)
        self.expected=pose
        height=.28 if self.selected.kind=='A' else .23
        radius=math.hypot(.3,.2) if self.selected.kind=='A' else math.hypot(.2,.15)
        tool=Pose(*self.actual())
        # Include destination support, even if an occluded lower box is not visible.
        obstacles=self.obstacles+[(pose.x,pose.y,pose.z-height/2,radius)]
        self.transit_z=max(tool.z,clearance_height(tool,pose,obstacles,radius,height+.06))
        self.routes.append({'box':self.selected.identity,'tool_height':self.transit_z,'bottom_height':self.transit_z-height-.06})
        self.move(tool.x,tool.y,self.transit_z,tool.yaw,loaded=True,settle=False)
        self.move(pose.x,pose.y,self.transit_z,pose.yaw,loaded=True)
        return self.loaded()
    def measured(self,reference):
        samples=[]
        for _ in range(3):
            candidates=[p for kind,p in self.detect(roi=reference) if kind==self.selected.kind
                        and math.hypot(p.x-reference.x,p.y-reference.y)<.07]
            if len(candidates)!=1: raise RuntimeError('Unique box top observation unavailable')
            samples.append(candidates[0])
        if any(placement_error(samples[0],p)[0]>.006 or placement_error(samples[0],p)[1]>math.radians(2) for p in samples[1:]):
            raise RuntimeError('Box observation unstable')
        yaw=samples[0].yaw+float(np.median([(p.yaw-samples[0].yaw+math.pi/2)%math.pi-math.pi/2 for p in samples]))
        return Pose(*[float(np.median([getattr(p,field) for p in samples])) for field in ('x','y','z')],yaw)

    def place(self,pose):
        if self.placement_mode=='coarse' and not self.recovering:
            self.report('DIRECT PLACE '+self.selected.identity)
            height=.28 if self.selected.kind=='A' else .23
            offset=self.grasp_offset
            if offset is None or abs(offset-(height/2+.06))>.02:
                raise RuntimeError('Contact-derived grasp offset inconsistent')
            tool=Pose(*self.actual())
            self.move(pose.x,pose.y,pose.z+offset+.025,pose.yaw,speed=.3,loaded=True,settle=False)
            self.move(pose.x,pose.y,pose.z+offset,pose.yaw,speed=.08,loaded=True,
                      tolerance=.003,velocity_limit=.015)
            self.corrections.append({'box':self.selected.identity,'stage':'direct',
                                     'contact_offset_m':offset})
            return self.release_and_retreat(pose)
        return self.place_precise(pose)

    def place_precise(self,pose):
        self.report('ALIGN / RELEASE '+self.selected.identity)
        height=.28 if self.selected.kind=='A' else .23
        # Measure the held box itself: grasp eccentricity is not assumed to be zero.
        for attempt in range(3):
            tool=Pose(*self.actual())
            reference=Pose(pose.x,pose.y,tool.z-.06-height/2,pose.yaw)
            observed=self.measured(reference)
            desired=Pose(pose.x,pose.y,observed.z,pose.yaw)
            error,angle=placement_error(desired,observed)
            self.corrections.append({'stage':'held','attempt':attempt,'error_m':error,'yaw_rad':angle})
            print('Held visual correction',self.corrections[-1],flush=True)
            if error<.003 and angle<math.radians(1): break
            adjusted=corrected_tool(tool,desired,observed)
            self.move(adjusted.x,adjusted.y,tool.z,adjusted.yaw,speed=.12,loaded=True)
        else: raise RuntimeError('Held visual servo did not converge')
        tool=Pose(*self.actual())
        observed=self.measured(Pose(pose.x,pose.y,tool.z-.06-height/2,pose.yaw))
        tool=Pose(*self.actual())
        tool_to_center=tool.z-observed.z
        if abs(tool_to_center-(height/2+.06))>.015:
            raise RuntimeError('Measured tool-to-box offset inconsistent: '+str(tool_to_center))
        self.move(tool.x,tool.y,pose.z+tool_to_center+.035,tool.yaw,speed=.22,loaded=True)
        self.move(tool.x,tool.y,pose.z+tool_to_center+.008,tool.yaw,speed=.045,loaded=True,
                  tolerance=.0015,velocity_limit=.004)
        # At support height, remove residual lateral tracking error before release.
        for attempt in range(3):
            tool=Pose(*self.actual())
            supported=self.measured(Pose(pose.x,pose.y,tool.z-tool_to_center,pose.yaw))
            desired=Pose(pose.x,pose.y,supported.z,pose.yaw)
            error,angle=placement_error(desired,supported)
            self.corrections.append({'stage':'supported','attempt':attempt,'error_m':error,'yaw_rad':angle})
            print('Pre-release visual correction',self.corrections[-1],flush=True)
            if error<.005 and angle<math.radians(1): break
            adjusted=corrected_tool(tool,desired,supported)
            self.move(adjusted.x,adjusted.y,tool.z,adjusted.yaw,speed=.06,loaded=True)
        else: raise RuntimeError('Pre-release alignment did not converge')
        # Correct lateral pose while suspended, then seat vertically without sliding
        # on the lower box. The gripper offset comes from fresh RGB-D evidence.
        tool=Pose(*self.actual())
        supported=self.measured(Pose(pose.x,pose.y,tool.z-tool_to_center,pose.yaw))
        tool_to_center=tool.z-supported.z
        self.move(tool.x,tool.y,pose.z+tool_to_center,tool.yaw,speed=.035,loaded=True,
                  tolerance=.0015,velocity_limit=.004)
        return self.release_and_retreat(pose)

    def release_and_retreat(self,pose):
        height=.28 if self.selected.kind=='A' else .23
        tool=Pose(*self.actual())
        self.vac.publish(Bool(data=False))
        deadline=time.monotonic()+2
        while self.loaded() and time.monotonic()<deadline: time.sleep(.02)
        if self.loaded(): raise RuntimeError('Vacuum did not release')
        radius=math.hypot(.3,.2) if self.selected.kind=='A' else math.hypot(.2,.15)
        self.obstacles.append((pose.x,pose.y,pose.z+height/2,radius))
        retreat=Pose(0,pose.y,pose.z,tool.yaw)
        retreat_z=clearance_height(Pose(*self.actual()),retreat,self.obstacles,.17,.06)
        self.move(tool.x,tool.y,retreat_z,tool.yaw,loaded=False)
        self.move(retreat.x,retreat.y,retreat_z,tool.yaw,loaded=False)
        self.placed.add(self.selected.identity)
        return True

    def inspect_placement(self,identity):
        # Every release is measured independently. Only verified observations reach the supervisor.
        self.report('VERIFY '+identity)
        for attempt in range(3):
            measured=self.measured(self.expected)
            error,angle=placement_error(self.expected,measured)
            self.corrections.append({'box':identity,'stage':'released','attempt':attempt,'error_m':error,'yaw_rad':angle,
                                     'measured':vars(measured),'target':vars(self.expected)})
            print('Released visual verification',self.corrections[-1],flush=True)
            if (error<=.01 and angle<=math.radians(5)) or attempt==2:
                now=time.monotonic()
                self.records.append({'box':identity,'kind':self.selected.kind,'center_mm':error*1000,
                                     'yaw_deg':math.degrees(angle),'cycle_seconds':now-self.cycle_started,
                                     'elapsed_seconds':now-self.run_started,
                                     'dx_mm':(measured.x-self.expected.x)*1000,
                                     'dy_mm':(measured.y-self.expected.y)*1000,
                                     'dz_mm':(measured.z-self.expected.z)*1000,
                                     'pass':error<=.01 and angle<=math.radians(5)})
                self.cycle_started=None
                self.report('VERIFIED' if self.records[-1]['pass'] else 'OUT OF TOLERANCE')
                return measured
            if error>.05 or angle>math.radians(10): raise RuntimeError('Released box outside recovery envelope')
            # Regrasp from a fresh observation and remeasure the grasp offset; never reuse a previous box correction.
            self.placed.discard(identity)
            self.targets[identity]=(self.selected.kind,measured)
            target=Detection(identity,self.selected.kind,measured,.99)
            if not self.regrasp(target): raise RuntimeError('Placement correction regrasp failed')
            self.recovering=True
            try:
                self.lift(); self.transfer(self.expected); self.place(self.expected)
            finally:
                self.recovering=False
        return None

    def regrasp(self,target):
        # Placement workspace is excluded by observe(), so reacquire directly from its sensor ROI.
        measured=self.measured(target.pose)
        return self.grasp_observed(Detection(target.identity,target.kind,measured,.99))
    def safe_stop(self):
        if self.positions:
            self.cmd.publish(Float64MultiArray(data=[self.positions[n] for n in ['axis_x','axis_y','axis_z','axis_yaw']]))
        # Never release vacuum on an uncertain loaded failure.


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--placement-mode',choices=['precise','coarse'],default='precise')
    args=parser.parse_args(rospy.myargv()[1:])
    rospy.init_node('box_stacking_demo')
    robot=GazeboAdapter(args.placement_mode)
    deadline=time.monotonic()+15
    while not robot.positions and time.monotonic()<deadline and not rospy.is_shutdown(): time.sleep(.05)
    robot.move(0,0,1.65,0)
    # Scene setup owns spawn poses; perception/control never receives this manifest.
    from gazebo_msgs.srv import SpawnModel
    from geometry_msgs.msg import Pose as SpawnPose
    import random
    scene=json.loads((Path(__file__).parent/'spawn_scene.json').read_text())
    boxes=list(scene['boxes']); random.Random(scene['seed']).shuffle(boxes)
    rospy.wait_for_service('/gazebo/spawn_sdf_model',timeout=15)
    spawn=rospy.ServiceProxy('/gazebo/spawn_sdf_model',SpawnModel)
    for index,box in enumerate(boxes):
        robot.report('RANDOM SPAWN {}/8 | seed {}'.format(index+1,scene['seed']))
        origin=SpawnPose(); origin.orientation.w=1
        response=spawn(box['name'],box['sdf'],'',origin,'world')
        if not response.success: raise RuntimeError('Spawn failed: '+response.status_message)
        time.sleep(.65)
    time.sleep(1)
    robot.run_started=time.monotonic(); robot.report('RUNNING')
    pallet=Pallet([Zone('A',Pose(1,1.05,.72),1.3,.9),Zone('B',Pose(1,-1.05,.72),.9,.7)],slots_per_layer=2)
    result=Supervisor(pallet,robot).run()
    result['visual_corrections']=robot.corrections
    result['box_records']=robot.records
    result['scene_seed']=scene['seed']
    result['routes']=robot.routes
    result['pick_timings']=robot.pick_timings
    result['wheels_locked']=True
    result['elapsed_seconds']=time.monotonic()-robot.run_started
    robot.status_pub.publish(String(data=json.dumps({'phase':result['status'].upper(),'started':robot.run_started,
        'finished':time.monotonic(),'records':robot.records,'reason':result['reason']})))
    output=Path(__file__).resolve().parent/'last_run.json'
    result['placement_mode']=args.placement_mode
    result['regrasp_count']=sum(c.get('stage')=='released' and c.get('attempt',0)>0 for c in robot.corrections)
    output.write_text(json.dumps(result,indent=2))
    (output.parent/('run_'+args.placement_mode+'_'+time.strftime('%Y%m%d_%H%M%S')+'.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['status']=='complete' else 2)
