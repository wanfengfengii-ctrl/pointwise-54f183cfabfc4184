import json
import sqlite3
from fractions import Fraction

from analysis.area import area_budget_positions, missed_area, validate_budget
from analysis.endpoints import (
    ExactInterval,
    QuadraticEndpoint,
    compare_endpoints,
    decode_endpoint,
    decode_exact_positions,
    encode_exact_positions,
    endpoints_equal,
    merge_exact_intervals,
)
from analysis.head import HeadRequest
from analysis.positions import qualify_head_positions
from area_budget_examples import SLOPE, TENT
from demo import RAIL, rectangle
from evidence.payload import CoveragePayload
from reports.export import export_area_budget, export_report
from reports.history import read_area_budget, read_report
from reports.publish import publish_area_budget, publish_head
from reports.receipts import get_area_budget_receipt
from tests import ProjectCase, SOLID, endpoints


SLOPE_REQUEST = HeadRequest(0, 2, 1, 0, '3/2')
OVERLAP_REQUEST = HeadRequest(0, 2, 1, 0, 1)


def _fraction_polygon(polygon):
    return tuple((Fraction(x), Fraction(y)) for x, y in polygon)


SLOPE_EXACT = tuple(_fraction_polygon(polygon) for polygon in SLOPE)
TENT_EXACT = tuple(_fraction_polygon(polygon) for polygon in TENT)
SLOPE_COVERAGE = (CoveragePayload(SLOPE_EXACT), CoveragePayload(()))
TENT_COVERAGE = CoveragePayload(TENT_EXACT)


def exact_text(interval):
    return encode_exact_positions((interval,))[0]


class AreaBudgetEngineTests(ProjectCase):
    def test_slope_handover_example(self):
        first, second = SLOPE_COVERAGE
        positions = area_budget_positions(first, second, SLOPE_REQUEST, Fraction(1, 8))
        expected_left = QuadraticEndpoint('3/2', '-1/2', 2)
        self.assertEqual(len(positions), 1)
        self.assertTrue(endpoints_equal(positions[0].left, expected_left))
        self.assertEqual(positions[0].right, Fraction(3, 2))
        # The witness center 4/5 is admitted; 3/4 falls outside the signed span.
        self.assertTrue(compare_endpoints(positions[0].left, Fraction(4, 5)) <= 0)
        self.assertTrue(compare_endpoints(Fraction(3, 4), positions[0].left) < 0)
        # Exact missed area at the 4/5 mm center is the handover 49/400 mm^2 figure.
        witness = missed_area(first, second, SLOPE_REQUEST, Fraction(4, 5))
        self.assertEqual(witness, Fraction(49, 400))
        self.assertLessEqual(witness, Fraction(1, 8))
        actual = exact_text(positions[0])
        self.scenario('ab1.slope', {'budget': '1/8', 'witness': '4/5'},
                      [[{'offset': '3/2', 'scale': '-1/2', 'radicand': '2'}, '3/2']], [actual],
                      '49/400', str(witness),
                      ['analysis/gaps.py', 'analysis/area.py', 'analysis/endpoints.py'],
                      'The uncovered area is a piecewise quadratic of the center; solving A(c)<=1/8 gives the surd left endpoint.')

    def test_slope_rational_roots_and_zero_budget(self):
        first, second = SLOPE_COVERAGE
        rational_case = area_budget_positions(first, second, SLOPE_REQUEST, Fraction(1, 16))
        self.assertEqual(rational_case, (ExactInterval(Fraction(1), Fraction(3, 2)),))
        zero = area_budget_positions(first, second, SLOPE_REQUEST, 0)
        self.assertEqual(zero, (ExactInterval(Fraction(3, 2), Fraction(3, 2)),))
        actual = [exact_text(rational_case[0]), exact_text(zero[0])]
        expected = [['1', '3/2'], ['3/2', '3/2']]
        self.scenario('ab1.slope_rationals', {'budgets': ['1/16', '0']},
                      expected, actual,
                      'Fraction', type(zero[0].left).__name__,
                      ['analysis/area.py'],
                      'Budget 1/16 yields a rational discriminant; zero budget leaves the single V1 center.')

    def test_overlap_handover_example(self):
        positions_38 = area_budget_positions(TENT_COVERAGE, TENT_COVERAGE, OVERLAP_REQUEST, Fraction(3, 8))
        expected = ExactInterval(
            QuadraticEndpoint(1, Fraction(-1, 4), 2),
            QuadraticEndpoint(1, Fraction(1, 4), 2),
        )
        self.assertEqual(len(positions_38), 1)
        self.assertTrue(endpoints_equal(positions_38[0].left, expected.left))
        self.assertTrue(endpoints_equal(positions_38[0].right, expected.right))
        quarter = area_budget_positions(TENT_COVERAGE, TENT_COVERAGE, OVERLAP_REQUEST, Fraction(1, 4))
        self.assertEqual(quarter, (ExactInterval(Fraction(1), Fraction(1)),))
        eighth = area_budget_positions(TENT_COVERAGE, TENT_COVERAGE, OVERLAP_REQUEST, Fraction(1, 8))
        self.assertEqual(eighth, ())
        actual = [exact_text(positions_38[0]), exact_text(quarter[0]), []]
        expected = [
            [{'offset': '1', 'scale': '-1/4', 'radicand': '2'},
             {'offset': '1', 'scale': '1/4', 'radicand': '2'}],
            ['1', '1'], [],
        ]
        self.scenario('ab2.overlap', {'budgets': ['3/8', '1/4', '1/8']},
                      expected, actual,
                      '1/4', str(missed_area(TENT_COVERAGE, TENT_COVERAGE, OVERLAP_REQUEST, 1)),
                      ['analysis/gaps.py', 'analysis/area.py'],
                      'The tent minimum misses 1/4 mm^2 at center 1; larger budgets open a symmetric surd span.')

    def test_zero_budget_matches_v1_everywhere(self):
        solid = (_fraction_polygon(rectangle(0, 4, 0, 2)),)
        outer = (
            _fraction_polygon(rectangle(0, 4, 0, Fraction(1, 2))),
            _fraction_polygon(rectangle(0, 4, Fraction(3, 2), 2)),
        )
        bridge = (_fraction_polygon(rectangle(1, 3, Fraction(1, 2), Fraction(3, 2))),)
        cases = (
            (solid, (), RAIL),
            (outer, bridge, RAIL),
            (SLOPE_EXACT, (), SLOPE_REQUEST),
            (TENT_EXACT, TENT_EXACT, OVERLAP_REQUEST),
        )
        last = None
        for first_polygons, second_polygons, request in cases:
            first = CoveragePayload(first_polygons)
            second = CoveragePayload(second_polygons)
            v1 = endpoints(qualify_head_positions(first, second, request))
            budgeted = encode_exact_positions(area_budget_positions(first, second, request, 0))
            self.assertEqual(budgeted, v1)
            last = (v1, budgeted)
        self.scenario('ab3.zero_equivalence', {'cases': len(cases)}, last[0], last[1], (), (),
                      ['analysis/positions.py', 'analysis/area.py'],
                      'A zero area budget admits exactly the centers whose whole rectangle is covered.')

    def test_rail_shorter_than_head_is_empty(self):
        first, second = SLOPE_COVERAGE
        short = HeadRequest(0, Fraction(1, 2), 1, 0, '3/2')
        empty = area_budget_positions(first, second, short, Fraction(1, 8))
        self.assertEqual(empty, ())
        # Full coverage still reports the complete center travel with a generous budget.
        solid = CoveragePayload((_fraction_polygon(rectangle(0, 4, 0, 2)),))
        full = area_budget_positions(solid, CoveragePayload(()), RAIL, Fraction(999))
        self.assertEqual(full, (ExactInterval(Fraction(1, 2), Fraction(7, 2)),))
        self.scenario('ab4.rail', {'rail_length': '1/2', 'width': 1},
                      [[], ['1/2', '7/2']], [[], exact_text(full[0])], (), (),
                      ['analysis/area.py'],
                      'No center fits a rail shorter than the head; a fully covered rail signs every legal center.')

    def test_budget_validation(self):
        for bad in (-1, Fraction(-1, 2), '-3', True):
            with self.assertRaises(ValueError):
                validate_budget(bad)
        accepted = [validate_budget(good) for good in (0, Fraction(0), '0', Fraction(1, 8), '2/3', 5)]
        self.assertTrue(all(value >= 0 for value in accepted))
        self.scenario('ab5.validation', {'negatives': 4, 'accepted': len(accepted)},
                      'ValueError', 'ValueError', (), (),
                      ['analysis/area.py'], 'Budgets are non-negative exact rationals; booleans are rejected.')

    def test_vertical_edge_gap_jump(self):
        # Coverage starts abruptly at the vertical edge x=1; the gap on [0,1)
        # stays at the full band height instead of sloping toward the edge.
        strip = (
            (Fraction(1), Fraction(0)), (Fraction(3), Fraction(0)),
            (Fraction(3), Fraction(1, 2)), (Fraction(1), Fraction(1, 2)),
        )
        cov = CoveragePayload((_fraction_polygon(strip),))
        request = HeadRequest(0, 6, Fraction(1, 2), 0, Fraction(3, 2))
        # Window [0, 1/2] never reaches the strip: whole band is uncovered.
        self.assertEqual(
            missed_area(cov, CoveragePayload(()), request, Fraction(1, 4)),
            Fraction(3, 4),
        )
        # Window [1, 3/2] sits inside the strip's covered half-height.
        self.assertEqual(
            missed_area(cov, CoveragePayload(()), request, Fraction(5, 4)),
            Fraction(1, 2),
        )
        # The band [0, 3/2] can never be fully covered, so zero budget signs nothing.
        self.assertEqual(area_budget_positions(cov, CoveragePayload(()), request, 0), ())
        self.scenario('ab4.vertical_edge', {'edge': 1, 'band_height': '3/2'},
                      ['3/4', '1/2', []],
                      [str(missed_area(cov, CoveragePayload(()), request, Fraction(1, 4))),
                       str(missed_area(cov, CoveragePayload(()), request, Fraction(5, 4))),
                       encode_exact_positions(area_budget_positions(cov, CoveragePayload(()), request, 0))],
                      (), (), ['analysis/gaps.py', 'analysis/area.py'],
                      'A vertical footprint edge is a zero-width jump; interior gap samples keep it exact.')

    def test_engine_matches_independent_piecewise_oracle(self):
        import random
        random.seed(11)
        for _ in range(25):
            polygons = []
            for _piece in range(random.randint(0, 3)):
                x1 = Fraction(random.randint(0, 8), 2)
                x2 = x1 + Fraction(random.randint(1, 6), 2)
                y1 = Fraction(random.randint(0, 4), 2)
                y2 = y1 + Fraction(random.randint(1, 6), 2)
                polygons.append((
                    (x1, y1), (x2, y1), (x2, y2), (x1, y2),
                ))
            width = Fraction(random.choice([1, 2, 3, 4]), 2)
            upper = Fraction(random.randint(2, 5), 2)
            request = HeadRequest(0, 6, width, 0, upper)
            cov = CoveragePayload(tuple(polygons))
            half = width / 2
            for k in range(0, 21, 4):
                center = half + (6 - width) * Fraction(k, 20)
                exact = missed_area(cov, CoveragePayload(()), request, center)
                oracle = _rectangle_oracle(polygons, center - half, center + half, upper)
                self.assertEqual(exact, oracle)
        self.scenario('ab4.oracle', {'configurations': 25}, 'exact equality', 'exact equality',
                      (), (), ['analysis/gaps.py', 'analysis/area.py'],
                      'The piecewise quadratic engine agrees with an independent rectangle-clipping integral.')


def _rectangle_oracle(polygons, xl, xr, upper):
    breaks = sorted({x for polygon in polygons for x, _ in polygon if xl <= x <= xr} | {xl, xr})
    total = Fraction(0)
    for start, end in zip(breaks, breaks[1:]):
        midpoint = (start + end) / 2
        sections = []
        for polygon in polygons:
            x1 = min(x for x, _ in polygon)
            x2 = max(x for x, _ in polygon)
            y1 = min(y for _, y in polygon)
            y2 = max(y for _, y in polygon)
            if x1 <= midpoint <= x2 and y2 > 0 and y1 < upper:
                sections.append((max(Fraction(0), y1), min(upper, y2)))
        if not sections:
            covered = Fraction(0)
        else:
            sections.sort()
            merged = [sections[0]]
            for lo, hi in sections[1:]:
                if lo <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
                else:
                    merged.append((lo, hi))
            covered = sum(hi - lo for lo, hi in merged)
        total += (upper - covered) * (end - start)
    return total


class EndpointAlgebraTests(ProjectCase):
    def test_quadratic_normalization_and_comparison(self):
        # sqrt(8) folds to 2*sqrt(2).
        endpoint = QuadraticEndpoint('1/2', '1/3', 8)
        self.assertEqual((endpoint.offset, endpoint.scale, endpoint.radicand),
                         (Fraction(1, 2), Fraction(2, 3), 2))
        surd = QuadraticEndpoint(1, 1, 2)  # 1 + sqrt(2) ~= 2.414
        self.assertEqual(compare_endpoints(surd, Fraction(1)), 1)
        self.assertEqual(compare_endpoints(Fraction(2), surd), -1)
        self.assertEqual(compare_endpoints(Fraction(3), surd), 1)
        self.assertEqual(compare_endpoints(surd, QuadraticEndpoint(1, 1, 2)), 0)
        self.assertEqual(compare_endpoints(QuadraticEndpoint(0, 1, 3), surd), -1)
        self.scenario('ab11.algebra', {'radicand': 8},
                      ['1/2', '2/3', '2'],
                      [str(endpoint.offset), str(endpoint.scale), str(endpoint.radicand)],
                      (), (), ['analysis/endpoints.py'],
                      'Non-square-free radicands normalize into the scale and comparisons stay exact.')

    def test_invalid_irrational_endpoints(self):
        for body in (
            {'offset': '1', 'scale': '0', 'radicand': '2'},
            {'offset': '1', 'scale': '1', 'radicand': '1'},
            {'offset': '1', 'scale': '1', 'radicand': '4'},
            {'offset': '1', 'scale': '1', 'radicand': '0'},
            {'offset': '1', 'scale': '1', 'radicand': '-2'},
            {'offset': 'bad', 'scale': '1', 'radicand': '2'},
            {'offset': '1', 'scale': '1'},
        ):
            with self.assertRaises(ValueError):
                QuadraticEndpoint.from_json(body)
        with self.assertRaises(ValueError):
            decode_endpoint('1/0')
        self.scenario('ab11.invalid', {'rejected': 8}, 'ValueError', 'ValueError', (), (),
                      ['analysis/endpoints.py'],
                      'Only canonical p+q*sqrt(r) with non-zero q and a non-square positive r decode.')

    def test_exact_merge_orders_mixed_endpoints(self):
        touch = QuadraticEndpoint(1, 1, 2)
        merged = merge_exact_intervals((
            ExactInterval(Fraction(0), touch),
            ExactInterval(touch, Fraction(3)),
            ExactInterval(Fraction(5), Fraction(5)),
        ))
        self.assertEqual(merged, (ExactInterval(Fraction(0), Fraction(3)),
                                  ExactInterval(Fraction(5), Fraction(5))))
        encoded = encode_exact_positions(merged)
        self.assertEqual(decode_exact_positions(encoded), merged)
        self.scenario('ab11.merge', {}, [['0', '3'], ['5', '5']], encoded, (), (),
                      ['analysis/endpoints.py'],
                      'Touching closed intervals merge even when the shared endpoint is an irrational surd.')


class AreaBudgetReportTests(ProjectCase):
    def _slope_pair(self, center):
        return self.accept(center, 'A', SLOPE), self.accept(center, 'B', ())

    def test_publish_reopen_and_exact_json_set(self):
        with self.center() as center:
            parents = self._slope_pair(center)
            report = publish_area_budget(center, *parents, SLOPE_REQUEST, Fraction(1, 8))
            exported = json.loads(export_area_budget(report))
            self.assertEqual(report.parent_ids, tuple(parents))
            self.assertEqual(report.budget, Fraction(1, 8))
            self.assertEqual(report.receipt.receipt_id, f'area:{report.report_id}')
        with self.center() as center:
            recovered = read_area_budget(center, report.report_id)
            self.assertEqual(recovered, report)
            reopened_export = json.loads(export_area_budget(recovered))
            self.assertEqual(reopened_export, exported)
            self.assertEqual(reopened_export['budget_unit'], 'mm2')
            self.assertEqual(reopened_export['unit'], 'mm')
            self.assertEqual(reopened_export['budget'], '1/8')
            self.assertEqual(reopened_export['parent_ids'], list(parents))
            self.assertEqual(reopened_export['receipt'],
                             {'receipt_id': f'area:{report.report_id}', 'report_id': report.report_id})
            # The JSON body alone fixes the exact irrational endpoint set.
            decoded = decode_exact_positions(reopened_export['positions'])
            self.assertEqual(decoded, report.positions)
        self.scenario('ab6.publish', {'budget': '1/8'},
                      exported['positions'], reopened_export['positions'],
                      report.receipt, recovered.receipt,
                      ['reports/publish.py', 'reports/history.py', 'reports/export.py'],
                      'Report, parent links and receipt commit together; reopening returns the same exact set.')

    def test_illegal_specs_wrong_station_and_mixed_domain(self):
        with self.center() as center:
            parents = self._slope_pair(center)
            with self.assertRaisesRegex(ValueError, 'non-negative'):
                publish_area_budget(center, *parents, SLOPE_REQUEST, Fraction(-1, 2))
            with self.assertRaisesRegex(ValueError, 'width must be positive'):
                publish_area_budget(center, *parents, HeadRequest(0, 2, 0, 0, 1), Fraction(1, 8))
            same_station = (parents[0], self.accept(center, 'A', SOLID, revision_id='r2'))
            with self.assertRaisesRegex(ValueError, 'two distinct stations'):
                publish_area_budget(center, *same_station, SLOPE_REQUEST, Fraction(1, 8))
            other = self.accept(center, 'B', SOLID, revision_id='r9', domain='other-origin')
            with self.assertRaisesRegex(ValueError, 'different coordinate domains'):
                publish_area_budget(center, parents[0], other, SLOPE_REQUEST, Fraction(1, 8))
            with self.assertRaises(LookupError):
                publish_area_budget(center, parents[0], 'unknown-piece', SLOPE_REQUEST, Fraction(1, 8))
            counts = self.counts(center)
            area_rows = center.connection.execute('SELECT count(*) FROM area_budget_reports').fetchone()[0]
        self.assertEqual((counts, area_rows), ((0, 0), 0))
        self.scenario('ab7.rejections', {}, 'ValueError/LookupError', 'ValueError/LookupError',
                      ((0, 0), 0), (counts, area_rows),
                      ['reports/publish.py', 'evidence/accept.py'],
                      'Validation happens before the write transaction, so failures leave no report or receipt.')

    def test_report_types_keep_separate_identities(self):
        with self.center() as center:
            parents = self.pair(center)
            head = publish_head(center, *parents, RAIL)
            area = publish_area_budget(center, *parents, RAIL, 0)
            # Each type numbers from one on its own table; receipts stay distinct too.
            self.assertEqual(head.report_id, area.report_id)
            self.assertEqual(head.receipt.receipt_id, 'head:1')
            self.assertEqual(area.receipt.receipt_id, 'area:1')
            # The typed read entries never look into the other type's table.
            self.assertEqual(read_report(center, head.report_id), head)
            self.assertEqual(read_area_budget(center, area.report_id), area)
            with self.assertRaises(LookupError):
                read_area_budget(center, head.report_id + 100)
            with self.assertRaises(LookupError):
                read_report(center, area.report_id + 100)
            with self.assertRaises(ValueError):
                read_area_budget(center, -1)
            head_export = json.loads(export_report(head))
            area_export = json.loads(export_area_budget(area))
        self.assertNotIn('budget', head_export)
        self.assertEqual(area_export['budget'], '0')
        self.scenario('ab8.identities', {'head': head.report_id, 'area': area.report_id},
                      'separate tables', 'separate tables',
                      ('head:1', 'area:1'), (head.receipt.receipt_id, area.receipt.receipt_id),
                      ['reports/store.py', 'reports/history.py'],
                      'Each report type owns its numbering and read entry; a number only resolves in its own type.')

    def test_correction_keeps_original_numbers(self):
        with self.center() as center:
            first, second = self._slope_pair(center)
            old = publish_area_budget(center, first, second, SLOPE_REQUEST, Fraction(1, 8))
            corrected = self.accept(center, 'B', TENT, revision_id='r2')
            new = publish_area_budget(center, first, corrected, OVERLAP_REQUEST, Fraction(3, 8))
            self.assertNotEqual(old.report_id, new.report_id)
            old_text = export_area_budget(old)
        with self.center() as center:
            restored_old = read_area_budget(center, old.report_id)
            restored_new = read_area_budget(center, new.report_id)
            self.assertEqual(restored_old, old)
            self.assertEqual(restored_new, new)
            self.assertEqual(export_area_budget(restored_old), old_text)
            self.assertEqual(get_area_budget_receipt(center, old.report_id), old.receipt)
        self.scenario('ab9.correction', {'old': old.report_id, 'new': new.report_id},
                      old.parent_ids, restored_old.parent_ids,
                      new.parent_ids, restored_new.parent_ids,
                      ['reports/publish.py', 'reports/history.py'],
                      'An erratum is a new issuance; the original number still returns its parents, budget and spans.')

    def test_commit_failure_leaves_no_area_report(self):
        with self.center() as center:
            parents = self._slope_pair(center)
            existing = publish_area_budget(center, *parents, SLOPE_REQUEST, Fraction(1, 8))
        staged = []

        def deny_commit(connection):
            staged.append(connection.execute('''
                SELECT report_id FROM area_budget_reports ORDER BY report_id DESC LIMIT 1
            ''').fetchone())

        with self.center(before_commit=deny_commit) as center:
            def authorizer(action, first, second, database, source):
                if action == sqlite3.SQLITE_TRANSACTION and first == 'COMMIT':
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK

            center.connection.set_authorizer(authorizer)
            with self.assertRaises(sqlite3.DatabaseError) as failure:
                publish_area_budget(center, *parents, SLOPE_REQUEST, Fraction(1, 16))
            self.assertEqual(failure.exception.sqlite_errorcode, sqlite3.SQLITE_AUTH)
            self.assertFalse(center.connection.in_transaction)
        self.assertEqual(len(staged), 1)
        candidate = staged[0][0]
        self.assertNotEqual(candidate, existing.report_id)
        with self.center() as center:
            with self.assertRaises(LookupError):
                read_area_budget(center, candidate)
            with self.assertRaises(LookupError):
                get_area_budget_receipt(center, candidate)
            saved = read_area_budget(center, existing.report_id)
            rows = (
                center.connection.execute('SELECT count(*) FROM area_budget_reports').fetchone()[0],
                center.connection.execute('SELECT count(*) FROM area_budget_receipts').fetchone()[0],
            )
        self.assertEqual((saved, rows), (existing, (1, 1)))
        self.scenario('ab10.rollback', {'staged': candidate, 'existing': existing.report_id},
                      sqlite3.SQLITE_AUTH, failure.exception.sqlite_errorcode,
                      (1, 1), rows, ['reports/store.py', 'reports/publish.py'],
                      'A denied COMMIT rolls back the report and its receipt together and the same call can be retried.')
