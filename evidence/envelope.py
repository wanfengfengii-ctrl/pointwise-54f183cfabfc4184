import hashlib
import json
from dataclasses import asdict, dataclass
from hmac import compare_digest


def _canonical(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'))


def _digest(fields):
    return hashlib.sha256(_canonical(fields).encode('ascii')).hexdigest()


@dataclass(frozen=True)
class PieceEnvelope:
    version: int
    station_id: str
    batch_id: str
    revision_id: str
    domain: str
    unit: str
    payload: str
    piece_id: str

    def to_json(self):
        return _canonical(asdict(self))

    @classmethod
    def from_json(cls, text):
        def unique_fields(pairs):
            fields = dict(pairs)
            if len(fields) != len(pairs):
                raise ValueError('duplicate envelope field')
            return fields

        try:
            fields = json.loads(text, object_pairs_hook=unique_fields)
            envelope = cls(**fields)
        except (ValueError, TypeError) as exc:
            raise ValueError('malformed piece envelope') from exc
        return verify_envelope(envelope)


def seal_envelope(station_id, batch_id, revision_id, domain, payload):
    fields = {
        'version': 1,
        'station_id': station_id,
        'batch_id': batch_id,
        'revision_id': revision_id,
        'domain': domain,
        'unit': 'mm',
        'payload': payload,
    }
    return verify_envelope(PieceEnvelope(**fields, piece_id=_digest(fields)))


def verify_envelope(envelope):
    if not isinstance(envelope, PieceEnvelope):
        raise ValueError('expected a PieceEnvelope')
    if type(envelope.version) is not int or envelope.version != 1 or envelope.unit != 'mm':
        raise ValueError('unsupported piece envelope version or unit')
    for field in ('station_id', 'batch_id', 'revision_id', 'domain'):
        value = getattr(envelope, field)
        if not isinstance(value, str) or not value or value.strip() != value:
            raise ValueError(f'invalid envelope {field}')
    if not isinstance(envelope.payload, str):
        raise ValueError('piece payload must be JSON text')
    fields = asdict(envelope)
    piece_id = fields.pop('piece_id')
    if not isinstance(piece_id, str) or not piece_id.isascii() or not compare_digest(piece_id, _digest(fields)):
        raise ValueError('piece identity does not match content')
    return envelope
