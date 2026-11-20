from dataclasses import dataclass
from fractions import Fraction

from quality.calibration import rational


@dataclass(frozen=True, order=True)
class ClosedInterval:
    left: Fraction
    right: Fraction

    def __post_init__(self):
        left = rational(self.left, 'interval left endpoint')
        right = rational(self.right, 'interval right endpoint')
        if left > right:
            raise ValueError('interval endpoints are reversed')
        object.__setattr__(self, 'left', left)
        object.__setattr__(self, 'right', right)


def intersect_closed_intervals(first, second):
    left = max(first.left, second.left)
    right = min(first.right, second.right)
    return ClosedInterval(left, right) if left <= right else None


def merge_closed_intervals(intervals):
    merged = []
    for interval in sorted(intervals):
        if merged and interval.left <= merged[-1].right:
            previous = merged[-1]
            merged[-1] = ClosedInterval(previous.left, max(previous.right, interval.right))
        else:
            merged.append(interval)
    return tuple(merged)
