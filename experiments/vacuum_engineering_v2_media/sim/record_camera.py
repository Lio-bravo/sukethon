"""Record sensor video and display live mission metrics in a separate HUD window."""
import argparse
import os
import hashlib
import json
import threading
import time
from pathlib import Path
import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from std_msgs.msg import String

parser=argparse.ArgumentParser()
parser.add_argument('--seconds',type=float,default=650)
parser.add_argument('--topic',default='/overhead/rgb/image_raw')
parser.add_argument('--main-topic',default='/main_view/image_raw')
parser.add_argument('--no-main-view',action='store_true',help='Record overhead view only')
parser.add_argument('--no-preview',action='store_true')
args=parser.parse_args()
rospy.init_node('simulation_video_recorder',anonymous=True)
folder=Path(__file__).parent/'videos'; folder.mkdir(exist_ok=True)
output=folder/('sensor_'+time.strftime('%Y%m%d_%H%M%S')+'.mp4')
bridge=CvBridge(); writer=None; frames=0
lock=threading.Lock(); latest=None; main_latest=None; status={'phase':'WAITING FOR SCENE','records':[]}
def image_received(msg):
    global latest
    with lock: latest=bridge.imgmsg_to_cv2(msg,'bgr8').copy()
def main_image_received(msg):
    global main_latest
    with lock: main_latest=bridge.imgmsg_to_cv2(msg,'bgr8').copy()
def status_received(msg):
    global status
    try:
        data=json.loads(msg.data)
        with lock: status=data
    except (ValueError,TypeError) as exc: rospy.logwarn('Invalid HUD status: %s',exc)
rospy.Subscriber(args.topic,Image,image_received,queue_size=1)
if not args.no_main_view: rospy.Subscriber(args.main_topic,Image,main_image_received,queue_size=1)
rospy.Subscriber('/demo/status',String,status_received,queue_size=1)
run_id=Path(os.environ.get('SUKETHON_TELEMETRY','unknown')).parent.name
model_id=hashlib.sha256((Path(__file__).parent/'vacuum_model.hh').read_bytes()).hexdigest()[:12]
started=time.monotonic(); last_written=-1; last_snapshot=-1; completed_at=None
try:
    while not rospy.is_shutdown() and time.monotonic()-started<args.seconds:
        with lock:
            image=None if latest is None else latest.copy()
            main_image=None if main_latest is None else main_latest.copy()
            data=dict(status)
        if image is None:
            time.sleep(.03); continue
        if main_image is None and not args.no_main_view:
            main_image=np.zeros((image.shape[0],int(image.shape[0]*1.6),3),np.uint8)
            cv2.putText(main_image,'WAITING FOR GAZEBO MAIN VIEW',(24,48),cv2.FONT_HERSHEY_SIMPLEX,.8,(230,240,230),2,cv2.LINE_AA)
        if main_image is not None:
            main_image=cv2.resize(main_image,(int(image.shape[0]*1.6),image.shape[0]))
            cv2.putText(main_image,'MAIN VIEW | SPIDER GANTRY',(20,35),cv2.FONT_HERSHEY_SIMPLEX,.8,(220,245,230),2,cv2.LINE_AA)
            cv2.putText(image,'OVERHEAD RGB-D',(20,35),cv2.FONT_HERSHEY_SIMPLEX,.8,(220,245,230),2,cv2.LINE_AA)
            views=np.hstack((main_image,image))
        else:
            views=image
        panel=np.zeros((views.shape[0],590,3),np.uint8); panel[:]=(30,35,28)
        def text(value,y,color=(230,240,230),scale=.58):
            cv2.putText(panel,value,(18,y),cv2.FONT_HERSHEY_SIMPLEX,scale,color,1,cv2.LINE_AA)
        now=time.monotonic(); begin=data.get('started')
        elapsed=max(0.,data.get('finished',now)-begin) if begin else 0.
        text('SPIDER GANTRY | MAIN + OVERHEAD RGB-D',38,(110,240,125),.75)
        text('MISSION TIME  {:07.2f} s'.format(elapsed),82,(110,240,125),.85)
        text(str(data.get('phase','WAITING'))[:65],118,scale=.49)
        text('Center <= 10 mm | Yaw <= 5 deg',151)
        text('RUN '+run_id+' | MODEL '+model_id,918,(110,240,125),.47)
        text('WHEEL BRAKES: LOCKED | SIMULATION',945,(110,240,125),.47)
        text('Cycle: pick start -> released-box verification',180,scale=.48)
        text('# Type   Center/mm   Yaw/deg   Cycle/s   Result',226,scale=.52)
        records=data.get('records',[])
        for index in range(8):
            y=266+index*68
            if index<len(records):
                row=records[index]; color=(100,235,120) if row['pass'] else (80,80,255)
                text('{}  {}       {:6.2f}       {:5.2f}     {:6.2f}   {}'.format(index+1,row['kind'],row['center_mm'],row['yaw_deg'],row['cycle_seconds'],'PASS' if row['pass'] else 'FAIL'),y,color,.51)
                text('dx {:+.2f}  dy {:+.2f}  dz {:+.2f} mm | total {:.2f}s'.format(row['dx_mm'],row['dy_mm'],row['dz_mm'],row['elapsed_seconds']),y+23,scale=.45)
            else: text('{}  --       --          --        --      WAIT'.format(index+1),y,scale=.51)
        text('Completed: {}/8'.format(sum(r['pass'] for r in records)),850,(110,240,125),.75)
        if data.get('reason'): text(str(data['reason'])[:72],890,(80,80,255),.44)
        combined=np.hstack((views,panel))
        if writer is None:
            writer=cv2.VideoWriter(str(output),cv2.VideoWriter_fourcc(*'mp4v'),10,(combined.shape[1],combined.shape[0]))
            if not writer.isOpened(): raise RuntimeError('Video writer unavailable')
        slot=int((now-started)*10)
        while last_written<slot:
            writer.write(combined); frames+=1; last_written+=1
        if slot // 10 > last_snapshot:
            cv2.imwrite(str(folder/'live_scoreboard.png'),combined)
            last_snapshot=slot // 10
        if not args.no_preview:
            cv2.imshow('Spider Gantry - Live Timer and 8 Box Results',cv2.resize(combined,(1162,720)))
            cv2.waitKey(1)
        if data.get('finished'):
            completed_at=completed_at or now
            if now-completed_at>8:
                cv2.imwrite(str(output.with_suffix('.png')),combined)
                break
        time.sleep(.02)
except rospy.ROSInterruptException:
    pass
finally:
    if writer: writer.release()
    cv2.destroyAllWindows()
print(str(output),'frames=',frames,'wall_seconds=',time.monotonic()-started)
