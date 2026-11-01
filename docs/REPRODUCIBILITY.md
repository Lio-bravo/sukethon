# Reproducibility

This repository contains two related surfaces:

- `sukethon/` is a simulator-independent Python task core, supervisor, telemetry format, and ROS1 observation CLI.
- `sim/` is the baseline ROS Noetic/Gazebo 11 XYZ+yaw gantry simulation.
- `experiments/vacuum_engineering_v1/` is a separate experimental copy with the vacuum capacity model and fault scenarios. It is intentionally kept separate from the baseline.

All paths below are relative to the repository root. Do not rely on the old machine-specific `/mnt/e/...` path; substitute the checkout path visible inside your WSL distribution.

## Native Python setup

The package declares no mandatory runtime dependencies. Python 3.8 or newer is required. `pytest` is needed for the test suite.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools
python -m pip install -e .
python -m pip install pytest
python -m pytest -q
```

The package-only workflow does not require ROS, Gazebo, OpenCV, NumPy, or PowerPoint tooling:

```bash
python -m sukethon.cli dry-run
python -m sukethon.cli dry-run --a-count 8
python -m sukethon.cli dry-run --fail grasp
python -m sukethon.cli dry-run --fail transfer
python -m sukethon.cli dry-run --placement-offset 0.02
```

The failure and placement-offset examples intentionally return exit code 2. They exercise supervisor rejection paths; they are not failed test-suite runs.

## ROS/Gazebo prerequisites

The simulation was developed for WSL Ubuntu 20.04 with ROS Noetic and Gazebo 11. Ubuntu 24.04 is not the primary target. Install the system packages in the Ubuntu 20.04 distribution:

```bash
sudo apt update
sudo apt install -y build-essential cmake python3 python3-pip \
  gazebo11 libgazebo11-dev \
  ros-noetic-ros-base ros-noetic-roscpp ros-noetic-std-msgs \
  ros-noetic-sensor-msgs ros-noetic-cv-bridge \
  ros-noetic-gazebo-ros-pkgs ros-noetic-gazebo-plugins \
  python3-opencv python3-numpy
```

The C++ plugin is built by CMake with C++14 and links against Gazebo, `roscpp`, `std_msgs`, and `sensor_msgs`. Runtime camera recording additionally imports OpenCV, NumPy, `rospy`, `cv_bridge`, `sensor_msgs`, and `std_msgs`.

Open a WSL shell in the checkout and source ROS before every simulation shell:

```bash
source /opt/ros/noetic/setup.bash
cd /path/to/sukethon
```

## Baseline simulation

Use separate WSL shells. The build action generates `sim/stacking.world` and `sim/spawn_scene.json`, then builds the plugin in `/tmp/sukethon-gazebo-build`.

Shell 1, ROS master:

```bash
source /opt/ros/noetic/setup.bash
roscore
```

Shell 2, build and Gazebo server:

```bash
source /opt/ros/noetic/setup.bash
cd /path/to/sukethon
python3 sim/run_sim.py build
python3 sim/run_sim.py server
```

Shell 3, optional GUI:

```bash
source /opt/ros/noetic/setup.bash
cd /path/to/sukethon
python3 sim/run_sim.py gui
```

Shell 4, controller and optional rendered camera recording:

```bash
source /opt/ros/noetic/setup.bash
cd /path/to/sukethon
python3 sim/execute.py --placement-mode coarse
python3 sim/record_camera.py --no-preview --seconds 240
```

`execute.py` consumes RGB-D and joint feedback; it does not read simulator ground truth for control. `record_camera.py` writes video output under ignored run paths. WSLg/X11 screen capture may be black; rendered sensor recording is the useful evidence path.

For an isolated benchmark, the runner starts its own ROS/Gazebo processes on dynamically selected ports, writes a timestamped directory under `sim/benchmark_results/`, and cleans up child processes:

```bash
source /opt/ros/noetic/setup.bash
cd /path/to/sukethon
python3 sim/benchmark.py --seeds 8675309 --modes coarse --timeout 650 --no-video
```

`--timeout` must be at least 60 seconds. `--modes` accepts `coarse` or `precise`; `--seeds` accepts one or more integer seeds. Omitting `--no-video` also records a sensor video. The benchmark returns success only when every requested run completes with 8 passed placements.

## Vacuum experiment

The experimental implementation has its own copied package, plugin, generated scene, and build path. Run it from its own directory so imports and generated files stay isolated:

```bash
source /opt/ros/noetic/setup.bash
cd /path/to/sukethon/experiments/vacuum_engineering_v1
python3 sim/run_sim.py build
python3 sim/run_fault_checks.py
```

The fault script runs the leak and overload scenarios with seed `8675309`, then asserts that the vacuum constraint trips and the mission aborts. The overload case injects an extra 1000 N software demand after attachment; it is not a physical added mass. `sim/vacuum_parameters.json` documents the lumped pressure model and explicitly labels its constants as uncalibrated engineering equivalents. The fixed constraint remains a simplification while capacity gates pass; this is not a pneumatic digital twin or hardware safety validation.

The standalone model unit test can run without ROS/Gazebo:

```bash
cd /path/to/sukethon/experiments/vacuum_engineering_v1
c++ -std=c++14 sim/test_vacuum_model.cpp -o /tmp/sukethon-vacuum-model-test
/tmp/sukethon-vacuum-model-test
python3 sim/analyze_vacuum.py
```

## Observed evidence

These are recorded simulation observations, not universal performance claims:

- Baseline `sim/benchmark_results/20261101_093846/summary.json`: seed `8675309`, coarse mode, 8/8 passed, maximum center error 7.041 mm, maximum yaw error 0 degrees, zero regrasp, 195.008 seconds simulated elapsed time.
- Vacuum experiment `experiments/vacuum_engineering_v1/sim/benchmark_results/20261101_100944/summary.json`: seed `8675309`, coarse mode, 8/8 passed, maximum center error 8.882 mm, maximum yaw error 0 degrees, zero regrasp, 210.577 seconds simulated elapsed time.
- Acceptance checks used here are 8/8 placements, center error at most 10 mm, and yaw error at most 5 degrees. Other seeds and modes can produce different results.
- Curated summaries may be committed. Full logs, JSONL telemetry, videos, generated scenes, archives, and build outputs are ignored to avoid repository bloat; local evidence is not deleted by this policy.

## Optional roadshow tooling

`tools/build_roadshow.py`, `tools/build_roadshow_v2.py`, and `tools/preview_roadshow.py` require optional host-Python packages:

```bash
python -m pip install python-pptx Pillow
```

These tools generate presentations, previews, and archives. Outputs are intentionally ignored. They are not required for the package tests or ROS/Gazebo simulation.

## Reproducibility limits

The simulation uses deterministic scene generation when `SUKETHON_SEED` is set, but wall time depends on host load and Gazebo scheduling. The vacuum parameters are not hardware-calibrated. The project does not claim physical robot completion, real-hardware safety, general carton perception, collision validation for a complete robot, or a universal benchmark score. Use the generated result JSON and summary CSV from each run as the record for that run.
