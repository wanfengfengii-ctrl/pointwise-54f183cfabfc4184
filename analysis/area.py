"""Area-budget head qualification with exact piecewise quadratic solving."""
from fractions import Fraction
from math import isqrt

from analysis.endpoints import (
    ExactInterval,
    QuadraticEndpoint,
    compare_endpoints,
    max_endpoint,
    merge_exact_intervals,
    min_endpoint,
)
from analysis.gaps import cell_index, gap_profile
from analysis.head import validate_head_request
from analysis.positions import qualify_head_positions
from quality.calibration import rational


def validate_budget(budget):
    value = rational(budget, 'area budget')
    if value < 0:
        raise ValueError('area budget must be non-negative')
    return value


def area_budget_positions(first_coverage, second_coverage, request, budget):
    """Centers whose whole-head rectangle has uncovered area at most ``budget``."""
    request = validate_head_request(request)
    budget = validate_budget(budget)
    if request.rail_right - request.rail_left < request.width:
        return ()
    if budget == 0:
        # Zero tolerance is exactly the V1 full-coverage qualification.
        return _rational_exact_intervals(
            qualify_head_positions(first_coverage, second_coverage, request)
        )
    profile = _prepare(first_coverage, second_coverage, request)
    events, antiderivative, half_width = profile
    centers = sorted({
        event - half_width for event in events
        if request.rail_left + half_width <= event <= request.rail_right - half_width
    })
    lower_center = request.rail_left + half_width
    upper_center = request.rail_right - half_width
    intervals = []
    for cell_left, cell_right in _center_cells(lower_center, upper_center, centers):
        alpha, beta, gamma = _area_polynomial(
            antiderivative, events, cell_left, cell_right, half_width
        )
        intervals.extend(_solve_cell(cell_left, cell_right, alpha, beta, gamma - budget))
    return merge_exact_intervals(intervals)


def _prepare(first_coverage, second_coverage, request):
    polygons = first_coverage.polygons + second_coverage.polygons
    events, cells, _ = gap_profile(polygons, request)
    return events, _build_antiderivative(events, cells), request.width / 2


def _rational_exact_intervals(intervals):
    return tuple(ExactInterval(interval.left, interval.right) for interval in intervals)


def _center_cells(lower_center, upper_center, centers):
    bounds = [lower_center, *centers, upper_center]
    return [(left, right) for left, right in zip(bounds, bounds[1:]) if left <= right]


def _build_antiderivative(events, cells):
    """Piecewise antiderivative G(x) with G(events[0]) = 0.

    Each segment stores ``(start, end, slope, intercept, base)``.  The gap
    follows the linear function ``slope*x + intercept`` on the open cell and
    the stored boundary values at the closed ends; ``base`` is the cumulative
    integral through ``start``.  A vertical edge only changes the boundary
    values (zero-width jumps contribute no area), so the interior line integral
    is the exact contribution of every cell.
    """
    segments = []
    accumulated = Fraction(0)
    for index, cell in enumerate(cells):
        start, end = events[index], events[index + 1]
        slope, intercept = cell['slope'], cell['intercept']
        segments.append((start, end, slope, intercept, accumulated))
        accumulated += slope * (end * end - start * start) / 2 + intercept * (end - start)
    return segments


def _integral_to(antiderivative, events, cells, x):
    """Evaluate the piecewise antiderivative at rational ``x``."""
    index = cell_index(events, x)
    start, end, slope, intercept, base = antiderivative[index]
    if x == end and index < len(cells) - 1:
        # Honor any boundary jump by reading the next segment's accumulated base.
        return antiderivative[index + 1][4]
    if x == start:
        return base
    return base + slope * (x * x - start * start) / 2 + intercept * (x - start)


def _area_polynomial(antiderivative, events, cell_left, cell_right, half_width):
    """Coefficients ``(alpha, beta, gamma)`` of A(c) = alpha*c^2 + beta*c + gamma.

    On one center cell neither window crosses a gap breakpoint, so each side
    expands from a single antiderivative segment.
    """
    left_window = cell_left - half_width
    right_window = cell_right + half_width
    left_segment = antiderivative[cell_index(events, left_window)]
    right_segment = antiderivative[cell_index(events, right_window)]

    def coefficients(segment, shift, sign):
        start, _, slope, intercept, base = segment
        # G(c + shift) = A*c^2 + B*c + C inside this fixed segment.
        a = slope / 2
        b = slope * shift + intercept
        c = base + slope * (shift * shift - start * start) / 2 + intercept * (shift - start)
        return sign * a, sign * b, sign * c

    left_a, left_b, left_c = coefficients(left_segment, -half_width, -1)
    right_a, right_b, right_c = coefficients(right_segment, half_width, 1)
    return left_a + right_a, left_b + right_b, left_c + right_c


def _solve_cell(cell_left, cell_right, alpha, beta, gamma):
    """Solve alpha*c^2 + beta*c + gamma <= 0 on the closed rational cell."""
    if alpha == 0:
        if beta == 0:
            return [ExactInterval(cell_left, cell_right)] if gamma <= 0 else []
        root = -gamma / beta
        qualifying = [(_minus_infinity(), root)] if beta > 0 else [(root, _plus_infinity())]
    else:
        discriminant = beta * beta - 4 * alpha * gamma
        if discriminant < 0:
            return [ExactInterval(cell_left, cell_right)] if alpha < 0 else []
        if discriminant == 0:
            root = -beta / (2 * alpha)
            qualifying = [(_minus_infinity(), _plus_infinity())] if alpha < 0 else [(root, root)]
        else:
            root_left, root_right = _discriminant_roots(alpha, beta, discriminant)
            qualifying = (
                [(root_left, root_right)] if alpha > 0
                else [(_minus_infinity(), root_left), (root_right, _plus_infinity())]
            )
    return [
        clipped
        for lo, hi in qualifying
        if (clipped := _clip_qualifying(lo, hi, cell_left, cell_right)) is not None
    ]


def _discriminant_roots(alpha, beta, discriminant):
    square = _perfect_square(discriminant)
    if square is not None:
        base = -beta / (2 * alpha)
        delta = square / (2 * alpha)
        roots = [base - delta, base + delta]
        return min(roots), max(roots)
    # sqrt(discriminant) as sqrt_scale * sqrt(radicand), radicand square-free:
    # sqrt(p/q) = num_factor / (den_factor * den_free) * sqrt(num_free * den_free).
    num_free, num_factor = _square_free_integer(discriminant.numerator)
    den_free, den_factor = _square_free_integer(discriminant.denominator)
    radicand = num_free * den_free
    sqrt_scale = Fraction(num_factor, den_factor * den_free)
    scale = sqrt_scale / (2 * alpha)
    offset = -beta / (2 * alpha)
    root_left = QuadraticEndpoint(offset, scale, radicand)
    root_right = QuadraticEndpoint(offset, -scale, radicand)
    if compare_endpoints(root_left, root_right) <= 0:
        return root_left, root_right
    return root_right, root_left


def _square_free_integer(value):
    remaining = value
    factor = 1
    prime = 2
    while prime * prime <= remaining:
        while remaining % (prime * prime) == 0:
            remaining //= prime * prime
            factor *= prime
        prime += 1 if prime == 2 else 2
    return remaining, factor


def _perfect_square(value):
    if value < 0:
        return None
    numerator = isqrt(value.numerator)
    denominator = isqrt(value.denominator)
    if numerator * numerator == value.numerator and denominator * denominator == value.denominator:
        return Fraction(numerator, denominator)
    return None


class _Infinite:
    def __init__(self, negative):
        self.negative = negative


def _minus_infinity():
    return _Infinite(True)


def _plus_infinity():
    return _Infinite(False)


def _clip_qualifying(lo, hi, cell_left, cell_right):
    if isinstance(lo, _Infinite):
        left = cell_left
    else:
        if compare_endpoints(lo, cell_right) > 0:
            return None
        left = max_endpoint(cell_left, lo)
    if isinstance(hi, _Infinite):
        right = cell_right
    else:
        if compare_endpoints(hi, cell_left) < 0:
            return None
        right = min_endpoint(cell_right, hi)
    if compare_endpoints(left, right) > 0:
        return None
    return ExactInterval(left, right)


def missed_area(first_coverage, second_coverage, request, center):
    """Exact uncovered area of the head rectangle centered at a rational center."""
    request = validate_head_request(request)
    center = rational(center, 'head center')
    half_width = request.width / 2
    head_left = center - half_width
    head_right = center + half_width
    if not (request.rail_left <= head_left and head_right <= request.rail_right):
        raise ValueError('head center does not fit inside the closed rail')
    polygons = first_coverage.polygons + second_coverage.polygons
    events, cells, _ = gap_profile(polygons, request)
    antiderivative = _build_antiderivative(events, cells)
    return (
        _integral_to(antiderivative, events, cells, head_right)
        - _integral_to(antiderivative, events, cells, head_left)
    )
