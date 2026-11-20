from dataclasses import dataclass
from fractions import Fraction

from intake.store import require_identifier
from quality.calibration import rational
from quality.footprints import Polygon, validate_quadrilateral


@dataclass(frozen=True)
class ScanFrame:
    frame_id: str
    footprint: Polygon
    reading: Fraction


def freeze_frame_sequence(frames):
    try:
        incoming = iter(frames)
    except TypeError as exc:
        raise ValueError('scan frames must be an iterable of ScanFrame') from exc
    frozen = []
    seen = set()
    for frame in incoming:
        if not isinstance(frame, ScanFrame):
            raise ValueError('expected a ScanFrame')
        frame_id = require_identifier(frame.frame_id, 'frame identity')
        if frame_id in seen:
            raise ValueError(f'duplicate frame identity {frame_id}')
        seen.add(frame_id)
        frozen.append(ScanFrame(
            frame_id,
            validate_quadrilateral(frame.footprint),
            rational(frame.reading, 'quality reading'),
        ))
    return tuple(frozen)
