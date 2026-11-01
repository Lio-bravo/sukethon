"""Read-only sensor diagnostic for an occluded held box."""
import time
import rospy
import cv2
from execute import GazeboAdapter
from sukethon.task import Pose
rospy.init_node('sensor_diagnostic')
r=GazeboAdapter(); time.sleep(2)
print('joints',r.positions,flush=True)
print('all',r.detect(),flush=True)
print('roi',r.detect(Pose(1.31,.84,1.45)),flush=True)
with r.lock:
    cv2.imwrite('/mnt/e/Project/sukethon/sim/held_view.png',r.rgb)
