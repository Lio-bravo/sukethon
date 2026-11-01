import execute
import rospy
import time
rospy.init_node('check_vision',anonymous=True)
a=execute.GazeboAdapter()
time.sleep(2)
for kind,pose in a.detect(): print(kind,pose)
from sukethon.task import Pose
for target in [Pose(.69,.84,.86,0),Pose(1.31,.84,.86,0),Pose(.69,1.26,.86,0),Pose(1.31,1.26,.86,0)]:
    print('Slot',target,'observed',a.detect(roi=target))
