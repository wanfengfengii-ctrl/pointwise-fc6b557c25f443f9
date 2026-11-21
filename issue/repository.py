import sqlite3

from calibration.revisions import RevisionRef


class FrozenPieceRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def initialize(self) -> None:
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS frozen_pieces (
                piece_id TEXT PRIMARY KEY NOT NULL,
                strip_id TEXT NOT NULL REFERENCES strips(strip_id),
                revision_id TEXT NOT NULL REFERENCES scenario_revisions(revision_id),
                wire TEXT NOT NULL,
                UNIQUE (strip_id, revision_id)
            )
        ''')

    def find_by_revision(self, revision: RevisionRef) -> str | None:
        row = self.db.execute('''
            SELECT wire FROM frozen_pieces WHERE strip_id = ? AND revision_id = ?
        ''', (revision.strip_id, revision.revision_id)).fetchone()
        return row[0] if row is not None else None

    def save_once(self, revision: RevisionRef, piece_id: str, wire: str) -> str:
        self.db.execute('BEGIN IMMEDIATE')
        with self.db:
            self.db.execute('''
                INSERT INTO frozen_pieces (piece_id, strip_id, revision_id, wire) VALUES (?, ?, ?, ?)
                ON CONFLICT(strip_id, revision_id) DO NOTHING
            ''', (piece_id, revision.strip_id, revision.revision_id, wire))
            row = self.db.execute('''
                SELECT wire FROM frozen_pieces WHERE strip_id = ? AND revision_id = ?
            ''', (revision.strip_id, revision.revision_id)).fetchone()
        return row[0]

    def read(self, piece_id: str) -> str:
        row = self.db.execute('SELECT wire FROM frozen_pieces WHERE piece_id = ?', (piece_id,)).fetchone()
        if row is None:
            raise KeyError(piece_id)
        return row[0]
