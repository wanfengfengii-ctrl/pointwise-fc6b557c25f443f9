import sqlite3
from fractions import Fraction

from archive.history import ReportNotFound, read
from archive.publication import PublicationError, publish
from calibration.repository import RevisionRepository
from issue.freeze import issue
from issue.transport import decode_envelope
from review.repository import IntakeRepository
from review.slope_range import supports_relative_readings
from tests import LabTestCase, ZERO


class ArchiveTests(LabTestCase):
    def deny_receipt_writes(self):
        self.center.execute('''
            CREATE TEMP TRIGGER reject_receipt BEFORE INSERT ON main.first_receipts
            BEGIN
                SELECT RAISE(ABORT, 'receipt write rejected');
            END
        ''')

    def test_publish_rollback(self):
        _, _, intake = self.accepted([(0, 1, 2, 3)])
        self.take_source_offline()
        self.center.executescript('''
            CREATE TABLE receipt_check_parent (id INTEGER PRIMARY KEY);
            CREATE TABLE receipt_check (
                parent_id INTEGER REFERENCES receipt_check_parent(id) DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TEMP TRIGGER reject_at_commit AFTER INSERT ON main.first_receipts
            BEGIN
                INSERT INTO receipt_check(parent_id) VALUES (1);
            END;
        ''')
        with self.assertRaises(PublicationError) as caught:
            publish(self.center, intake, ZERO, 1)
        self.assertIsInstance(caught.exception.__cause__, sqlite3.IntegrityError)
        self.assertFalse(self.center.in_transaction)
        self.reopen_center()
        self.assertEqual(self.publication_counts(), (0, 0))
        self.assertEqual(self.center.execute('SELECT count(*) FROM receipt_check').fetchone()[0], 0)

    def test_receipt_write_failure(self):
        _, _, intake = self.accepted([(0, 1, 2, 3)])
        saved = publish(self.center, intake, ZERO, 1)
        self.deny_receipt_writes()
        with self.assertRaises(PublicationError) as caught:
            publish(self.center, intake, ('1/7', 0, 0, 0), 1)
        self.assertIn('receipt write rejected', str(caught.exception.__cause__))
        self.reopen_center()
        self.assertEqual(self.publication_counts(), (1, 1))
        self.assertEqual(read(self.center, saved.report.report_id), saved)

    def test_retry_after_reopen(self):
        _, wire, intake = self.accepted([(0, 1, 2, 3)])
        self.take_source_offline()
        self.deny_receipt_writes()
        with self.assertRaises(PublicationError):
            publish(self.center, intake, ZERO, 1)
        self.reopen_center()
        self.assertEqual(self.publication_counts(), (0, 0))
        result = publish(self.center, intake, ZERO, 1)
        self.assertEqual(result.report.piece_id, decode_envelope(wire).piece_id)
        self.assertEqual(self.publication_counts(), (1, 1))
        self.assertEqual(read(self.center, result.report.report_id), result)

    def test_correction_preserves_report(self):
        first, old_wire, old_intake = self.accepted([(0, 1, 2, 3)])
        old = publish(self.center, old_intake, ZERO, 1)
        second, new_wire, new_intake = self.accepted([(0, 2, 4, 6)], first)
        self.take_source_offline()
        new = publish(self.center, new_intake, ZERO, 1)
        self.reopen_center()
        for signed, expected, exempt, revision, wire in (
            (old, (1, 1), True, first, old_wire), (new, (2, 2), False, second, new_wire),
        ):
            claimed = read(self.center, signed.report.report_id)
            self.assertEqual(claimed, signed)
            self.assertEqual((claimed.report.bounds.lower, claimed.report.bounds.upper), expected)
            self.assertIs(claimed.report.exempt, exempt)
            self.assertEqual(claimed.report.revision_id, revision.revision_id)
            self.assertEqual(claimed.report.piece_id, decode_envelope(wire).piece_id)
        self.assertNotEqual(new.report.piece_id, old.report.piece_id)

    def test_equal_domain_lineage(self):
        first, first_wire, first_intake = self.accepted([(0, 1, 2, 3)])
        second, second_wire, second_intake = self.accepted([(5, 6, 7, 8)], first)
        revisions = RevisionRepository(self.source)
        self.assertEqual(revisions.get(second).previous, first)
        self.assertEqual(revisions.get(first).batch.rows, ((0, 1, 2, 3),))
        self.assertEqual(revisions.get(second).batch.rows, ((5, 6, 7, 8),))
        self.assertEqual(revisions.get_current(self.strip).ref, second)
        self.take_source_offline()
        for revision, wire, intake in ((first, first_wire, first_intake), (second, second_wire, second_intake)):
            accepted = IntakeRepository(self.center).get(intake)
            self.assertTrue(supports_relative_readings(accepted, (1, 2, 3)))
            self.assertFalse(supports_relative_readings(accepted, (1, 2, 4)))
            publication = publish(self.center, intake, ZERO, 1)
            self.assertEqual((publication.report.bounds.lower, publication.report.bounds.upper), (1, 1))
            self.assertEqual(publication.report.revision_id, revision.revision_id)
            self.assertEqual(publication.report.piece_id, decode_envelope(wire).piece_id)
        self.assertNotEqual(first, second)
        self.assertNotEqual(first_intake, second_intake)
        self.assertNotEqual(decode_envelope(first_wire).piece_id, decode_envelope(second_wire).piece_id)

    def test_reissue_old_revision(self):
        first, old_wire = self.frozen([(0, 1, 2, 3)])
        second, new_wire = self.frozen([(5, 6, 7, 8)], first)
        third, _ = self.frozen([(0, 3, 6, 9)], first)
        self.assertEqual(RevisionRepository(self.source).get_current(self.strip).ref, third)
        self.assertEqual(issue(self.source, first), old_wire)
        self.assertEqual(issue(self.source, second), new_wire)
        self.assertEqual(decode_envelope(issue(self.source, first)).revision_id, first.revision_id)
        self.assertEqual(self.source.execute('SELECT count(*) FROM frozen_pieces').fetchone()[0], 3)

    def test_first_receipt(self):
        first, _, old_intake = self.accepted([(0, 1, 2, 3)])
        _, _, new_intake = self.accepted([(0, 2, 4, 6)], first)
        self.take_source_offline()
        old = publish(self.center, old_intake, (1, 1, 1, 1), '6/7')
        new = publish(self.center, new_intake, (0, '1/7', '2/7', '3/7'), '15/7')
        self.assertEqual(new.report.bounds.upper, Fraction(15, 7))
        self.assertNotEqual(old.receipt.receipt_id, new.receipt.receipt_id)
        self.reopen_center()
        self.center.execute('PRAGMA query_only = ON')
        for publication in (new, old, new, old):
            self.assertEqual(read(self.center, publication.report.report_id), publication)
        self.assertEqual(self.publication_counts(), (2, 2))
        self.assertEqual(self.center.total_changes, 0)

    def test_unknown_report(self):
        missing = 'not signed / night 2'
        with self.assertRaises(ReportNotFound) as caught:
            read(self.center, missing)
        self.assertEqual(caught.exception.report_id, missing)
        self.assertEqual(caught.exception.args, (missing,))
        self.assertEqual(self.publication_counts(), (0, 0))
