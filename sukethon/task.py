"""SI-unit pallet geometry and transactional occupancy; no simulator access."""
from dataclasses import dataclass
import math

def number(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + " must be finite")
    if positive and value <= 0:
        raise ValueError(label + " must be positive")
    return float(value)


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    z: float
    yaw: float = 0.0

    def __post_init__(self):
        for key in ("x", "y", "z", "yaw"):
            number(getattr(self, key), key)


@dataclass(frozen=True)
class BoxSpec:
    kind: str
    length: float
    width: float
    height: float
    max_mass: float

    def __post_init__(self):
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("Box kind is required")
        for key in ("length", "width", "height", "max_mass"):
            number(getattr(self, key), key, positive=True)


BOXES = {"A": BoxSpec("A", 0.6, 0.4, 0.28, 10.0),
         "B": BoxSpec("B", 0.4, 0.3, 0.23, 6.0)}


@dataclass(frozen=True)
class Zone:
    kind: str
    origin: Pose  # Center of footprint; z is support surface height.
    extent_x: float
    extent_y: float
    gap: float = 0.02

    def __post_init__(self):
        if self.kind not in BOXES:
            raise ValueError("Unknown zone kind")
        number(self.extent_x, "extent_x", True)
        number(self.extent_y, "extent_y", True)
        if number(self.gap, "gap") < 0:
            raise ValueError("Gap must be nonnegative")
        spec = BOXES[self.kind]
        if self.extent_x < 2 * spec.length + self.gap or self.extent_y < 2 * spec.width + self.gap:
            raise ValueError("Zone cannot contain the 2x2 footprint")


@dataclass(frozen=True)
class Slot:
    kind: str
    layer: int
    row: int
    column: int
    pose: Pose  # Box center, not tool pose.

    @property
    def key(self):
        return (self.kind, self.layer, self.row, self.column)


class Pallet:
    def __init__(self, zones, slots_per_layer=4):
        if slots_per_layer not in (2, 4):
            raise ValueError('Slots per layer must be 2 or 4')
        self.rows = slots_per_layer // 2
        self.zones = {zone.kind: zone for zone in zones}
        if len(zones) != 2 or set(self.zones) != set(BOXES):
            raise ValueError("Exactly one A zone and one B zone required")
        self.slots = {}
        self.reserved = {}  # Slot key -> box identity
        self.confirmed = {}
        self.uncertain = set()
        for kind, zone in self.zones.items():
            spec = BOXES[kind]
            c, s = math.cos(zone.origin.yaw), math.sin(zone.origin.yaw)
            for layer in range(2):
                for row in range(self.rows):
                    for column in range(2):
                        x = (column - 0.5) * (spec.length + zone.gap)
                        y = (row - (self.rows - 1)/2) * (spec.width + zone.gap)
                        pose = Pose(zone.origin.x + c*x - s*y, zone.origin.y + s*x + c*y,
                                    zone.origin.z + (layer + 0.5)*spec.height, zone.origin.yaw)
                        slot = Slot(kind, layer, row, column, pose)
                        self.slots[slot.key] = slot

    def reserve(self, kind, box_id):
        if kind not in BOXES or not isinstance(box_id, str) or not box_id:
            raise ValueError("Valid kind and box identity required")
        if box_id in self.reserved.values() or box_id in self.confirmed.values():
            raise ValueError("Box already allocated")
        for key, slot in self.slots.items():
            if slot.kind != kind or key in self.reserved or key in self.confirmed:
                continue
            # Conservative: complete the entire lower layer before opening the upper.
            if slot.layer and any((kind, 0, r, c) not in self.confirmed for r in range(self.rows) for c in range(2)):
                continue
            self.reserved[key] = box_id
            return slot
        raise RuntimeError("No supported free slot for " + kind)

    def release_unpicked(self, slot):
        if slot.key in self.uncertain:
            raise RuntimeError("Cannot free an uncertain placement")
        del self.reserved[slot.key]

    def verify(self, slot, observed, center_tolerance=0.01, yaw_tolerance=math.radians(5)):
        if slot.key not in self.reserved or self.slots.get(slot.key) != slot:
            raise ValueError("Slot is not reserved")
        number(center_tolerance, "center_tolerance", True)
        number(yaw_tolerance, "yaw_tolerance", True)
        error = math.sqrt(sum((getattr(slot.pose, a)-getattr(observed, a))**2 for a in ("x", "y", "z")))
        yaw_error = abs(math.atan2(math.sin(observed.yaw-slot.pose.yaw), math.cos(observed.yaw-slot.pose.yaw)))
        if error > center_tolerance + 1e-12 or yaw_error > yaw_tolerance + 1e-12:
            self.uncertain.add(slot.key)
            return False
        if slot.key in self.uncertain:
            raise RuntimeError("Uncertain slot requires explicit reconciliation")
        self.confirmed[slot.key] = self.reserved.pop(slot.key)
        return True


def load_layout(config):
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported task schema")
    count = config.get("expected_boxes")
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 16:
        raise ValueError("expected_boxes must be an integer in [1, 16]")
    zones = [Zone(z["kind"], Pose(**z["origin"]), z["extent_x"], z["extent_y"], z.get("gap", 0.02))
             for z in config["zones"]]
    return Pallet(zones), count
