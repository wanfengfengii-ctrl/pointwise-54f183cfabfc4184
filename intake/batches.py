from intake.frames import freeze_frame_sequence
from intake.receipts import insert_freeze_receipt
from intake.revisions import FrozenRevision, insert_revision
from intake.store import require_identifier
from quality.calibration import validate_calibration
from quality.gates import validate_quality_rule


def register_batch(store, batch_id, label):
    batch_id = require_identifier(batch_id, 'batch identity')
    if not isinstance(label, str) or not label.strip():
        raise ValueError('batch label must contain text')
    with store.write_transaction() as connection:
        connection.execute('''
            INSERT INTO batches (batch_id, label) VALUES (?, ?)
            ON CONFLICT(batch_id) DO UPDATE SET label = excluded.label
        ''', (batch_id, label))
    return label


def get_batch_label(store, batch_id):
    batch_id = require_identifier(batch_id, 'batch identity')
    row = store.connection.execute('SELECT label FROM batches WHERE batch_id = ?', (batch_id,)).fetchone()
    if row is None:
        raise LookupError(f'unknown batch {batch_id}')
    return row[0]


def freeze_batch(store, batch_id, revision_id, frames, calibration, quality_rule, domain):
    revision = FrozenRevision(
        station_id=store.station_id,
        batch_id=require_identifier(batch_id, 'batch identity'),
        revision_id=require_identifier(revision_id, 'revision identity'),
        domain=require_identifier(domain, 'coordinate domain'),
        calibration=validate_calibration(calibration),
        quality_rule=validate_quality_rule(quality_rule),
        frames=freeze_frame_sequence(frames),
    )
    with store.write_transaction() as connection:
        connection.execute('''
            INSERT INTO batches (batch_id, label) VALUES (?, ?)
            ON CONFLICT(batch_id) DO NOTHING
        ''', (revision.batch_id, revision.batch_id))
        insert_revision(connection, revision)
        receipt = insert_freeze_receipt(connection, revision)
    return revision, receipt
