"""Capture sensor evidence and joint feedback without simulator object poses."""
import time
from pathlib import Path
import cv2
import rospy
from sensor_msgs.msg import Image,JointState
from cv_bridge import CvBridge
rospy.init_node('capture_sensor_state')
root=Path(__file__).parent
msg=rospy.wait_for_message('/overhead/rgb/image_raw',Image,timeout=15)
cv2.imwrite(str(root/'current_view.png'),CvBridge().imgmsg_to_cv2(msg,'bgr8'))
print(rospy.wait_for_message('/gantry/joint_states',JointState,timeout=10))
