from evidence.envelope import seal_envelope
from evidence.payload import CoveragePayload, encode_coverage
from intake.revisions import get_revision
from quality.disposition import evaluate_revision


def issue_piece(store, revision_id):
    revision = get_revision(store, revision_id)
    dispositions = evaluate_revision(revision)
    footprints = tuple(item.footprint for item in dispositions if item.footprint is not None)
    payload = encode_coverage(CoveragePayload(footprints))
    return seal_envelope(
        revision.station_id, revision.batch_id, revision.revision_id, revision.domain, payload,
    )
