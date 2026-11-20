from itertools import combinations, pairwise

from analysis.edges import Edge, edge_intersection, polygon_edges, vertical_section
from analysis.intervals import ClosedInterval, intersect_closed_intervals, merge_closed_intervals


def full_height_spans(polygons, request):
    """Find the closed rail spans where the joint footprint fills the band."""
    polygons = tuple(polygons)
    left, right = request.rail_left, request.rail_right
    band = ClosedInterval(request.lower, request.upper)
    events = {left, right}
    edges = []
    for polygon in polygons:
        events.update(x for x, _ in polygon if left <= x <= right)
        edges.extend(polygon_edges(polygon))
    edges.extend(Edge((left, y), (right, y)) for y in (band.left, band.right))
    for first, second in combinations(edges, 2):
        events.update(x for x, _ in edge_intersection(first, second) if left <= x <= right)

    def fills_band(x):
        clipped_sections = []
        for polygon in polygons:
            section = vertical_section(polygon, x)
            if section is not None:
                clipped = intersect_closed_intervals(section, band)
                if clipped is not None:
                    clipped_sections.append(clipped)
        return merge_closed_intervals(clipped_sections) == (band,)

    sorted_events = sorted(events)
    spans = [ClosedInterval(x, x) for x in sorted_events if fills_band(x)]
    for start, end in pairwise(sorted_events):
        # Between events the active edges and their vertical ordering are fixed.
        # The filled set is closed because the finite union of footprints is closed.
        if fills_band((start + end) / 2):
            spans.append(ClosedInterval(start, end))
    return merge_closed_intervals(spans)
