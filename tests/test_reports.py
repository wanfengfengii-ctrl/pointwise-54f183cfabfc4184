import json
import sqlite3

from demo import MID_BRIDGE, OUTER_BANDS, RAIL, rectangle
from reports.export import export_report
from reports.history import read_report
from reports.publish import publish_head
from reports.receipts import get_report_receipt
from tests import ProjectCase, endpoints


class ReportTests(ProjectCase):
    def test_commit_failure_rolls_back(self):
        with self.center() as center:
            parents = self.pair(center)
            old = publish_head(center, *parents, RAIL)
        staged = []

        def deny_commit(connection):
            staged.append(connection.execute('''
                SELECT r.report_id, f.receipt_id
                FROM reports AS r JOIN report_receipts AS f USING (report_id)
                ORDER BY r.report_id DESC LIMIT 1
            ''').fetchone())

            def authorizer(action, first, second, database, source):
                if action == sqlite3.SQLITE_TRANSACTION and first == 'COMMIT':
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK

            connection.set_authorizer(authorizer)

        with self.center(before_commit=deny_commit) as center:
            with self.assertRaises(sqlite3.DatabaseError) as failure:
                publish_head(center, *parents, RAIL)
            self.assertEqual(failure.exception.sqlite_errorcode, sqlite3.SQLITE_AUTH)
            self.assertFalse(center.connection.in_transaction)
        self.assertEqual(len(staged), 1)
        candidate, receipt_id = staged[0]
        self.assertNotEqual(candidate, old.report_id)
        self.assertEqual(receipt_id, f'head:{candidate}')
        with self.center() as center:
            with self.assertRaises(LookupError):
                read_report(center, candidate)
            with self.assertRaises(LookupError):
                get_report_receipt(center, candidate)
            saved = read_report(center, old.report_id)
            counts = self.counts(center)
        self.scenario('n7', {'staged': [candidate, receipt_id], 'old_report': old.report_id},
                      sqlite3.SQLITE_AUTH, failure.exception.sqlite_errorcode, ((1, 1), old), (counts, saved),
                      ['reports/store.py', 'reports/publish.py', 'reports/history.py', 'reports/receipts.py'],
                      'SQLite denies the actual COMMIT after both inserts. The old report and receipt are the only rows after reopen.')

    def test_correction_reopen_preserves_history(self):
        with self.center() as center:
            first, second = self.pair(center, OUTER_BANDS, MID_BRIDGE)
            old = publish_head(center, first, second, RAIL)
            corrected = self.accept(center, 'B', (rectangle(0, 4, '1/2', '3/2'),), revision_id='r2')
            new = publish_head(center, first, corrected, RAIL)
        with self.center() as center:
            restored_old = read_report(center, old.report_id)
            restored_new = read_report(center, new.report_id)
            self.assertEqual((restored_old, restored_new), (old, new))
            self.assertEqual((get_report_receipt(center, old.report_id), get_report_receipt(center, new.report_id)), (old.receipt, new.receipt))
            self.assertNotEqual(old.receipt, new.receipt)
            self.assertNotEqual(second, corrected)
            old_export = json.loads(export_report(restored_old))
            new_export = json.loads(export_report(restored_new))
            unknown_id = max(old.report_id, new.report_id) + 100
            with self.assertRaises(LookupError) as missing:
                read_report(center, unknown_id)
            counts = self.counts(center)
        self.scenario('n8', {'old_bridge': [1, 3], 'new_bridge': [0, 4], 'width': 1},
                      ([['3/2', '5/2']], [['1/2', '7/2']]),
                      (endpoints(restored_old.positions), endpoints(restored_new.positions)),
                      ([first, second], [first, corrected], old.receipt.receipt_id, new.receipt.receipt_id),
                      (old_export['parent_ids'], new_export['parent_ids'], old_export['receipt']['receipt_id'], new_export['receipt']['receipt_id']),
                      ['evidence/issue.py', 'reports/publish.py', 'reports/history.py', 'reports/export.py'],
                      'The original and corrected bridges fill spans [1,3] and [0,4], respectively. Each issuance retains its selected parents and receipt.')
        self.scenario('n8.unknown_report', {'missing_id': unknown_id, 'existing_ids': [old.report_id, new.report_id]},
                      'LookupError', type(missing.exception).__name__, (2, 2), counts,
                      ['reports/history.py', 'reports/receipts.py'],
                      'Only the two successful issues have report numbers and receipts.')
