import math
import pytest

from sukethon.task import Pallet, Pose, Zone
from sukethon.supervisor import Detection, DryRunAdapter, Supervisor


def pallet():
    return Pallet([Zone("A", Pose(0, 1, 0.75), 1.3, 0.9),
                   Zone("B", Pose(0, -1, 0.75), 0.9, 0.7)])


def boxes(a=4):
    return [Detection(str(i), "A" if i < a else "B", Pose(0, 0, 1), 1) for i in range(8)]


@pytest.mark.parametrize("a", range(9))
def test_all_eight_box_class_distributions(a):
    p = pallet()
    result = Supervisor(p, DryRunAdapter(boxes(a))).run()
    assert result["status"] == "complete"
    assert len(p.confirmed) == 8
    assert not p.reserved


def test_upper_layer_requires_verified_lower_layer():
    p = pallet()
    slots = [p.reserve("A", str(i)) for i in range(4)]
    with pytest.raises(RuntimeError, match="supported"):
        p.reserve("A", "upper")
    for slot in slots:
        assert p.verify(slot, slot.pose)
    assert p.reserve("A", "upper").layer == 1


def test_wrong_placement_blocks_slot():
    p = pallet()
    slot = p.reserve("A", "box")
    assert not p.verify(slot, Pose(slot.pose.x + 0.02, slot.pose.y, slot.pose.z))
    assert slot.key not in p.confirmed
    with pytest.raises(RuntimeError):
        p.release_unpicked(slot)


def test_wrapped_yaw_and_boundary_tolerance():
    p = pallet()
    slot = p.reserve("B", "box")
    assert p.verify(slot, Pose(slot.pose.x + 0.01, slot.pose.y, slot.pose.z, 2*math.pi))


def test_grasp_retry_reobserves():
    p = pallet()
    robot = DryRunAdapter(boxes(), fail={"grasp": 1})
    result = Supervisor(p, robot).run()
    assert result["status"] == "complete"
    assert any(e["state"] == "reobserve" for e in result["events"])


def test_exhausted_grasp_releases_empty_reservation():
    p = pallet()
    robot = DryRunAdapter(boxes(), fail={"grasp": 2})
    result = Supervisor(p, robot).run()
    assert result["status"] == "stopped"
    assert not p.reserved
    assert robot.stopped and robot.held is None


@pytest.mark.parametrize("stage", ["lift", "transfer", "place"])
def test_loaded_failure_retains_box_and_reservation(stage):
    p = pallet()
    robot = DryRunAdapter(boxes(), fail={stage: 1})
    result = Supervisor(p, robot).run()
    assert result["status"] == "stopped"
    assert robot.stopped and robot.held is not None
    assert len(p.reserved) == 1 and not p.confirmed


def test_placement_failure_is_not_counted():
    p = pallet()
    robot = DryRunAdapter(boxes(), placement_offset=0.02)
    result = Supervisor(p, robot).run()
    assert result["completed_boxes"] == 0
    assert result["uncertain_slots"] == 1
    assert robot.stopped


def test_time_budget_and_single_use():
    times = iter([0, 601])
    supervisor = Supervisor(pallet(), DryRunAdapter(boxes()), clock=lambda: next(times))
    assert supervisor.run()["status"] == "stopped"
    with pytest.raises(RuntimeError, match="single-use"):
        supervisor.run()


def test_undersized_zone_rejected():
    with pytest.raises(ValueError, match="footprint"):
        Zone("A", Pose(0, 0, 0), 0.6, 0.4)


def test_duplicate_identity_stops():
    class DuplicateRobot(DryRunAdapter):
        def observe(self):
            return [boxes()[0], boxes()[0]]
    robot = DuplicateRobot(boxes())
    assert Supervisor(pallet(), robot).run()["status"] == "stopped"
    assert robot.stopped
