import sqlite3
from contextlib import contextmanager

from evidence.catalog import PieceCatalog


class ReportStore:
    def __init__(self, path, *, before_commit=None):
        self.connection = sqlite3.connect(path, isolation_level=None)
        self.connection.execute('PRAGMA foreign_keys = ON')
        self.catalog = PieceCatalog(self.connection)
        self.before_commit = before_commit

    def initialize(self):
        with self.write_transaction() as connection:
            self.catalog.initialize()
            connection.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    report_id INTEGER PRIMARY KEY,
                    first_piece_id TEXT NOT NULL REFERENCES accepted_pieces(piece_id),
                    second_piece_id TEXT NOT NULL REFERENCES accepted_pieces(piece_id),
                    request TEXT NOT NULL,
                    positions TEXT NOT NULL,
                    CHECK (first_piece_id <> second_piece_id)
                )
            ''')
            connection.execute('''
                CREATE TABLE IF NOT EXISTS report_receipts (
                    receipt_id TEXT PRIMARY KEY NOT NULL,
                    report_id INTEGER NOT NULL UNIQUE REFERENCES reports(report_id)
                )
            ''')
        return self

    @contextmanager
    def write_transaction(self, *, before_commit=None):
        connection = self.connection
        connection.execute('BEGIN IMMEDIATE')
        try:
            yield connection
            if before_commit is not None:
                before_commit(connection)
            connection.execute('COMMIT')
        except BaseException:
            if connection.in_transaction:
                connection.execute('ROLLBACK')
            raise

    def close(self):
        self.connection.close()

    def __enter__(self):
        try:
            return self.initialize()
        except BaseException:
            self.close()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
