"""Exact uncovered vertical gap of the joint coverage inside a head band."""
from itertools import combinations

from analysis.edges import Edge, edge_intersection, polygon_edges, vertical_section
from analysis.head import validate_head_request
from analysis.intervals import ClosedInterval, intersect_closed_intervals, merge_closed_intervals


def gap_profile(polygons, request):
    """Return ``(events, cells, band)`` describing the uncovered height.

    ``events`` are the rational abscissae at which the active edges change or
    the covered set jumps (polygon vertices, edge crossings, rail and band
    edges).  On each open interval ``(events[i], events[i+1])`` the covered
    section changes linearly, so the uncovered band height ``gap(x)`` is linear
    there as well; a vertical polygon edge only changes the closed boundary
    values, which contribute no area.  ``cells[i]`` stores the interior line
    ``gap(x) = slope*x + intercept`` valid strictly inside that interval.
    """
    request = validate_head_request(request)
    polygons = tuple(polygons)
    left, right = request.rail_left, request.rail_right
    band = ClosedInterval(request.lower, request.upper)
    band_height = request.upper - request.lower
    events = {left, right}
    edges = []
    for polygon in polygons:
        events.update(x for x, _ in polygon if left <= x <= right)
        edges.extend(polygon_edges(polygon))
    band_edges = [Edge((left, y), (right, y)) for y in (band.left, band.right)]
    for first, second in combinations(edges + band_edges, 2):
        events.update(x for x, _ in edge_intersection(first, second) if left <= x <= right)

    ordered_events = sorted(events)
    cells = []
    for start, end in zip(ordered_events, ordered_events[1:]):
        width = end - start
        sample_left = start + width / 3
        sample_right = start + 2 * width / 3
        gap_left = _gap_at(polygons, band, band_height, sample_left)
        gap_right = _gap_at(polygons, band, band_height, sample_right)
        slope = (gap_right - gap_left) / (sample_right - sample_left)
        intercept = gap_left - slope * sample_left
        cells.append({'start': start, 'end': end, 'slope': slope, 'intercept': intercept})
    return ordered_events, cells, band


def _covered_sections(polygons, band, x):
    sections = []
    for polygon in polygons:
        section = vertical_section(polygon, x)
        if section is not None:
            clipped = intersect_closed_intervals(section, band)
            if clipped is not None:
                sections.append(clipped)
    return merge_closed_intervals(sections)


def _gap_at(polygons, band, band_height, x):
    covered_length = sum(
        (section.right - section.left for section in _covered_sections(polygons, band, x)),
        start=band_height - band_height,
    )
    gap = band_height - covered_length
    if gap < 0:
        raise ValueError('coverage exceeds the requested band')
    return gap


def cell_index(events, x):
    for index, (start, end) in enumerate(zip(events, events[1:])):
        if start <= x <= end:
            return index
    raise ValueError('abscissa outside the event profile')
