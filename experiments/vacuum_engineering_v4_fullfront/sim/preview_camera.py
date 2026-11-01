"""Isolated camera-only smoke scene; shuts down only its own processes."""
import os,sys,socket,subprocess,time,signal,json
from pathlib import Path
R=Path(__file__).resolve().parent
processes=[]
def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
env=os.environ.copy();rp,gp=port(),port();env.update(ROS_MASTER_URI=f'http://127.0.0.1:{rp}',GAZEBO_MASTER_URI=f'http://127.0.0.1:{gp}',ROS_HOSTNAME='localhost')
def launch(cmd,name):
    f=(R/name).open('w');p=subprocess.Popen(cmd,cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);processes.append((p,f));return p
try:
    subprocess.run([sys.executable,str(R/'generate_world.py')],env=env,check=True)
    launch(['roscore','-p',str(rp)],'preview_ros.log');time.sleep(4)
    launch([sys.executable,str(R/'run_sim.py'),'server'],'preview_gazebo.log')
    code="import rospy,cv2;from sensor_msgs.msg import Image;from cv_bridge import CvBridge;rospy.init_node('camera_fit_proof');m=rospy.wait_for_message('/main_view/image_raw',Image,timeout=80);cv2.imwrite('camera_test_fullfront.png',CvBridge().imgmsg_to_cv2(m,'bgr8'));print(m.width,m.height)"
    subprocess.run([sys.executable,'-c',code],cwd=R,env=env,check=True,timeout=100)
finally:
    for p,f in reversed(processes):
        try:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=8)
        except ProcessLookupError:pass
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL)
        f.close()
