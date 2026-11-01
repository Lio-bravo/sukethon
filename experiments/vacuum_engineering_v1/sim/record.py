"""Record WSLg X11 Gazebo window with ffmpeg; fixed duration, no input events."""
import subprocess
import re
from pathlib import Path
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--seconds',type=int,default=240)
args=parser.parse_args()
text=subprocess.check_output(['xwininfo','-root','-tree'],text=True)
windows=[line for line in text.splitlines() if 'Gazebo' in line and 'gazebo' in line.lower()]
if not windows:
    raise SystemExit('Gazebo X11 window unavailable; open gzclient first')
match=re.search(r'0x[0-9a-fA-F]+',windows[0])
info=subprocess.check_output(['xwininfo','-id',match.group()],text=True)
def field(name):
    return int(re.search(name+r':\s+(-?\d+)',info).group(1))
x=field('Absolute upper-left X'); y=field('Absolute upper-left Y')
w=field('Width'); h=field('Height')
output=Path(__file__).parent/'videos'
output.mkdir(exist_ok=True)
raise SystemExit(subprocess.call(['ffmpeg','-y','-f','x11grab','-framerate','20','-video_size',f'{w}x{h}',
    '-i',f':0+{x},{y}','-t',str(args.seconds),'-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2','-c:v','libx264',
    '-preset','veryfast','-crf','22','-pix_fmt','yuv420p',str(output/'gazebo_trial.mp4')]))
