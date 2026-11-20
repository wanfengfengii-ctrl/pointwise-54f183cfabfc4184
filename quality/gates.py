from dataclasses import dataclass
from fractions import Fraction

from quality.calibration import rational


@dataclass(frozen=True)
class QualityRule:
    lower: Fraction
    upper: Fraction


def validate_quality_rule(rule):
    if not isinstance(rule, QualityRule):
        raise ValueError('expected a QualityRule')
    lower = rational(rule.lower, 'minimum quality reading')
    upper = rational(rule.upper, 'maximum quality reading')
    if lower > upper:
        raise ValueError('quality bounds are reversed')
    return QualityRule(lower, upper)


def passes_quality_gate(rule, reading):
    """Evaluate a normalized reading against the frozen inclusive gate."""
    return rule.lower <= reading <= rule.upper
