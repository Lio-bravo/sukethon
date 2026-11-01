"""Read-only simulator discovery in WSL."""
import subprocess

commands = [
    'for x in gazebo gz roscore ros2 ffmpeg cmake g++ xwininfo; do command -v "$x" || true; done',
    'source /opt/ros/noetic/setup.bash && rospack list',
    'source /opt/ros/jazzy/setup.bash && ros2 pkg list',
    'pkg-config --modversion gazebo; python3 -c "import cv2, numpy; print(cv2.__version__)"',
]
for cmd in commands:
    result = subprocess.run(['bash', '-c', cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in result.stdout.splitlines():
        if cmd.endswith('list'):
            if not any(word in line for word in ('moveit', 'panda', 'franka', 'controller', 'gazebo', 'ros_gz', 'ur_')):
                continue
        print(line)
    if result.returncode:
        print(result.stderr.strip())
