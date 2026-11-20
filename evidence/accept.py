from evidence.envelope import PieceEnvelope, verify_envelope


def accept_piece(catalog, envelope, expected_station):
    if isinstance(envelope, str):
        envelope = PieceEnvelope.from_json(envelope)
    else:
        verify_envelope(envelope)
    if envelope.station_id != expected_station:
        raise ValueError('piece does not match the expected station')
    return catalog.store_accepted_piece(envelope)


def resolve_qualification_parents(catalog, first_piece_id, second_piece_id):
    first = catalog.get_accepted_piece(first_piece_id)
    second = catalog.get_accepted_piece(second_piece_id)
    if first.envelope.station_id == second.envelope.station_id:
        raise ValueError('qualification needs two distinct stations')
    if first.envelope.domain != second.envelope.domain:
        raise ValueError('pieces have different coordinate domains')
    return first, second
