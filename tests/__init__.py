"""Shared workspace and evidence tracing for the business regressions."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from demo import DOMAIN, make_piece, rectangle
from evidence.accept import accept_piece
from reports.store import ReportStore


SOLID = (rectangle(0, 4, 0, 2),)


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory(prefix='strip-test-')))

    def center(self, **options):
        return ReportStore(self.root / 'center.sqlite', **options)

    def piece(self, station, polygons, **options):
        return make_piece(self.root / f'{station}.sqlite', station, polygons, **options)

    def accept(self, center, station, polygons, **options):
        envelope = self.piece(station, polygons, **options)
        return accept_piece(center.catalog, envelope.to_json(), station).piece_id

    def pair(self, center, first=SOLID, second=(), *, second_domain=DOMAIN):
        return (
            self.accept(center, 'A', first),
            self.accept(center, 'B', second, domain=second_domain),
        )

    def counts(self, center):
        connection = center.connection
        return (
            connection.execute('SELECT count(*) FROM reports').fetchone()[0],
            connection.execute('SELECT count(*) FROM report_receipts').fetchone()[0],
        )

    def scenario(self, case_id, inputs, expected, actual, downstream_expected, downstream_actual, code_paths, oracle):
        self.assertEqual(actual, expected)
        self.assertEqual(downstream_actual, downstream_expected)
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': case_id,
            'input': inputs,
            'expected': expected,
            'actual': actual,
            'downstream_expected': downstream_expected,
            'downstream_actual': downstream_actual,
            'code_paths': code_paths,
            'oracle': oracle,
        }, sort_keys=True, default=str))


def endpoints(positions):
    return [[str(interval.left), str(interval.right)] for interval in positions]
