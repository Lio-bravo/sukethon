"""Sensor-pose correction and bounded smooth trajectories, independent of ROS."""
import math
from .task import Pose, number


def rectangle_yaw_error(target, observed):
    return (target-observed+math.pi/2) % math.pi-math.pi/2


def placement_error(target, observed):
    return (math.sqrt((target.x-observed.x)**2+(target.y-observed.y)**2+
                      (target.z-observed.z)**2),
            abs(rectangle_yaw_error(target.yaw, observed.yaw)))


def corrected_tool(tool, desired, measured, max_translation=.06, max_yaw=math.radians(12)):
    """Recompute correction from this observation, never accumulate prior box offsets."""
    error, angle = placement_error(desired, measured)
    if error>max_translation or angle>max_yaw:
        raise ValueError('Visual correction exceeds safe recovery envelope')
    return Pose(tool.x+desired.x-measured.x, tool.y+desired.y-measured.y,
                tool.z+desired.z-measured.z,
                tool.yaw+rectangle_yaw_error(desired.yaw, measured.yaw))


def trajectory_duration(start, end, speed=.7, acceleration=.8, yaw_speed=.8):
    for value in (speed, acceleration, yaw_speed):
        number(value, 'motion limit', True)
    distance=math.sqrt(sum((a-b)**2 for a,b in zip(start[:3],end[:3])))
    # Quintic smoothstep maxima: velocity 1.875, acceleration 5.774.
    return max(.15,1.875*distance/speed,math.sqrt(5.774*distance/acceleration),
               1.875*abs(end[3]-start[3])/yaw_speed)


def clearance_height(start, end, obstacles, footprint, bottom_offset, margin=.035, floor=.72):
    """Tool height for a swept, conservatively circular load footprint.

    Obstacles are sensor-derived (x, y, top, footprint_radius) tuples.
    bottom_offset is the distance from tool origin to the load's bottom.
    """
    number(footprint, 'footprint radius', True)
    number(bottom_offset, 'bottom offset', True)
    number(margin, 'clearance margin', True)
    dx,dy=end.x-start.x,end.y-start.y
    length2=dx*dx+dy*dy
    highest=number(floor,'support height')
    for x,y,top,radius in obstacles:
        for value in (x,y,top,radius): number(value,'obstacle')
        if radius<0: raise ValueError('Obstacle radius must be nonnegative')
        t=max(0.,min(1.,((x-start.x)*dx+(y-start.y)*dy)/length2)) if length2 else 0.
        distance=math.hypot(x-start.x-t*dx,y-start.y-t*dy)
        if distance<=footprint+radius+margin: highest=max(highest,top)
    return highest+bottom_offset+margin


def smooth_target(start, end, fraction):
    fraction=max(0.,min(1.,number(fraction,'trajectory fraction')))
    blend=fraction**3*(10+fraction*(-15+6*fraction))
    return [a+(b-a)*blend for a,b in zip(start,end)]
