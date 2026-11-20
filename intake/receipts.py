from dataclasses import dataclass

from intake.store import require_identifier


@dataclass(frozen=True)
class FreezeReceipt:
    receipt_id: str
    station_id: str
    batch_id: str
    revision_id: str
    frame_count: int


def insert_freeze_receipt(connection, revision):
    receipt = FreezeReceipt(
        f'freeze:{revision.revision_id}', revision.station_id, revision.batch_id,
        revision.revision_id, len(revision.frames),
    )
    connection.execute('''
        INSERT INTO freeze_receipts (receipt_id, revision_id, frame_count) VALUES (?, ?, ?)
    ''', (receipt.receipt_id, receipt.revision_id, receipt.frame_count))
    return receipt


def get_freeze_receipt(store, revision_id):
    revision_id = require_identifier(revision_id, 'revision identity')
    row = store.connection.execute('''
        SELECT f.receipt_id, r.batch_id, f.frame_count
        FROM freeze_receipts AS f JOIN revisions AS r USING (revision_id)
        WHERE f.revision_id = ?
    ''', (revision_id,)).fetchone()
    if row is None:
        raise LookupError(f'no freeze receipt for {revision_id}')
    receipt_id, batch_id, frame_count = row
    return FreezeReceipt(receipt_id, store.station_id, batch_id, revision_id, frame_count)
