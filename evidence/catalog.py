from dataclasses import dataclass
from sqlite3 import Connection

from evidence.envelope import PieceEnvelope, verify_envelope
from evidence.payload import CoveragePayload, decode_coverage


@dataclass(frozen=True)
class AcceptedPiece:
    envelope: PieceEnvelope
    coverage: CoveragePayload

    @property
    def piece_id(self):
        return self.envelope.piece_id


class PieceCatalog:
    def __init__(self, connection: Connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS accepted_pieces (
                piece_id TEXT PRIMARY KEY NOT NULL,
                envelope TEXT NOT NULL
            )
        ''')

    def store_accepted_piece(self, envelope):
        verify_envelope(envelope)
        coverage = decode_coverage(envelope.payload)
        encoded = envelope.to_json()
        cursor = self.connection.execute('''
            INSERT INTO accepted_pieces (piece_id, envelope) VALUES (?, ?)
            ON CONFLICT(piece_id) DO NOTHING
        ''', (envelope.piece_id, encoded))
        if cursor.rowcount == 0:
            saved = self.connection.execute(
                'SELECT envelope FROM accepted_pieces WHERE piece_id = ?', (envelope.piece_id,)
            ).fetchone()
            if saved != (encoded,):
                raise ValueError('piece identity conflicts with the stored envelope')
        return AcceptedPiece(envelope, coverage)

    def get_accepted_piece(self, piece_id):
        if not isinstance(piece_id, str) or not piece_id:
            raise ValueError('invalid piece identity')
        row = self.connection.execute(
            'SELECT envelope FROM accepted_pieces WHERE piece_id = ?', (piece_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f'piece not received: {piece_id}')
        envelope = PieceEnvelope.from_json(row[0])
        if envelope.piece_id != piece_id:
            raise ValueError('stored envelope has a different identity')
        return AcceptedPiece(envelope, decode_coverage(envelope.payload))
