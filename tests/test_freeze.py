from fractions import Fraction

from demo import DOMAIN, GATE, IDENTITY, rectangle
from evidence.issue import issue_piece
from evidence.payload import decode_coverage
from intake.batches import freeze_batch, get_batch_label, register_batch
from intake.frames import ScanFrame
from intake.receipts import get_freeze_receipt
from intake.revisions import get_revision
from intake.store import StationStore
from quality.calibration import AffineCalibration
from quality.disposition import evaluate_revision
from tests import ProjectCase


class FreezeTests(ProjectCase):
    def test_reinitialize_preserves_batch_and_frozen_data(self):
        path = self.root / 'a.sqlite'
        original_polygons = (rectangle(1, 2, 0, 1),)
        with StationStore(path, 'A') as store:
            register_batch(store, 'shift', 'Original note')
            revision, receipt = freeze_batch(store, 'shift', 'r1', [ScanFrame('first', original_polygons[0], 2)], IDENTITY, GATE, DOMAIN)
            register_batch(store, 'shift', 'Operator correction')
        calibration = AffineCalibration(2, 0, 1, 0, 1, 1)
        frames = [ScanFrame('pass', rectangle(0, 1, 0, 1), 1), ScanFrame('fail', rectangle(5, 6, 0, 1), 0)]
        with StationStore(path, 'A') as store:
            store.initialize()
            original = get_revision(store, 'r1')
            original_receipt = get_freeze_receipt(store, 'r1')
            self.assertEqual(original, revision)
            self.assertEqual(original_receipt, receipt)
            self.scenario('n1.reinitialize_preserves_batch', {'station': 'A', 'batch': 'shift', 'revision': 'r1'},
                          'Operator correction', get_batch_label(store, 'shift'),
                          ('first', 2, 'freeze:r1', 1),
                          (original.frames[0].frame_id, original.frames[0].reading, original_receipt.receipt_id, original_receipt.frame_count),
                          ['intake/store.py', 'intake/batches.py', 'intake/revisions.py', 'intake/receipts.py'],
                          'Compare the reopened label and the saved frame and receipt with the submitted values.')
            second, second_receipt = freeze_batch(store, 'shift', 'r2', frames, calibration, GATE, DOMAIN)
            with self.assertRaisesRegex(ValueError, 'revision already exists'):
                freeze_batch(store, 'unrelated', 'r1', frames, calibration, GATE, DOMAIN)
            with self.assertRaises(LookupError):
                get_batch_label(store, 'unrelated')
            self.assertEqual(get_batch_label(store, 'shift'), 'Operator correction')
            self.assertEqual(get_revision(store, 'r1'), revision)
            self.assertEqual(second_receipt.frame_count, 2)
            dispositions = evaluate_revision(second)
            issued = decode_coverage(issue_piece(store, 'r2').payload)
        self.scenario('n1', {'affine': [2, 0, 1, 0, 1, 1], 'readings': [1, 0]},
                      [True, False], [item.accepted for item in dispositions],
                      (rectangle(1, 3, 1, 2),), issued.polygons,
                      ['intake/batches.py', 'quality/disposition.py', 'evidence/issue.py'],
                      'Only the reading 1 enters the gate. Transform its four corners by x=2x+1 and y=y+1.')

    def test_frame_association(self):
        far, near = rectangle(8, 9, 0, 1), rectangle(0, 1, 0, 1)
        with StationStore(self.root / 'a.sqlite', 'A') as store:
            frames = (ScanFrame('first-far', far, 2), ScanFrame('second-near', near, '1/2'))
            freeze_batch(store, 'shift', 'r1', frames, IDENTITY, GATE, DOMAIN)
            saved = get_revision(store, 'r1')
            self.assertEqual(saved.frames, (ScanFrame('first-far', far, 2), ScanFrame('second-near', near, Fraction(1, 2))))
            dispositions = evaluate_revision(saved)
            issued = issue_piece(store, 'r1')
        self.assertNotIn('first-far', issued.to_json())
        self.assertNotIn('second-near', issued.to_json())
        self.scenario('n1.frame_association', {'submitted_ids': ['first-far', 'second-near'], 'readings': [2, '1/2']},
                      [(1, 'first-far', True), (2, 'second-near', False)],
                      [(d.ordinal, d.frame_id, d.accepted) for d in dispositions],
                      (far,), decode_coverage(issued.payload).polygons,
                      ['intake/frames.py', 'intake/revisions.py', 'quality/disposition.py', 'evidence/issue.py'],
                      'The original first frame alone meets the quality rule and is the more distant footprint.')

    def test_empty_coverage(self):
        with StationStore(self.root / 'a.sqlite', 'A') as store:
            revision, receipt = freeze_batch(store, 'shift', 'r1', [ScanFrame('rejected', rectangle(0, 1, 0, 1), 0)], IDENTITY, GATE, DOMAIN)
            piece = issue_piece(store, 'r1')
        self.assertEqual(receipt.frame_count, 1)
        self.scenario('n1.empty_coverage', {'reading': 0, 'gate': [1, 2]},
                      [False], [d.accepted for d in evaluate_revision(revision)],
                      (), decode_coverage(piece.payload).polygons,
                      ['quality/gates.py', 'quality/disposition.py', 'evidence/issue.py', 'evidence/payload.py'],
                      'Zero is below the lower quality boundary. The batch is valid with no eligible geometry.')

    def test_singular_calibration_and_unknown_revision(self):
        frames = [ScanFrame('f', rectangle(0, 1, 0, 1), 1)]
        with StationStore(self.root / 'a.sqlite', 'A') as store:
            revision, receipt = freeze_batch(store, 'shift', 'r1', frames, IDENTITY, GATE, DOMAIN)
            original_piece = issue_piece(store, 'r1')
            with self.assertRaisesRegex(ValueError, 'invertible') as denied:
                freeze_batch(store, 'shift', 'bad', frames, AffineCalibration(1, 0, 0, 0, 0, 0), GATE, DOMAIN)
            with self.assertRaises(LookupError):
                issue_piece(store, 'bad')
            with self.assertRaises(LookupError):
                get_freeze_receipt(store, 'bad')
            self.assertEqual(get_revision(store, 'r1'), revision)
            self.assertEqual(get_freeze_receipt(store, 'r1'), receipt)
            self.scenario('n2', {'attempt': 'x unchanged, y=0', 'revision': 'bad'},
                          'ValueError', type(denied.exception).__name__, original_piece, issue_piece(store, 'r1'),
                          ['quality/calibration.py', 'intake/batches.py', 'evidence/issue.py'],
                          'A map sending every y to zero is singular. The original immutable revision still issues the same piece.')

    def test_mirrored_control(self):
        frames = [ScanFrame('f', tuple(reversed(rectangle(0, 1, 0, 1))), 1)]
        with StationStore(self.root / 'a.sqlite', 'A') as store:
            revision, _ = freeze_batch(store, 'shift', 'mirror', frames, AffineCalibration(-1, 0, 4, 0, 1, 0), GATE, DOMAIN)
            with self.assertRaises(ValueError):
                freeze_batch(store, 'shift', 'singular', frames, AffineCalibration(0, 0, 4, 0, 1, 0), GATE, DOMAIN)
            pieces = decode_coverage(issue_piece(store, revision.revision_id).payload)
            self.assertEqual(get_revision(store, 'mirror'), revision)
        self.scenario('n2.mirrored_control', {'local': [0, 1, 0, 1], 'transform': 'x=4-x, y unchanged'},
                      rectangle(3, 4, 0, 1), evaluate_revision(revision)[0].footprint,
                      (rectangle(3, 4, 0, 1),), pieces.polygons,
                      ['quality/calibration.py', 'quality/footprints.py', 'evidence/issue.py'],
                      'The x endpoints map to 4 and 3, and the y endpoints retain their values.')
