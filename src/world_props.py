"""Static roadside props, shared by physics and display."""

from dataclasses import dataclass

from coastal_map import map_length, nearest_point, offset_point, point_at
from tracks import COASTAL_CIRCUIT


@dataclass(frozen=True)
class Prop:
    kind: str
    x: float
    y: float
    scale: float
    heading: float


def collision_box(prop):
    """Half extents and centre height, measured from the displayed model origin."""
    half, height = {
        "tree": ((0.09, 0.09, 0.65), 0.65),
        "rock": ((0.39, 0.50, 0.13), 0.08),
        "checkpoint": ((0.12, 0.12, 1.7), 1.7),
        "checkpoint-beam": ((5.52, 0.12, 0.12), 3.35),
    }[prop.kind]
    return tuple(value * prop.scale for value in half), height * prop.scale


def props_for(track):
    props = []
    if track == "coastal":
        for i in range(72):
            x, y, _ = offset_point(point_at(i * map_length() / 72), -11 - (i % 4) * 6)
            scale = 2.8 + (i % 3) * 0.55
            if nearest_point(x, y)[1] > 7 + scale * 0.21:
                props.append(Prop("tree", x, y, scale, i * 73))
        for i in range(32):
            p = point_at(i * map_length() / 32 + 4)
            x, y, _ = offset_point(p, 8.5)
            props.append(Prop("rock", x, y, 1 + (i % 3) * 0.4, i * 47))
        for distance in COASTAL_CIRCUIT.checkpoints:
            p = point_at(distance)
            for side in (-1, 1):
                x, y, _ = offset_point(p, side * 5.4)
                props.append(Prop("checkpoint", x, y, 1, p.heading))
            props.append(Prop("checkpoint-beam", p.x, p.y, 1, p.heading))
    elif track == "highway":
        for i in range(48):
            props.append(
                Prop(
                    "tree",
                    (-1 if i % 2 else 1) * (20 + (i % 3) * 12),
                    20 + (i // 2) * 55,
                    2.2 + (i % 3) * 0.4,
                    i * 53,
                )
            )
    return tuple(props)
