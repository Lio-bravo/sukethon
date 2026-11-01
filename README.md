# sukethon

Sukethon combines a simulator-independent box-stacking task core with a ROS1/Gazebo 11 simulation prototype. The simulator is a custom force-actuated XYZ plus yaw gantry with eight dynamic A/B boxes, RGB-D sensing, and contact-gated vacuum behavior. It is a gantry prototype, not a six-axis industrial arm.

## Start here

- Python package, dry runs, and test suite: see [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md#native-python-setup).
- ROS Noetic/Gazebo 11 setup and four-shell launch sequence: see [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md#rosgazebo-prerequisites) and [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md#baseline-simulation).
- Vacuum engineering experiment and fault checks: see [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md#vacuum-experiment).
- Curated observed runs and their limits: see [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md#observed-evidence).

## Python package

The `sukethon/` package provides SI-unit A/B box specifications, rotated 2x2x2 pallet slots, reservation and verification transactions, bounded-retry supervision, a synthetic adapter, and an observation-only ROS1 telemetry collector. It does not publish control commands or consume simulator ground truth.

```powershell
python -m pip install -e .
python -m sukethon.cli dry-run
python -m pytest -q
```

The package has no mandatory runtime dependencies. ROS collection requires the ROS1 environment and approved `sensor_msgs/JointState` topics; configure real authorized topics instead of the placeholders in `config/monitor.json`.

## Scope and limitations

The Gazebo prototype uses RGB-D and joint feedback, contact collision identity for simplified vacuum attachment, and generated colored boxes for segmentation. It does not yet represent a complete robot collision model, hardware-calibrated pneumatic dynamics, flexible cup deformation, general uncolored-carton perception, ROS2/MoveIt2 execution, or physical completion. Passing software tests and simulation thresholds is not a physical safety or hardware score claim.

Generated scenes, build output, videos, full logs, telemetry archives, and presentation archives are ignored by design. Small curated benchmark summaries and meaningful source/test/configuration files remain eligible for version control. Existing local files are not deleted.
