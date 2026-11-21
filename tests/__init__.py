import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.repository import ArchiveRepository
from calibration.corrections import record
from calibration.repository import RevisionRepository
from issue.freeze import issue
from issue.repository import FrozenPieceRepository
from review.intake import receive
from review.repository import IntakeRepository
from strips.catalog import register
from strips.repository import StripRepository


SAMPLES = Path(__file__).resolve().parents[1] / 'samples'
ZERO = (0, 0, 0, 0)


def sample(name: str) -> dict:
    return json.loads((SAMPLES / f'{name}.json').read_text(encoding='utf-8'))


class LabTestCase(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix='strip-tests-')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.source_path = self.directory / 'source.sqlite'
        self.center_path = self.directory / 'center.sqlite'
        self.source = self.connect(self.source_path)
        self.center = self.connect(self.center_path)
        self.initialize_source()
        self.initialize_center()
        self.names = ('P4', 'P2', 'P1', 'P3')
        self.strip = register(self.source, 'HC-17', self.names, (0, 1, 2, 3))

    def connect(self, path):
        db = sqlite3.connect(path)
        self.addCleanup(db.close)
        db.execute('PRAGMA foreign_keys = ON')
        return db

    def initialize_source(self):
        StripRepository(self.source).initialize()
        RevisionRepository(self.source).initialize()
        FrozenPieceRepository(self.source).initialize()

    def initialize_center(self):
        IntakeRepository(self.center).initialize()
        ArchiveRepository(self.center).initialize()

    def reopen_center(self):
        self.center.close()
        self.center = self.connect(self.center_path)

    def take_source_offline(self):
        self.source.close()
        self.source_path.unlink()

    def frozen(self, rows, previous=None):
        revision = record(self.source, self.strip, rows, previous)
        return revision, issue(self.source, revision)

    def accepted(self, rows, previous=None):
        revision, wire = self.frozen(rows, previous)
        return revision, wire, receive(self.center, wire)

    def publication_counts(self):
        return (
            self.center.execute('SELECT count(*) FROM trend_reports').fetchone()[0],
            self.center.execute('SELECT count(*) FROM first_receipts').fetchone()[0],
        )

    def intake_count(self):
        return self.center.execute('SELECT count(*) FROM accepted_calibrations').fetchone()[0]
