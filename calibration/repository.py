import json
import sqlite3
from fractions import Fraction

from calibration.revisions import RevisionRef, ScenarioRevision
from calibration.scenarios import ScenarioBatch


class RevisionRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def initialize(self) -> None:
        self.db.execute('BEGIN IMMEDIATE')
        with self.db:
            self.db.execute('''
                CREATE TABLE IF NOT EXISTS scenario_revisions (
                    revision_id TEXT PRIMARY KEY NOT NULL,
                    strip_id TEXT NOT NULL REFERENCES strips(strip_id),
                    previous_id TEXT REFERENCES scenario_revisions(revision_id),
                    scenarios TEXT NOT NULL
                )
            ''')
            self.db.execute('''
                CREATE TABLE IF NOT EXISTS current_revisions (
                    strip_id TEXT PRIMARY KEY NOT NULL REFERENCES strips(strip_id),
                    revision_id TEXT NOT NULL REFERENCES scenario_revisions(revision_id)
                )
            ''')

    def append(self, revision: ScenarioRevision) -> RevisionRef:
        ref, previous = revision.ref, revision.previous
        payload = json.dumps([[str(value) for value in row] for row in revision.batch.rows])
        self.db.execute('BEGIN IMMEDIATE')
        with self.db:
            if previous is not None:
                if previous.strip_id != ref.strip_id:
                    raise ValueError('predecessor belongs to another strip')
                self.get(previous)
            self.db.execute('''
                INSERT INTO scenario_revisions (revision_id, strip_id, previous_id, scenarios)
                VALUES (?, ?, ?, ?)
            ''', (ref.revision_id, ref.strip_id, previous.revision_id if previous else None, payload))
            self.db.execute('''
                INSERT INTO current_revisions (strip_id, revision_id) VALUES (?, ?)
                ON CONFLICT(strip_id) DO UPDATE SET revision_id = excluded.revision_id
            ''', (ref.strip_id, ref.revision_id))
        return ref

    def get(self, ref: RevisionRef) -> ScenarioRevision:
        if not isinstance(ref, RevisionRef):
            raise ValueError('expected a revision reference')
        row = self.db.execute('''
            SELECT previous_id, scenarios FROM scenario_revisions WHERE revision_id = ? AND strip_id = ?
        ''', (ref.revision_id, ref.strip_id)).fetchone()
        if row is None:
            raise KeyError(ref)
        previous_id, scenarios = row
        previous = RevisionRef(ref.strip_id, previous_id) if previous_id is not None else None
        batch = ScenarioBatch(tuple(tuple(map(Fraction, values)) for values in json.loads(scenarios)))
        return ScenarioRevision(ref, previous, batch)

    def get_current(self, strip_id: str) -> ScenarioRevision | None:
        row = self.db.execute('SELECT revision_id FROM current_revisions WHERE strip_id = ?', (strip_id,)).fetchone()
        if row is None:
            return None
        return self.get(RevisionRef(strip_id, row[0]))
