from dataclasses import dataclass

from intake.revisions import FrozenRevision
from quality.calibration import validate_calibration
from quality.footprints import Polygon, transform_footprint
from quality.gates import passes_quality_gate, validate_quality_rule


@dataclass(frozen=True)
class FrameDisposition:
    ordinal: int
    frame_id: str
    accepted: bool
    footprint: Polygon | None


def evaluate_revision(revision: FrozenRevision) -> tuple[FrameDisposition, ...]:
    calibration = validate_calibration(revision.calibration)
    rule = validate_quality_rule(revision.quality_rule)
    dispositions = []
    for ordinal, frame in enumerate(revision.frames, start=1):
        accepted = passes_quality_gate(rule, frame.reading)
        footprint = transform_footprint(calibration, frame.footprint) if accepted else None
        dispositions.append(FrameDisposition(ordinal, frame.frame_id, accepted, footprint))
    return tuple(dispositions)
