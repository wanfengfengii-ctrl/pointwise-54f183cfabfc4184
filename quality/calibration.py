from dataclasses import astuple, dataclass
from fractions import Fraction


Point = tuple[Fraction, Fraction]


def rational(value, field='value'):
    if isinstance(value, bool) or not isinstance(value, (int, str, Fraction)):
        raise ValueError(f'{field} must be an exact rational')
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f'{field} must be an exact rational') from exc


@dataclass(frozen=True)
class AffineCalibration:
    a: Fraction
    b: Fraction
    c: Fraction
    d: Fraction
    e: Fraction
    f: Fraction


def validate_calibration(calibration):
    if not isinstance(calibration, AffineCalibration):
        raise ValueError('expected an AffineCalibration')
    a, b, c, d, e, f = (rational(value, 'calibration coefficient') for value in astuple(calibration))
    if a * e == b * d:
        raise ValueError('calibration must be invertible')
    return AffineCalibration(a, b, c, d, e, f)


def transform_vertex(calibration: AffineCalibration, point: Point) -> Point:
    """Map a local vertex with already validated coefficients."""
    x, y = point
    return (
        calibration.a * x + calibration.b * y + calibration.c,
        calibration.d * x + calibration.e * y + calibration.f,
    )
