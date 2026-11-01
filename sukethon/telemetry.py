"""Validated JSONL observations and offline joint metrics (SI units)."""
import json
import math
from pathlib import Path


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Expected a finite numeric value")
    return float(value)


def validate_sample(sample):
    if sample.get("kind") not in ("measured", "command"):
        raise ValueError("Sample kind must be measured or command")
    if not isinstance(sample.get("stream"), str) or not sample["stream"]:
        raise ValueError("Sample requires a stream identifier")
    if finite(sample["t"]) < 0:
        raise ValueError("Sample time must be nonnegative")
    names = sample["names"]
    if not isinstance(names, list) or not names or any(not isinstance(n, str) or not n for n in names):
        raise ValueError("Joint names must be a nonempty list of strings")
    if len(set(names)) != len(names):
        raise ValueError("Duplicate joint names")
    positions = sample["position"]
    if not isinstance(positions, list) or len(positions) != len(names):
        raise ValueError("Position and name lengths differ")
    for value in positions:
        finite(value)
    for field in ("velocity", "effort"):
        values = sample.get(field, [])
        if not isinstance(values, list) or (values and len(values) != len(names)):
            raise ValueError(field + " and name lengths differ")
        for value in values:
            finite(value)
    return sample


def load_samples(path):
    samples = []
    with Path(path).open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                samples.append(validate_sample(json.loads(line)))
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError("Invalid telemetry at line {}: {}".format(number, exc)) from exc
    return samples


def analyze(samples, command_max_age=0.5):
    max_age = finite(command_max_age)
    if max_age <= 0:
        raise ValueError("Command maximum age must be positive")
    commands, previous, stats, clocks = {}, {}, {}, {}
    measured_count = 0
    for sample in samples:
        validate_sample(sample)
        stream, kind, timestamp = sample["stream"], sample["kind"], sample["t"]
        key = (stream, kind)
        if timestamp < clocks.get(key, -1):
            raise ValueError("Time moved backwards for {} {}; split recordings at clock resets".format(*key))
        clocks[key] = timestamp
    # Merge by source time; command precedes measurement at equal timestamps.
    ordered = sorted(samples, key=lambda s: (s["t"], s["kind"] != "command"))
    for sample in ordered:
        stream, timestamp = sample["stream"], sample["t"]
        for index, name in enumerate(sample["names"]):
            joint = (stream, name)
            position = sample["position"][index]
            if sample["kind"] == "command":
                commands[joint] = (timestamp, position)
                continue
            measured_count += 1
            stat = stats.setdefault(joint, {"samples": 0, "position_min": position, "position_max": position,
                                           "peak_speed_estimate": None, "tracking_pairs": 0,
                                           "tracking_squared_sum": 0.0, "tracking_abs_max": None})
            stat["samples"] += 1
            stat["position_min"] = min(stat["position_min"], position)
            stat["position_max"] = max(stat["position_max"], position)
            old = previous.get(joint)
            if old is not None and timestamp > old[0]:
                speed = abs((position - old[1]) / (timestamp - old[0]))
                stat["peak_speed_estimate"] = max(stat["peak_speed_estimate"] or 0, speed)
            previous[joint] = (timestamp, position)
            command = commands.get(joint)
            if command is not None and 0 <= timestamp - command[0] <= max_age:
                error = abs(position - command[1])
                stat["tracking_pairs"] += 1
                stat["tracking_squared_sum"] += error * error
                stat["tracking_abs_max"] = max(stat["tracking_abs_max"] or 0, error)
    if not measured_count:
        raise ValueError("No measured joint samples found")
    result = []
    for (stream, name), stat in sorted(stats.items()):
        count = stat["tracking_pairs"]
        square_sum = stat.pop("tracking_squared_sum")
        stat["tracking_rmse"] = math.sqrt(square_sum / count) if count else None
        result.append(dict(stream=stream, joint=name, **stat))
    return {"schema_version": 1, "joint_observations": measured_count, "joints": result,
            "notes": ["Speed is estimated from position differences without angle unwrapping.",
                      "Tracking uses the latest earlier command in the same stream and the configured maximum age.",
                      "Joint effort is not equivalent to box contact force; these metrics do not prove a successful grasp."]}
