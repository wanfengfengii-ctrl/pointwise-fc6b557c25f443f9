from archive.history import read
from archive.publication import publish
from calibration.repository import RevisionRepository
from issue.freeze import issue
from issue.repository import FrozenPieceRepository
from issue.transport import decode_envelope
from review.repository import IntakeRepository
from strips.catalog import resolve_strip
from tests import LabTestCase, ZERO


class ReinitializeTests(LabTestCase):
    def test_source_reinitialize(self):
        original, wire = self.frozen([(0, 1, 2, 3)])
        correction, changed_wire = self.frozen([(0, 2, 4, 6)], original)
        self.source.close()
        self.source = self.connect(self.source_path)
        self.initialize_source()
        self.initialize_source()
        self.assertEqual(resolve_strip(self.source, self.strip).station_map.names, self.names)
        revisions = RevisionRepository(self.source)
        self.assertEqual(revisions.get(original).batch.rows, ((0, 1, 2, 3),))
        self.assertEqual(revisions.get_current(self.strip).ref, correction)
        self.assertEqual(revisions.get(correction).previous, original)
        for revision, frozen in ((original, wire), (correction, changed_wire)):
            self.assertEqual(issue(self.source, revision), frozen)
            self.assertEqual(FrozenPieceRepository(self.source).read(decode_envelope(frozen).piece_id), frozen)

    def test_center_reinitialize(self):
        initial, wire, first = self.accepted([(0, 1, 2, 3)])
        old = publish(self.center, first, ZERO, 1)
        _, corrected_wire, second = self.accepted([(0, 2, 4, 6)], initial)
        new = publish(self.center, second, ZERO, 1)
        self.take_source_offline()
        self.reopen_center()
        self.initialize_center()
        self.initialize_center()
        for intake, original_wire, publication in ((first, wire, old), (second, corrected_wire, new)):
            self.assertEqual(IntakeRepository(self.center).get(intake).envelope, decode_envelope(original_wire))
            self.assertEqual(read(self.center, publication.report.report_id), publication)
        self.assertEqual(self.intake_count(), 2)
        self.assertEqual(self.publication_counts(), (2, 2))
        replayed_request = publish(self.center, first, ZERO, 1)
        self.assertEqual(replayed_request.report.bounds, old.report.bounds)
        self.assertEqual(replayed_request.report.piece_id, old.report.piece_id)
        self.assertTrue(replayed_request.report.exempt)
        self.assertEqual(self.publication_counts(), (3, 3))
