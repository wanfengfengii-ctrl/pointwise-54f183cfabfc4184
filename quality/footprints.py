from quality.calibration import Point, rational, transform_vertex


Polygon = tuple[Point, ...]


def _side(start, end, point):
    return (end[0] - start[0]) * (point[1] - start[1]) - (end[1] - start[1]) * (point[0] - start[0])


def canonical_polygon(vertices) -> Polygon:
    """Normalize a strictly convex perimeter to CCW from its least vertex."""
    if not isinstance(vertices, (list, tuple)) or len(vertices) < 3:
        raise ValueError('a polygon needs at least three vertices')
    points = []
    for vertex in vertices:
        if not isinstance(vertex, (list, tuple)) or len(vertex) != 2:
            raise ValueError('each vertex must contain two coordinates')
        points.append((rational(vertex[0], 'vertex x'), rational(vertex[1], 'vertex y')))
    if len(set(points)) != len(points):
        raise ValueError('polygon vertices must be distinct')
    direction = _side(points[0], points[1], points[2])
    if direction < 0:
        points.reverse()
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        if any(_side(start, end, point) <= 0 for point in points if point != start and point != end):
            raise ValueError('expected a strictly convex polygon in perimeter order')
    first = points.index(min(points))
    return tuple(points[first:] + points[:first])


def validate_quadrilateral(vertices) -> Polygon:
    if not isinstance(vertices, (tuple, list)) or len(vertices) != 4:
        raise ValueError('a scan footprint must have four vertices')
    return canonical_polygon(vertices)


def transform_footprint(calibration, footprint) -> Polygon:
    return canonical_polygon(tuple(transform_vertex(calibration, point) for point in footprint))
