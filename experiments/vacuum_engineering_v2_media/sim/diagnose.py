import rospy
from sensor_msgs.msg import JointState,Image
from cv_bridge import CvBridge
import cv2
from pathlib import Path
rospy.init_node('sim_diagnostic',anonymous=True)
msg=rospy.wait_for_message('/gantry/joint_states',JointState,timeout=10)
print(msg)
image=rospy.wait_for_message('/overhead/rgb/image_raw',Image,timeout=15)
p=Path(__file__).parent/'camera.png'
cv2.imwrite(str(p),CvBridge().imgmsg_to_cv2(image,'bgr8'))
print(p)
