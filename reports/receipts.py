from dataclasses import dataclass


@dataclass(frozen=True)
class ReportReceipt:
    receipt_id: str
    report_id: int


def insert_report_receipt(connection, report_id):
    receipt = ReportReceipt(f'head:{report_id}', report_id)
    connection.execute('''
        INSERT INTO report_receipts (receipt_id, report_id) VALUES (?, ?)
    ''', (receipt.receipt_id, receipt.report_id))
    return receipt


def get_report_receipt(store, report_id):
    row = store.connection.execute(
        'SELECT receipt_id FROM report_receipts WHERE report_id = ?', (report_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f'no success receipt for report {report_id}')
    return ReportReceipt(row[0], report_id)
