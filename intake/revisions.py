import json
from dataclasses import astuple, dataclass

from intake.frames import ScanFrame, freeze_frame_sequence
from intake.store import require_identifier
from quality.calibration import AffineCalibration, validate_calibration
from quality.gates import QualityRule, validate_quality_rule


@dataclass(frozen=True)
class FrozenRevision:
    station_id: str
    batch_id: str
    revision_id: str
    domain: str
    calibration: AffineCalibration
    quality_rule: QualityRule
    frames: tuple[ScanFrame, ...]


def insert_revision(connection, revision):
    existing = connection.execute(
        'SELECT 1 FROM revisions WHERE revision_id = ?', (revision.revision_id,)
    ).fetchone()
    if existing is not None:
        raise ValueError(f'revision already exists: {revision.revision_id}')
    frames = [
        [frame.frame_id, [[str(x), str(y)] for x, y in frame.footprint], str(frame.reading)]
        for frame in revision.frames
    ]
    connection.execute('''
        INSERT INTO revisions (revision_id, batch_id, domain, calibration, quality_rule, frames)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        revision.revision_id,
        revision.batch_id,
        revision.domain,
        json.dumps([str(value) for value in astuple(revision.calibration)]),
        json.dumps([str(value) for value in astuple(revision.quality_rule)]),
        json.dumps(frames),
    ))


def get_revision(store, revision_id):
    revision_id = require_identifier(revision_id, 'revision identity')
    row = store.connection.execute('''
        SELECT batch_id, domain, calibration, quality_rule, frames
        FROM revisions WHERE revision_id = ?
    ''', (revision_id,)).fetchone()
    if row is None:
        raise LookupError(f'unknown revision {revision_id}')
    batch_id, domain, calibration, rule, frames = row
    return FrozenRevision(
        store.station_id, batch_id, revision_id, domain,
        validate_calibration(AffineCalibration(*json.loads(calibration))),
        validate_quality_rule(QualityRule(*json.loads(rule))),
        freeze_frame_sequence(ScanFrame(*saved) for saved in json.loads(frames)),
    )
