"""WSL Gazebo11 build/launch entry; use with system Python after sourcing Noetic."""
import os
from pathlib import Path
import subprocess
import argparse
import sys

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('action',choices=['build','server','gui'])
args=parser.parse_args()
if args.action=='build':
    subprocess.run([sys.executable,str(ROOT/'generate_world.py')],check=True)
    build=Path('/tmp/sukethon-vacuum-engineering-v4-fullfront-build')
    subprocess.run(['cmake','-S',str(ROOT),'-B',str(build)],check=True)
    subprocess.run(['cmake','--build',str(build),'-j2'],check=True)
else:
    ros_lib='/opt/ros/noetic/lib'
    os.environ['GAZEBO_PLUGIN_PATH']=':'.join(filter(None, ['/tmp/sukethon-vacuum-engineering-v4-fullfront-build', ros_lib, os.environ.get('GAZEBO_PLUGIN_PATH','')]))
    os.environ['LIBGL_ALWAYS_SOFTWARE']='1'
    os.environ['LD_LIBRARY_PATH']=':'.join(filter(None, [ros_lib, '/usr/lib/x86_64-linux-gnu/gazebo-11/plugins', os.environ.get('LD_LIBRARY_PATH','')]))
    if args.action=='server':
        command=['gzserver','--verbose','-s','libgazebo_ros_api_plugin.so',str(ROOT/'stacking.world')]
    else:
        command=['gzclient','--verbose']
    raise SystemExit(subprocess.call(command))
