from dataclasses import astuple, dataclass
from fractions import Fraction

from quality.calibration import rational


@dataclass(frozen=True)
class HeadRequest:
    rail_left: Fraction
    rail_right: Fraction
    width: Fraction
    lower: Fraction
    upper: Fraction


def validate_head_request(request):
    if not isinstance(request, HeadRequest):
        raise ValueError('expected a HeadRequest')
    left, right, width, lower, upper = (rational(value, 'head parameter') for value in astuple(request))
    if left > right:
        raise ValueError('rail endpoints are reversed')
    if width <= 0:
        raise ValueError('head width must be positive')
    if lower >= upper:
        raise ValueError('head vertical bounds must be strictly increasing')
    return HeadRequest(left, right, width, lower, upper)
