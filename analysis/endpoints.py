"""Exact one-dimensional endpoints and closed intervals for area budgets.

Endpoints are either a rational :class:`~fractions.Fraction` or a quadratic
irrational ``offset + scale * sqrt(radicand)`` with a positive square-free
integer radicand.  Every comparison and every JSON encoding stays exact; no
floating point arithmetic is used anywhere in this module.
"""
from dataclasses import dataclass
from fractions import Fraction
from functools import cmp_to_key
from math import isqrt

from quality.calibration import rational


class QuadraticEndpoint:
    """Exact value ``offset + scale * sqrt(radicand)`` (``scale`` nonzero)."""

    __slots__ = ('offset', 'scale', 'radicand')

    def __init__(self, offset, scale, radicand):
        offset = rational(offset, 'irrational offset')
        scale = rational(scale, 'irrational scale')
        if scale == 0:
            raise ValueError('irrational scale must be non-zero')
        if isinstance(radicand, bool) or not isinstance(radicand, int) or radicand <= 0:
            raise ValueError('radicand must be a positive integer')
        square_free, remainder = square_free_part(radicand)
        if square_free == 1:
            raise ValueError('radicand must not be a rational square')
        if remainder != 1:
            # sqrt(r) = remainder * sqrt(square_free); fold the factor into scale.
            scale = scale * remainder
        object.__setattr__(self, 'offset', offset)
        object.__setattr__(self, 'scale', scale)
        object.__setattr__(self, 'radicand', square_free)

    def __setattr__(self, name, value):
        raise AttributeError('QuadraticEndpoint is immutable')

    def __eq__(self, other):
        if isinstance(other, QuadraticEndpoint):
            return (
                self.offset == other.offset
                and self.scale == other.scale
                and self.radicand == other.radicand
            )
        return NotImplemented

    def __hash__(self):
        return hash((QuadraticEndpoint, self.offset, self.scale, self.radicand))

    def __repr__(self):
        return f'QuadraticEndpoint({self.offset!r}, {self.scale!r}, {self.radicand})'

    def to_json(self):
        return {
            'offset': str(self.offset),
            'scale': str(self.scale),
            'radicand': str(self.radicand),
        }

    @classmethod
    def from_json(cls, body):
        if not isinstance(body, dict) or body.keys() != {'offset', 'scale', 'radicand'}:
            raise ValueError('invalid irrational endpoint fields')
        try:
            endpoint = cls(body['offset'], body['scale'], int(body['radicand']))
        except ValueError as exc:
            raise ValueError('invalid irrational endpoint') from exc
        if str(endpoint.radicand) != body['radicand']:
            raise ValueError('radicand must be square-free')
        return endpoint


def square_free_part(value):
    """Return ``(square_free, square_factor)`` with ``value = square_free * factor^2``."""
    remaining = value
    factor = 1
    prime = 2
    while prime * prime <= remaining:
        while remaining % (prime * prime) == 0:
            remaining //= prime * prime
            factor *= prime
        prime += 1 if prime == 2 else 2
    return remaining, factor


def _surd_sign(endpoint):
    """Exact sign of an irrational endpoint (it is never zero)."""
    if endpoint.offset == 0:
        return 1 if endpoint.scale > 0 else -1
    root = endpoint.radicand
    a, b = endpoint.offset, endpoint.scale
    if b > 0:
        # a + b*sqrt(r); zero would require a < 0 and a^2 = b^2 r (impossible: r not a square).
        if a >= 0:
            return 1
        return 1 if b * b * root > a * a else -1
    if a <= 0:
        return -1
    # a > 0, b < 0: sign of a - |b|sqrt(r).
    return 1 if a * a > b * b * root else -1


def _bracket(endpoint, precision):
    """Rational brackets [lo, hi] around the endpoint with the given denominator."""
    root = isqrt(endpoint.radicand * precision * precision)
    scaled = endpoint.offset * precision + endpoint.scale * root
    lo = Fraction(scaled, precision)
    hi = Fraction(scaled + 1, precision)
    if endpoint.scale < 0:
        lo, hi = Fraction(scaled - 1, precision), Fraction(scaled, precision)
    return lo, hi


def compare_endpoints(left, right):
    """Exact three-way comparison for rationals and quadratic irrationals."""
    if isinstance(left, Fraction) and isinstance(right, Fraction):
        return (left > right) - (left < right)
    if isinstance(left, Fraction):
        return -_surd_sign(QuadraticEndpoint(right.offset - left, right.scale, right.radicand))
    if isinstance(right, Fraction):
        return _surd_sign(QuadraticEndpoint(left.offset - right, left.scale, left.radicand))
    if left.radicand == right.radicand:
        scale = left.scale - right.scale
        offset = left.offset - right.offset
        if scale == 0:
            return (offset > 0) - (offset < 0)
        return _surd_sign(QuadraticEndpoint(offset, scale, left.radicand))
    # Distinct radicands can never be equal; separate them with tightening rational brackets.
    precision = 1
    while True:
        left_lo, left_hi = _bracket(left, precision)
        right_lo, right_hi = _bracket(right, precision)
        if left_hi < right_lo:
            return -1
        if right_hi < left_lo:
            return 1
        precision *= 16


def endpoints_equal(left, right):
    return compare_endpoints(left, right) == 0


@dataclass(frozen=True)
class ExactInterval:
    """A closed interval whose endpoints may be rational or exactly irrational."""

    left: object
    right: object

    def __post_init__(self):
        left = _validate_endpoint(self.left, 'interval left endpoint')
        right = _validate_endpoint(self.right, 'interval right endpoint')
        if compare_endpoints(left, right) > 0:
            raise ValueError('interval endpoints are reversed')
        object.__setattr__(self, 'left', left)
        object.__setattr__(self, 'right', right)


def _validate_endpoint(value, field):
    if isinstance(value, Fraction):
        return value
    if isinstance(value, QuadraticEndpoint):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Fraction(value)
    raise ValueError(f'{field} must be an exact rational or quadratic endpoint')


def min_endpoint(left, right):
    return left if compare_endpoints(left, right) <= 0 else right


def max_endpoint(left, right):
    return left if compare_endpoints(left, right) >= 0 else right


def merge_exact_intervals(intervals):
    """Sort by the left endpoint and merge overlapping and touching closed intervals."""
    ordered = sorted(intervals, key=cmp_to_key(_compare_intervals))
    merged = []
    for interval in ordered:
        if merged and compare_endpoints(interval.left, merged[-1].right) <= 0:
            previous = merged[-1]
            merged[-1] = ExactInterval(previous.left, max_endpoint(previous.right, interval.right))
        else:
            merged.append(interval)
    return tuple(merged)


def _compare_intervals(left, right):
    return compare_endpoints(left.left, right.left)


def encode_endpoint(endpoint):
    if isinstance(endpoint, Fraction):
        return str(endpoint)
    return endpoint.to_json()


def decode_endpoint(body):
    if isinstance(body, str):
        return rational(body, 'interval endpoint')
    return QuadraticEndpoint.from_json(body)


def encode_exact_positions(positions):
    return [[encode_endpoint(interval.left), encode_endpoint(interval.right)] for interval in positions]


def decode_exact_positions(body):
    if not isinstance(body, list):
        raise ValueError('positions must be a sequence')
    return tuple(
        ExactInterval(decode_endpoint(left), decode_endpoint(right)) for left, right in body
    )
