import sqlite3
from contextlib import contextmanager


def require_identifier(value, field):
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f'invalid {field}')
    return value


class StationStore:
    def __init__(self, path, station_id):
        self._station_id = require_identifier(station_id, 'station identity')
        self.connection = sqlite3.connect(path, isolation_level=None)
        self.connection.execute('PRAGMA foreign_keys = ON')

    @property
    def station_id(self):
        return self._station_id

    def initialize(self):
        with self.write_transaction() as connection:
            connection.execute('''
                CREATE TABLE IF NOT EXISTS station_meta (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    station_id TEXT NOT NULL
                )
            ''')
            connection.execute('''
                CREATE TABLE IF NOT EXISTS batches (
                    batch_id TEXT PRIMARY KEY NOT NULL,
                    label TEXT NOT NULL
                )
            ''')
            connection.execute('''
                CREATE TABLE IF NOT EXISTS revisions (
                    revision_id TEXT PRIMARY KEY NOT NULL,
                    batch_id TEXT NOT NULL REFERENCES batches(batch_id),
                    domain TEXT NOT NULL,
                    calibration TEXT NOT NULL,
                    quality_rule TEXT NOT NULL,
                    frames TEXT NOT NULL
                )
            ''')
            connection.execute('''
                CREATE TABLE IF NOT EXISTS freeze_receipts (
                    receipt_id TEXT PRIMARY KEY NOT NULL,
                    revision_id TEXT NOT NULL UNIQUE REFERENCES revisions(revision_id),
                    frame_count INTEGER NOT NULL CHECK (frame_count >= 0)
                )
            ''')
            connection.execute('''
                INSERT INTO station_meta (singleton, station_id) VALUES (1, ?)
                ON CONFLICT(singleton) DO NOTHING
            ''', (self.station_id,))
            saved = connection.execute('SELECT station_id FROM station_meta WHERE singleton = 1').fetchone()
            if saved != (self.station_id,):
                raise ValueError('station database belongs to another station')
        return self

    @contextmanager
    def write_transaction(self):
        connection = self.connection
        connection.execute('BEGIN IMMEDIATE')
        try:
            yield connection
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
