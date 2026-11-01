import math
import unittest
from sukethon.task import Pose
from sukethon.servo import corrected_tool, placement_error, trajectory_duration, smooth_target


class ServoTests(unittest.TestCase):
    def test_each_box_uses_its_own_observation(self):
        tool=Pose(1,1,1.5)
        desired=Pose(1,1,.9)
        corrected=corrected_tool(tool,desired,Pose(1.012,.994,.9,.02))
        self.assertAlmostEqual(corrected.x,.988)
        self.assertAlmostEqual(corrected.y,1.006)
        self.assertAlmostEqual(corrected.yaw,-.02)
        self.assertEqual(corrected_tool(tool,desired,desired),tool)

    def test_reject_unsafe_recovery(self):
        with self.assertRaises(ValueError):
            corrected_tool(Pose(0,0,1),Pose(0,0,0),Pose(.1,0,0))
        with self.assertRaises(ValueError):
            corrected_tool(Pose(0,0,1),Pose(0,0,0),Pose(0,0,0,.4))

    def test_smooth_trajectory_bounds_and_endpoints(self):
        start=[0,0,1,0]; end=[1,1,1,.5]
        duration=trajectory_duration(start,end)
        samples=[smooth_target(start,end,i/1000) for i in range(1001)]
        self.assertEqual(samples[0],start); self.assertEqual(samples[-1],end)
        dt=duration/1000
        velocities=[[(b-a)/dt for a,b in zip(left,right)] for left,right in zip(samples,samples[1:])]
        self.assertLessEqual(max(math.sqrt(sum(v*v for v in row[:3])) for row in velocities),.70001)
        acceleration=[math.sqrt(sum(((b-a)/dt)**2 for a,b in zip(left[:3],right[:3]))) for left,right in zip(velocities,velocities[1:])]
        self.assertLessEqual(max(acceleration),.8001)
        for limit in (0,-1,float('nan')):
            with self.assertRaises(ValueError): trajectory_duration(start,end,speed=limit)

    def test_path_clearance(self):
        from sukethon.servo import clearance_height
        start,end=Pose(-1,0,1),Pose(1,0,1)
        self.assertAlmostEqual(clearance_height(start,end,[],.3,.34),1.095)
        self.assertAlmostEqual(clearance_height(start,end,[(0,0,1.28,.3)],.3,.34),1.655)
        self.assertAlmostEqual(clearance_height(start,end,[(0,2,2,.3)],.3,.34),1.095)
        self.assertAlmostEqual(clearance_height(start,start,[(-1,0,1,.3)],.3,.34),1.375)
        with self.assertRaises(ValueError): clearance_height(start,end,[],.3,.34,margin=0)
        with self.assertRaises(ValueError): clearance_height(start,end,[(0,0,1,-.1)],.3,.34)

    def test_two_layer_eight_box_layout(self):
        from sukethon.task import Pallet,Zone
        pallet=Pallet([Zone('A',Pose(1,1,.72),1.3,.9),Zone('B',Pose(1,-1,.72),.9,.7)],slots_per_layer=2)
        for kind in ('A','B'):
            slots=[]
            for i in range(4):
                slot=pallet.reserve(kind,kind+str(i)); slots.append(slot)
                self.assertTrue(pallet.verify(slot,slot.pose))
            self.assertEqual([s.layer for s in slots],[0,0,1,1])
            self.assertEqual(slots[0].pose.x,slots[2].pose.x)
            self.assertEqual(slots[0].pose.y,slots[2].pose.y)
        self.assertEqual(len(pallet.confirmed),8)

    def test_rectangle_symmetry(self):
        self.assertAlmostEqual(placement_error(Pose(0,0,0),Pose(0,0,0,math.pi))[1],0)
