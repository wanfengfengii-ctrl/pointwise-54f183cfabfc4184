import json
from dataclasses import dataclass

from quality.footprints import Polygon, canonical_polygon


@dataclass(frozen=True)
class CoveragePayload:
    polygons: tuple[Polygon, ...]


def _normalize(polygons):
    if not isinstance(polygons, (tuple, list)):
        raise ValueError('coverage polygons must be a sequence')
    return tuple(sorted({canonical_polygon(polygon) for polygon in polygons}))


def _encode(polygons):
    body = {'polygons': [[[str(x), str(y)] for x, y in polygon] for polygon in polygons]}
    return json.dumps(body, separators=(',', ':'))


def encode_coverage(coverage):
    if not isinstance(coverage, CoveragePayload):
        raise ValueError('expected a CoveragePayload')
    return _encode(_normalize(coverage.polygons))


def decode_coverage(encoded):
    if not isinstance(encoded, str):
        raise ValueError('coverage payload must be JSON text')
    try:
        body = json.loads(encoded)
    except ValueError as exc:
        raise ValueError('malformed coverage JSON') from exc
    if not isinstance(body, dict) or body.keys() != {'polygons'}:
        raise ValueError('invalid coverage fields')
    polygons = _normalize(body['polygons'])
    if _encode(polygons) != encoded:
        raise ValueError('coverage payload is not canonical')
    return CoveragePayload(polygons)
