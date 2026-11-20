import json
from dataclasses import asdict

from reports.history import position_fields, request_fields


def export_report(report):
    output = {
        'report_id': report.report_id,
        'parent_ids': list(report.parent_ids),
        'request': request_fields(report.request),
        'positions': position_fields(report.positions),
        'receipt': asdict(report.receipt),
        'unit': 'mm',
    }
    return json.dumps(output, sort_keys=True, separators=(',', ':'))
