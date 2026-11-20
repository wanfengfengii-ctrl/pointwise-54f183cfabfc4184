from analysis.coverage import full_height_spans
from analysis.head import validate_head_request
from analysis.intervals import ClosedInterval, merge_closed_intervals


def qualify_head_positions(first_coverage, second_coverage, request):
    request = validate_head_request(request)
    if request.rail_right - request.rail_left < request.width:
        return ()
    polygons = first_coverage.polygons + second_coverage.polygons
    half_width = request.width / 2
    return merge_closed_intervals(
        ClosedInterval(span.left + half_width, span.right - half_width)
        for span in full_height_spans(polygons, request)
        if span.right - span.left >= request.width
    )
