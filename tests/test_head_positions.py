import json
from dataclasses import replace
from fractions import Fraction

from analysis.edges import vertical_section
from analysis.head import HeadRequest
from analysis.intervals import ClosedInterval
from demo import DOMAIN, MID_BRIDGE, OUTER_BANDS, RAIL, rectangle
from evidence.accept import accept_piece
from evidence.envelope import seal_envelope
from evidence.payload import CoveragePayload, decode_coverage, encode_coverage
from reports.export import export_report
from reports.history import read_report
from reports.publish import publish_head
from tests import ProjectCase, SOLID, endpoints


class HeadPositionsTests(ProjectCase):
    def test_solid_stock_offline(self):
        with self.center() as center:
            parents = self.pair(center)
        with self.center() as center:
            report = publish_head(center, *parents, RAIL)
            self.assertEqual(report.positions, (ClosedInterval('1/2', '7/2'),))
            restored = read_report(center, report.report_id)
        self.scenario('n3', {'stock': [0, 4, 0, 2], 'width': 1},
                      [['1/2', '7/2']], endpoints(report.positions), (parents, report.receipt),
                      (restored.parent_ids, restored.receipt),
                      ['evidence/catalog.py', 'analysis/positions.py', 'reports/publish.py', 'reports/history.py'],
                      'The solid footprint fills the rail. Both head sides need half a millimeter of margin.')

    def test_rail_edges(self):
        with self.center() as center:
            parents = self.pair(center)
            fitting = publish_head(center, *parents, HeadRequest(1, 3, 1, 0, 2))
            wider = publish_head(center, *parents, HeadRequest(1, 3, 3, 0, 2))
            saved = read_report(center, wider.report_id)
        self.scenario('n3.rail_edges', {'rail': [1, 3], 'widths': [1, 3]},
                      ([['3/2', '5/2']], []), (endpoints(fitting.positions), endpoints(wider.positions)),
                      ([], parents), (endpoints(saved.positions), saved.parent_ids),
                      ['analysis/head.py', 'analysis/positions.py', 'reports/history.py'],
                      'A rail of length 2 leaves one millimeter of center travel for width 1 and has no space for width 3.')

    def test_wrong_station(self):
        with self.center() as center:
            piece = self.piece('B', SOLID)
            first = self.accept(center, 'A', SOLID)
            with self.assertRaisesRegex(ValueError, 'expected station') as rejected:
                accept_piece(center.catalog, piece, 'A')
            with self.assertRaises(LookupError):
                center.catalog.get_accepted_piece(piece.piece_id)
            with self.assertRaises(LookupError):
                publish_head(center, first, piece.piece_id, RAIL)
            self.scenario('n4.wrong_station', {'expected': 'A', 'observed': 'B'},
                          'ValueError', type(rejected.exception).__name__, (0, 0), self.counts(center),
                          ['evidence/accept.py', 'evidence/catalog.py', 'reports/publish.py'],
                          'An envelope from station B cannot be admitted as A or used as an unreceived parent.')

    def test_content_identity(self):
        with self.center() as center:
            source = self.piece('A', SOLID)
            accepted = accept_piece(center.catalog, source.to_json(), 'A')
            self.assertEqual(accept_piece(center.catalog, source, 'A'), accepted)
            revised = encode_coverage(CoveragePayload((rectangle(0, 3, 0, 2),)))
            changed = replace(source, payload=revised)
            with self.assertRaisesRegex(ValueError, 'identity does not match') as rejected:
                accept_piece(center.catalog, changed, 'A')
            saved = center.catalog.get_accepted_piece(accepted.piece_id)
            self.assertEqual(center.connection.execute('SELECT count(*) FROM accepted_pieces').fetchone(), (1,))
            self.scenario('n4.content_identity', {'original_right': 4, 'changed_right': 3, 'given_id': changed.piece_id},
                          'ValueError', type(rejected.exception).__name__, (accepted, (0, 0)), (saved, self.counts(center)),
                          ['evidence/envelope.py', 'evidence/payload.py', 'evidence/catalog.py'],
                          'Changing a bound while retaining the original identity invalidates the envelope and leaves the saved piece intact.')

    def test_same_unit_different_domain(self):
        other = 'different-origin'
        with self.center() as center:
            parents = self.pair(center, SOLID, SOLID, second_domain=other)
            pieces = tuple(center.catalog.get_accepted_piece(parent) for parent in parents)
            self.assertEqual(tuple(piece.envelope.unit for piece in pieces), ('mm', 'mm'))
            with self.assertRaisesRegex(ValueError, 'different coordinate domains') as rejected:
                publish_head(center, *parents, RAIL)
        with self.center() as center:
            counts = self.counts(center)
            domains = tuple(center.catalog.get_accepted_piece(parent).envelope.domain for parent in parents)
        self.scenario('n4', {'domains': [DOMAIN, other]},
                      'ValueError', type(rejected.exception).__name__, (0, 0), counts,
                      ['evidence/accept.py', 'reports/publish.py', 'reports/store.py'],
                      'There is no coordinate correspondence between the two domain identifiers.')
        self.scenario('n4.same_unit_different_domain', {'domains': [DOMAIN, other], 'units': ['mm', 'mm']},
                      (DOMAIN, other), domains, (0, 0), counts,
                      ['evidence/catalog.py', 'evidence/accept.py', 'reports/store.py'],
                      'Millimeters measure distance in either domain and do not give them a common origin.')

    def test_gap_witness(self):
        with self.center() as center:
            split = self.accept(center, 'A', OUTER_BANDS)
            solid = self.accept(center, 'A', SOLID, revision_id='r2')
            bridge = self.accept(center, 'B', MID_BRIDGE)
            covered = []
            for piece_id in (split, solid):
                coverage = center.catalog.get_accepted_piece(piece_id).coverage
                sections = [vertical_section(polygon, Fraction(0)) for polygon in coverage.polygons]
                covered.append(any(section is not None and section.left <= 1 <= section.right for section in sections))
            split_report = publish_head(center, split, bridge, RAIL)
            solid_report = publish_head(center, solid, bridge, RAIL)
        self.scenario('n5.gap_witness', {'point': [0, 1], 'A_split': OUTER_BANDS, 'A_solid': SOLID},
                      [False, True], covered,
                      ([['3/2', '5/2']], [['1/2', '7/2']]),
                      (endpoints(split_report.positions), endpoints(solid_report.positions)),
                      ['evidence/issue.py', 'evidence/payload.py', 'analysis/edges.py', 'reports/publish.py'],
                      'The two bands at x=0 leave y=1 outside, while the same outer rectangle filled in contains that point.')

    def test_bridge_offline(self):
        with self.center() as center:
            parents = self.pair(center, OUTER_BANDS, MID_BRIDGE)
            report = publish_head(center, *parents, RAIL)
            saved = read_report(center, report.report_id)
        self.scenario('n5', {'A': OUTER_BANDS, 'B': MID_BRIDGE, 'width': 1},
                      [['3/2', '5/2']], endpoints(report.positions),
                      (parents, [['3/2', '5/2']]), (saved.parent_ids, endpoints(saved.positions)),
                      ['evidence/issue.py', 'analysis/coverage.py', 'analysis/positions.py', 'reports/history.py'],
                      'Only the closed part of the rail from 1 through 3 has all three bands, with half-width clearance on either side.')

    def test_exact_parents_joint(self):
        with self.center() as center:
            parents = []
            for station, polygons in (('A', OUTER_BANDS), ('B', MID_BRIDGE)):
                payload = encode_coverage(CoveragePayload(polygons))
                envelope = seal_envelope(station, 'shift-7', 'checked-fixture', DOMAIN, payload)
                accepted = accept_piece(center.catalog, envelope.to_json(), station)
                self.assertEqual(accepted.coverage, decode_coverage(payload))
                parents.append(accepted.piece_id)
            report = publish_head(center, *parents, RAIL)
            saved = read_report(center, report.report_id)
        self.scenario('n5.exact_parents_joint', {'A': OUTER_BANDS, 'B': MID_BRIDGE, 'width': 1},
                      [['3/2', '5/2']], endpoints(report.positions), tuple(parents), saved.parent_ids,
                      ['evidence/envelope.py', 'evidence/accept.py', 'analysis/coverage.py', 'reports/publish.py'],
                      'Neither parent fills height 2 alone. Together they fill it for x in [1,3] inclusive.')

    def test_zero_width(self):
        with self.center() as center:
            parents = self.pair(center)
            with self.assertRaisesRegex(ValueError, 'width must be positive') as rejected:
                publish_head(center, *parents, HeadRequest(0, 4, 0, 0, 2))
            self.scenario('n6', {'rail': [0, 4], 'width': 0},
                          'ValueError', type(rejected.exception).__name__, (0, 0), self.counts(center),
                          ['analysis/head.py', 'reports/publish.py'],
                          'A zero-width head falls outside the positive-width device contract.')

    def test_sloping_seam_and_raised_boundary(self):
        first = (((0, 0), (2, 0), (2, '3/2'), (0, '1/2')),)
        second = (((0, '3/2'), (2, '1/2'), (2, 2), (0, 2)),)
        raised = (((0, '7/4'), (2, '3/4'), (2, 2), (0, 2)),)
        request = HeadRequest(0, 2, 1, 0, 2)
        with self.center() as center:
            parents = self.pair(center, first, second)
            initial = publish_head(center, *parents, request)
            revised_piece = self.accept(center, 'B', raised, revision_id='r2')
            revised = publish_head(center, parents[0], revised_piece, request)
            initial_export = json.loads(export_report(read_report(center, initial.report_id)))
            revised_export = json.loads(export_report(read_report(center, revised.report_id)))
        self.assertEqual(initial.positions, (ClosedInterval('3/2', '3/2'),))
        self.assertEqual(revised.positions, ())
        self.scenario('n9', {'rail': [0, 2], 'width': 1, 'lower_edge_raise': '1/4'},
                      ([['3/2', '3/2']], []), (endpoints(initial.positions), endpoints(revised.positions)),
                      ([['3/2', '3/2']], []), (initial_export['positions'], revised_export['positions']),
                      ['analysis/edges.py', 'analysis/coverage.py', 'analysis/positions.py', 'reports/export.py'],
                      'Solve 1/2+x/2 >= 3/2-x/2 for x>=1, and the raised version for x>=5/4. Only the first span fits an entire width 1.')

    def test_band_boundary_crossing_and_separated_spans(self):
        rising = (((0, 0), (3, 0), (3, 2), (0, '1/2')),)
        with self.center() as center:
            parents = self.pair(center, rising, (rectangle(4, 6, 0, 1),))
            report = publish_head(center, *parents, HeadRequest(0, 6, '1/2', 0, 1))
        self.assertEqual(report.positions, (ClosedInterval('5/4', '11/4'), ClosedInterval('17/4', '23/4')))
