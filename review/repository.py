import sqlite3
from dataclasses import dataclass
from uuid import uuid4

from issue.envelope import V1Envelope
from issue.transport import decode_envelope, encode_envelope


@dataclass(frozen=True, slots=True)
class AcceptedCalibration:
    intake_ref: str
    envelope: V1Envelope


class IntakeRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def initialize(self) -> None:
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS accepted_calibrations (
                intake_ref TEXT PRIMARY KEY NOT NULL,
                piece_id TEXT UNIQUE NOT NULL,
                wire TEXT NOT NULL
            )
        ''')

    def accept(self, envelope: V1Envelope) -> str:
        wire = encode_envelope(envelope)
        self.db.execute('BEGIN IMMEDIATE')
        with self.db:
            prior = self.db.execute('''
                SELECT intake_ref, wire FROM accepted_calibrations WHERE piece_id = ?
            ''', (envelope.piece_id,)).fetchone()
            if prior is not None:
                if wire != prior[1]:
                    raise ValueError('piece identity already has a different accepted snapshot')
                return prior[0]
            intake_ref = f'intake-{uuid4().hex}'
            self.db.execute('''
                INSERT INTO accepted_calibrations (intake_ref, piece_id, wire) VALUES (?, ?, ?)
            ''', (intake_ref, envelope.piece_id, wire))
        return intake_ref

    def get(self, intake_ref: str) -> AcceptedCalibration:
        if not isinstance(intake_ref, str) or not intake_ref.strip():
            raise ValueError('intake reference must be a nonempty string')
        row = self.db.execute('''
            SELECT wire FROM accepted_calibrations WHERE intake_ref = ?
        ''', (intake_ref,)).fetchone()
        if row is None:
            raise KeyError(intake_ref)
        return AcceptedCalibration(intake_ref, decode_envelope(row[0]))
