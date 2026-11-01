import json

import pytest

from sukethon.ros_monitor import validate_config
from sukethon.telemetry import analyze, load_samples, validate_sample


def sample(kind="measured", t=1.0, position=None):
    return {"stream": "arm", "kind": kind, "t": t, "names": ["j1"],
            "position": [0.2 if position is None else position], "velocity": [], "effort": []}


def test_analyze_tracking_and_speed():
    result = analyze([sample("command", 1.0, 0.0), sample("measured", 1.1, 0.2),
                      sample("measured", 1.2, 0.4)])
    joint = result["joints"][0]
    assert joint["tracking_pairs"] == 2
    assert joint["tracking_rmse"] == pytest.approx((0.1) ** 0.5)
    assert joint["peak_speed_estimate"] == pytest.approx(2.0)


def test_rejects_mismatched_arrays():
    value = sample()
    value["position"] = []
    with pytest.raises(ValueError):
        validate_sample(value)


def test_rejects_clock_reset():
    with pytest.raises(ValueError, match="backwards"):
        analyze([sample(t=2), sample(t=1)])


def test_config_rejects_ground_truth_topic():
    with pytest.raises(ValueError, match="forbidden"):
        validate_config({"schema_version": 1, "duration_seconds": 1,
                         "command_max_age_seconds": 1,
                         "streams": [{"id": "x", "measured_topic": "/gazebo/model_states"}]})


def test_jsonl_invalid_line_is_actionable(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(sample()) + "\n{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        load_samples(path)
