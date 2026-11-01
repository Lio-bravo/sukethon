"""ROS1 adapter. Explicit sensor_msgs/JointState topics only; never actuates."""
import json
import re
import threading
from pathlib import Path

from .telemetry import finite, validate_sample


FORBIDDEN = re.compile(r"(^|[/_])(gazebo|model_states|link_states|qpos|ground_truth|groundtruth|mujoco)([/_]|$)", re.I)


def validate_config(config):
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported config schema")
    duration = finite(config.get("duration_seconds"))
    if duration <= 0 or duration > 3600:
        raise ValueError("duration_seconds must be in (0, 3600]")
    age = finite(config.get("command_max_age_seconds"))
    if age <= 0:
        raise ValueError("command_max_age_seconds must be positive")
    streams = config.get("streams")
    if not isinstance(streams, list):
        raise ValueError("streams must be a list")
    ids, topics = set(), set()
    for stream in streams:
        name = stream.get("id")
        if not isinstance(name, str) or not name.strip() or name in ids:
            raise ValueError("Each stream requires a unique nonempty id")
        ids.add(name)
        measured = stream.get("measured_topic")
        command = stream.get("command_topic")
        if measured is None:
            raise ValueError("Each stream requires a measured_topic")
        for topic in (measured, command):
            if topic is None:
                continue
            if not isinstance(topic, str) or not re.fullmatch(r"/[A-Za-z][A-Za-z0-9_/]*", topic) or FORBIDDEN.search(topic):
                raise ValueError("Invalid or forbidden observation topic: " + str(topic))
            if topic in topics:
                raise ValueError("Topics must be unique across streams and roles")
            topics.add(topic)
    return config


def collect(config, output):
    validate_config(config)
    if not config["streams"]:
        raise ValueError("No approved streams configured; set measured_topic after inspecting the organizer environment")
    try:
        import rospy
        from sensor_msgs.msg import JointState
    except ImportError as exc:
        raise RuntimeError("ROS1 Python environment required; source its setup.bash before collecting") from exc
    import time
    lock = threading.Lock()
    subscribers = []
    accepting = threading.Event()
    accepting.set()
    counts = {"written": 0, "rejected": 0, "unstamped": 0}
    output = Path(output)
    # Exclusive create prevents accidental overwriting of an earlier experiment.
    with output.open("x", encoding="utf-8") as handle:
        rospy.init_node("sukethon_observer", anonymous=True, disable_signals=True)

        def callback(msg, stream, kind):
            timestamp = msg.header.stamp.to_sec()
            with lock:
                if not accepting.is_set():
                    return
                if timestamp <= 0:
                    counts["unstamped"] += 1
                    return
                sample = {"stream": stream, "kind": kind, "t": timestamp,
                          "names": list(msg.name), "position": list(msg.position),
                          "velocity": list(msg.velocity), "effort": list(msg.effort)}
                try:
                    validate_sample(sample)
                except (ValueError, TypeError, KeyError) as exc:
                    counts["rejected"] += 1
                    rospy.logwarn_throttle(5, "Rejected joint observation: %s", str(exc))
                    return
                handle.write(json.dumps(sample, allow_nan=False) + "\n")
                handle.flush()
                counts["written"] += 1

        try:
            for stream in config["streams"]:
                for role, field in (("measured", "measured_topic"), ("command", "command_topic")):
                    if stream.get(field):
                        subscribers.append(rospy.Subscriber(stream[field], JointState,
                            lambda msg, s=stream["id"], k=role: callback(msg, s, k), queue_size=100))
            deadline = time.monotonic() + config["duration_seconds"]
            while not rospy.is_shutdown() and time.monotonic() < deadline:
                time.sleep(0.05)
        finally:
            with lock:
                accepting.clear()
            for subscriber in subscribers:
                subscriber.unregister()
            # Serialize shutdown against callbacks before closing the output handle.
            rospy.signal_shutdown("Observation complete")
            with lock:
                pass
    return counts
