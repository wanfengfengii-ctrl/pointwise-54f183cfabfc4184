from dataclasses import dataclass
from fractions import Fraction

from analysis.intervals import ClosedInterval
from quality.calibration import Point
from quality.footprints import Polygon


@dataclass(frozen=True)
class Edge:
    start: Point
    end: Point


def polygon_edges(polygon: Polygon) -> tuple[Edge, ...]:
    return tuple(Edge(start, polygon[(i + 1) % len(polygon)]) for i, start in enumerate(polygon))


def _difference(first, second):
    return first[0] - second[0], first[1] - second[1]


def _cross(first, second):
    return first[0] * second[1] - first[1] * second[0]


def _contains(edge, point):
    return (
        min(edge.start[0], edge.end[0]) <= point[0] <= max(edge.start[0], edge.end[0])
        and min(edge.start[1], edge.end[1]) <= point[1] <= max(edge.start[1], edge.end[1])
        and _cross(_difference(edge.end, edge.start), _difference(point, edge.start)) == 0
    )


def edge_intersection(first: Edge, second: Edge) -> tuple[Point, ...]:
    """Return an intersection point or the two ends of a shared segment."""
    direction = _difference(first.end, first.start)
    other_direction = _difference(second.end, second.start)
    offset = _difference(second.start, first.start)
    determinant = _cross(direction, other_direction)
    if determinant == 0:
        endpoints = {first.start, first.end, second.start, second.end}
        return tuple(sorted(point for point in endpoints if _contains(first, point) and _contains(second, point)))
    first_parameter = Fraction(_cross(offset, other_direction), determinant)
    second_parameter = Fraction(_cross(offset, direction), determinant)
    if 0 <= first_parameter <= 1 and 0 <= second_parameter <= 1:
        x = first.start[0] + first_parameter * direction[0]
        y = first.start[1] + first_parameter * direction[1]
        return ((x, y),)
    return ()


def vertical_section(polygon: Polygon, x: Fraction) -> ClosedInterval | None:
    """Return the closed section of one convex footprint at x."""
    hits = []
    for edge in polygon_edges(polygon):
        x0, y0 = edge.start
        x1, y1 = edge.end
        if not min(x0, x1) <= x <= max(x0, x1):
            continue
        if x0 == x1:
            hits.extend((y0, y1))
        else:
            hits.append(y0 + Fraction(x - x0, x1 - x0) * (y1 - y0))
    return ClosedInterval(min(hits), max(hits)) if hits else None
