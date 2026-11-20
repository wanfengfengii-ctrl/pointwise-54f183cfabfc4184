import json
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis.area import missed_area
from analysis.endpoints import encode_exact_positions
from analysis.head import HeadRequest
from analysis.intervals import ClosedInterval
from evidence.accept import accept_piece
from evidence.issue import issue_piece
from intake.batches import freeze_batch, register_batch
from intake.frames import ScanFrame
from intake.store import StationStore
from quality.calibration import AffineCalibration
from quality.gates import QualityRule
from reports.export import export_area_budget, export_report
from reports.history import read_area_budget, read_report
from reports.publish import publish_area_budget, publish_head
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
            # V2 area budget: zero tolerance reproduces the V1 full-coverage set
            # exactly, while a positive budget widens the signed centers.
            zero_budget = publish_area_budget(center, *parents, RAIL, 0)
            area_report = publish_area_budget(center, *parents, RAIL, Fraction(1, 8))
            area_witness = missed_area(
                center.catalog.get_accepted_piece(parents[0]).coverage,
                center.catalog.get_accepted_piece(parents[1]).coverage,
                RAIL, Fraction(2),
            )
        with ReportStore(root / 'center.sqlite') as center:
            recovered = read_report(center, report.report_id)
            exported = json.loads(export_report(recovered))
            recovered_zero = read_area_budget(center, zero_budget.report_id)
            recovered_area = read_area_budget(center, area_report.report_id)
            area_export = json.loads(export_area_budget(recovered_area))
            zero_export = json.loads(export_area_budget(recovered_zero))

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
    expected_area = encode_exact_positions(area_report.positions)
    if expected_area != [['11/8', '21/8']] or area_witness != 0:
        print('AREA_BUDGET_MISMATCH')
        return 1
    if zero_export['positions'] != [['3/2', '5/2']] or zero_export['budget'] != '0':
        print('ZERO_BUDGET_V1_MISMATCH')
        return 1
    if recovered_area != area_report or area_export['budget'] != '1/8' or area_export['budget_unit'] != 'mm2':
        print('AREA_BUDGET_RETRIEVAL_MISMATCH')
        return 1
    print(json.dumps(exported, ensure_ascii=False, sort_keys=True))
    print(json.dumps(zero_export, ensure_ascii=False, sort_keys=True))
    print(json.dumps(area_export, ensure_ascii=False, sort_keys=True))
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
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': 'ab.demo',
        'input': {'budgets': ['0', '1/8'], 'center': 2},
        'expected': {
            'zero_positions': [['3/2', '5/2']],
            'budgeted_positions': [['11/8', '21/8']],
            'missed_area_at_2': '0',
            'budget_unit': 'mm2',
        },
        'actual': {
            'zero_positions': zero_export['positions'],
            'budgeted_positions': area_export['positions'],
            'missed_area_at_2': str(area_witness),
            'budget_unit': area_export['budget_unit'],
        },
        'downstream_expected': area_export['positions'],
        'downstream_actual': json.loads(export_area_budget(recovered_area))['positions'],
        'code_paths': ['analysis/gaps.py', 'analysis/area.py', 'reports/publish.py', 'reports/export.py'],
        'oracle': 'Zero budget reproduces the V1 centers; the always-uncovered top band makes 1/8 mm^2 widen the signed span, and reopen returns the identical exact set.',
    }, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
