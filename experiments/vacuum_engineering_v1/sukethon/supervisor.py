"""Synchronous task orchestration. Adapters must enforce operation timeouts.

DryRunAdapter is a logic test double, NOT perception or physics simulation.
"""
from dataclasses import dataclass
import time
from typing import Optional, Protocol, Sequence

from .task import Pose, number


@dataclass(frozen=True)
class Detection:
    identity: str
    kind: str
    pose: Pose
    confidence: float

    def __post_init__(self):
        if not isinstance(self.identity, str) or not self.identity or self.kind not in ("A", "B"):
            raise ValueError("Invalid detection identity or class")
        if not 0 <= number(self.confidence, "confidence") <= 1:
            raise ValueError("Confidence must be in [0, 1]")


class RobotAdapter(Protocol):
    """Implementations use authorized sensors only; never simulator object poses.

    False from grasp means empty tool and safe to retry. Other uncertain failures
    must raise. safe_stop must retain a held load, not blindly release vacuum.
    Place returns only after support, release, and tool withdrawal are confirmed.
    """
    def observe(self) -> Sequence[Detection]: ...
    def grasp(self, target: Detection) -> bool: ...
    def lift(self) -> bool: ...
    def transfer(self, box_center: Pose) -> bool: ...
    def place(self, box_center: Pose) -> bool: ...
    def inspect_placement(self, identity: str) -> Optional[Pose]: ...
    def safe_stop(self) -> None: ...


class Supervisor:
    def __init__(self, pallet, robot, expected_boxes=8, max_attempts=2,
                 time_limit=600.0, clock=time.monotonic):
        for value in (expected_boxes, max_attempts):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("Counts must be positive integers")
        number(time_limit, "time_limit", True)
        self.pallet, self.robot = pallet, robot
        self.expected_boxes, self.max_attempts = expected_boxes, max_attempts
        self.time_limit, self.clock = time_limit, clock
        self.events = []
        self.used = False

    def run(self):
        if self.used:
            raise RuntimeError("Supervisor is single-use; reconcile state before resuming")
        if self.pallet.reserved or self.pallet.confirmed or self.pallet.uncertain:
            raise RuntimeError("A new run requires a reconciled empty pallet")
        self.used = True
        started = self.clock()
        done = set()

        def event(state, identity=None):
            elapsed = self.clock() - started
            self.events.append({"state": state, "box": identity, "elapsed_seconds": elapsed})
            if elapsed >= self.time_limit:
                raise TimeoutError("Task time budget exhausted")

        try:
            while len(done) < self.expected_boxes:
                event("observe")
                detections = list(self.robot.observe())
                identities = [d.identity for d in detections]
                if len(set(identities)) != len(identities):
                    raise RuntimeError("Duplicate detection identities")
                candidates = [d for d in detections if d.identity not in done and d.confidence >= 0.95]
                if not candidates:
                    raise RuntimeError("No sufficiently confident unprocessed box")
                target = sorted(candidates, key=lambda d: d.identity)[0]
                slot = self.pallet.reserve(target.kind, target.identity)
                picked = False
                for attempt in range(self.max_attempts):
                    if attempt:
                        event("reobserve", target.identity)
                        matches = [d for d in self.robot.observe() if d.identity == target.identity]
                        if len(matches) != 1 or matches[0].kind != target.kind or matches[0].confidence < 0.95:
                            raise RuntimeError("Retry target cannot be reliably reacquired")
                        target = matches[0]
                    event("grasp", target.identity)
                    if self.robot.grasp(target):
                        picked = True
                        break
                if not picked:
                    self.pallet.release_unpicked(slot)
                    raise RuntimeError("Grasp retry budget exhausted")
                for state, operation in (("lift", self.robot.lift),
                                         ("transfer", lambda: self.robot.transfer(slot.pose)),
                                         ("place", lambda: self.robot.place(slot.pose))):
                    event(state, target.identity)
                    if not operation():
                        raise RuntimeError(state + " failed; load/slot requires reconciliation")
                event("verify", target.identity)
                observed = self.robot.inspect_placement(target.identity)
                if observed is None:
                    self.pallet.uncertain.add(slot.key)
                    raise RuntimeError("Placement observation unavailable")
                if not self.pallet.verify(slot, observed):
                    raise RuntimeError("Placement outside tolerance")
                done.add(target.identity)
                event("confirmed", target.identity)
            event("complete")
            status, reason = "complete", None
        except Exception as exc:
            status, reason = "stopped", str(exc)
            self.events.append({"state": "stopped", "reason": reason})
            try:
                self.robot.safe_stop()
            except Exception as stop_error:
                reason += "; safe_stop failed: " + str(stop_error)
        return {"status": status, "reason": reason, "completed_boxes": len(done),
                "events": self.events, "reserved_slots": len(self.pallet.reserved),
                "uncertain_slots": len(self.pallet.uncertain)}


class DryRunAdapter:
    """Synthetic fixtures: outputs must never count as physical validation."""
    def __init__(self, boxes, fail=None, placement_offset=0.0):
        self.boxes = {box.identity: box for box in boxes}
        self.held = None
        self.placed = {}
        self.fail = dict(fail or {})
        self.offset = number(placement_offset, "placement_offset")
        self.stopped = False

    def _ok(self, operation):
        remaining = self.fail.get(operation, 0)
        if remaining:
            self.fail[operation] = remaining - 1
            return False
        return True

    def observe(self):
        return [b for key, b in self.boxes.items() if key not in self.placed and key != self.held]

    def grasp(self, target):
        if self.held is not None:
            raise RuntimeError("Tool already holds a box")
        if not self._ok("grasp"):
            return False
        self.held = target.identity
        return True

    def lift(self):
        return self.held is not None and self._ok("lift")

    def transfer(self, box_center):
        return self.held is not None and self._ok("transfer")

    def place(self, box_center):
        if self.held is None or not self._ok("place"):
            return False
        self.placed[self.held] = Pose(box_center.x + self.offset, box_center.y, box_center.z, box_center.yaw)
        self.held = None
        return True

    def inspect_placement(self, identity):
        return self.placed.get(identity)

    def safe_stop(self):
        self.stopped = True
