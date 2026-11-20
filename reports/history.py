import json
from dataclasses import asdict, dataclass

from analysis.head import HeadRequest, validate_head_request
from analysis.intervals import ClosedInterval
from reports.receipts import ReportReceipt, get_report_receipt


@dataclass(frozen=True)
class SignedReport:
    report_id: int
    parent_ids: tuple[str, str]
    request: HeadRequest
    positions: tuple[ClosedInterval, ...]
    receipt: ReportReceipt


def request_fields(request):
    return {name: str(value) for name, value in asdict(request).items()}


def position_fields(positions):
    return [[str(interval.left), str(interval.right)] for interval in positions]


def insert_report(connection, parent_ids, request, positions):
    cursor = connection.execute('''
        INSERT INTO reports (first_piece_id, second_piece_id, request, positions)
        VALUES (?, ?, ?, ?)
    ''', (
        *parent_ids,
        json.dumps(request_fields(request), sort_keys=True, separators=(',', ':')),
        json.dumps(position_fields(positions), separators=(',', ':')),
    ))
    return cursor.lastrowid


def read_report(store, report_id):
    if type(report_id) is not int or not 0 < report_id <= 2**63 - 1:
        raise ValueError('report identity must be a positive SQLite integer')
    row = store.connection.execute('''
        SELECT first_piece_id, second_piece_id, request, positions FROM reports WHERE report_id = ?
    ''', (report_id,)).fetchone()
    if row is None:
        raise LookupError(f'unknown report {report_id}')
    first, second, request, positions = row
    return SignedReport(
        report_id, (first, second), validate_head_request(HeadRequest(**json.loads(request))),
        tuple(ClosedInterval(*interval) for interval in json.loads(positions)),
        get_report_receipt(store, report_id),
    )
