import json
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis.head import HeadRequest
from analysis.intervals import ClosedInterval
from evidence.accept import accept_piece
from evidence.issue import issue_piece
from intake.batches import freeze_batch, register_batch
from intake.frames import ScanFrame
from intake.store import StationStore
from quality.calibration import AffineCalibration
from quality.gates import QualityRule
from reports.export import export_report
from reports.history import read_report
from reports.publish import publish_head
from reports.store import ReportStore


IDENTITY = AffineCalibration(1, 0, 0, 0, 1, 0)
GATE = QualityRule(1, 2)
DOMAIN = 'line-4-mm'


def rectangle(left, right, lower, upper):
    return ((left, lower), (right, lower), (right, upper), (left, upper))


RAIL = HeadRequest(0, 4, 1, 0, 2)
OUTER_BANDS = (rectangle(0, 4, 0, '1/2'), rectangle(0, 4, '3/2', 2))
MID_BRIDGE = (rectangle(1, 3, '1/2', '3/2'),)


def make_piece(path, station_id, polygons, *, revision_id='r1', domain=DOMAIN):
    frames = tuple(ScanFrame(f'scan-{i}', polygon, 1) for i, polygon in enumerate(polygons, 1))
    with StationStore(path, station_id) as station:
        register_batch(station, 'shift-7', 'Night shift strip inspection')
        freeze_batch(station, 'shift-7', revision_id, frames, IDENTITY, GATE, domain)
        return issue_piece(station, revision_id)


def main():
    with TemporaryDirectory(prefix='strip-inspection-') as directory:
        root = Path(directory)
        with ReportStore(root / 'center.sqlite') as center:
            first = make_piece(root / 'a.sqlite', 'A', OUTER_BANDS)
            second = make_piece(root / 'b.sqlite', 'B', MID_BRIDGE)
            parents = tuple(
                accept_piece(center.catalog, piece.to_json(), station).piece_id
                for piece, station in ((first, 'A'), (second, 'B'))
            )
            report = publish_head(center, *parents, RAIL)
        with ReportStore(root / 'center.sqlite') as center:
            recovered = read_report(center, report.report_id)
            exported = json.loads(export_report(recovered))

    expected_positions = (ClosedInterval('3/2', '5/2'),)
    if report.positions != expected_positions:
        print(f'HEAD_COVERAGE_MISMATCH expected {expected_positions} got {report.positions}')
        return 1
    if recovered != report or exported['parent_ids'] != list(parents):
        print('REPORT_RETRIEVAL_MISMATCH')
        return 1
    expected_export = {'positions': [['3/2', '5/2']], 'parent_ids': list(parents)}
    actual_export = {field: exported[field] for field in expected_export}
    if actual_export != expected_export:
        print('REPORT_EXPORT_MISMATCH')
        return 1
    print(json.dumps(exported, ensure_ascii=False, sort_keys=True))
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': 'n5',
        'input': {'A': OUTER_BANDS, 'B': MID_BRIDGE, 'rail': [0, 4], 'width': 1, 'band': [0, 2]},
        'expected': [['3/2', '5/2']],
        'actual': [[str(interval.left), str(interval.right)] for interval in report.positions],
        'downstream_expected': expected_export,
        'downstream_actual': actual_export,
        'code_paths': ['evidence/issue.py', 'analysis/coverage.py', 'reports/publish.py', 'reports/history.py', 'reports/export.py'],
        'oracle': 'The middle band is filled from x=1 to x=3 inclusive. Move each edge in by half a millimeter.',
    }, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
