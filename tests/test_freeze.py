from fractions import Fraction

from calibration.corrections import record
from calibration.repository import RevisionRepository
from calibration.revisions import RevisionRef
from issue.freeze import issue
from issue.repository import FrozenPieceRepository
from issue.transport import decode_envelope
from review.repository import IntakeRepository
from review.slope_range import SlopeRange, marginal_slope_ranges, supports_relative_readings
from strips.catalog import register, resolve_strip
from tests import LabTestCase, sample


class FreezeTests(LabTestCase):
    def test_issue_fixed_revision(self):
        rows = [(0, 1, 2, 3)]
        initial, wire = self.frozen(rows)
        piece = decode_envelope(wire)
        self.assertEqual(issue(self.source, initial), wire)
        self.assertEqual(FrozenPieceRepository(self.source).read(piece.piece_id), wire)
        self.assertEqual((piece.strip_id, piece.revision_id), (self.strip, initial.revision_id))
        revision = RevisionRepository(self.source).get(initial)
        self.assertEqual(revision.batch.rows, ((0, 1, 2, 3),))
        self.assertIsNone(revision.previous)
        self.assertEqual(RevisionRepository(self.source).get_current(self.strip), revision)

    def test_station_order(self):
        _, wire = self.frozen([(0, 1, 2, 3)])
        for station_map in (resolve_strip(self.source, self.strip).station_map, decode_envelope(wire).station_map):
            self.assertEqual(station_map.names, self.names)
            self.assertEqual(station_map.positions, (0, 1, 2, 3))
        bad = [
            (('P4', 'P4', 'P1', 'P3'), (0, 1, 2, 3)),
            (self.names, (0, 2, 1, 3)),
            (self.names, (0, True, 2, 3)),
        ]
        for names, positions in bad:
            with self.subTest(names=names, positions=positions):
                with self.assertRaises(ValueError):
                    register(self.source, 'rejected', names, positions)
                with self.assertRaises(KeyError):
                    resolve_strip(self.source, 'rejected')
        with self.assertRaises(ValueError):
            register(self.source, self.strip, self.names[::-1])
        self.assertEqual(resolve_strip(self.source, self.strip).station_map.names, self.names)

    def test_joint_evidence(self):
        data = sample('boundaries')
        initial, _, first = self.accepted(data['simplex'])
        correction, _, second = self.accepted(data['cube'], initial)
        repository = RevisionRepository(self.source)
        self.assertEqual(repository.get(initial).batch.rows, tuple(map(tuple, data['simplex'])))
        self.assertEqual(repository.get(correction).batch.rows, tuple(map(tuple, data['cube'])))
        self.take_source_offline()
        intake = IntakeRepository(self.center)
        expected_edges = tuple(SlopeRange(Fraction(-1, d), Fraction(1, d)) for d in (1, 2, 3, 1, 2, 1))
        self.assertEqual(marginal_slope_ranges(intake.get(first)), expected_edges)
        self.assertEqual(marginal_slope_ranges(intake.get(second)), expected_edges)
        # The simplex has sum of relative coordinates <= 1. The cube contains
        # the witness with anchor 0 and the remaining coordinates in [0, 1].
        target = data['cube_only_target']
        self.assertFalse(supports_relative_readings(intake.get(first), target))
        self.assertTrue(supports_relative_readings(intake.get(second), target))

    def assert_unchanged(self, revision, wire, count=1):
        repository = RevisionRepository(self.source)
        self.assertEqual(repository.get_current(self.strip).ref, revision)
        self.assertEqual(self.source.execute('SELECT count(*) FROM scenario_revisions').fetchone()[0], count)
        self.assertEqual(issue(self.source, revision), wire)

    def test_reject_partial_scenario(self):
        initial, wire = self.frozen([(0, 1, 2, 3)])
        with self.assertRaises(ValueError):
            record(self.source, self.strip, [(0, 2, 4)], initial)
        self.assert_unchanged(initial, wire)

    def test_mixed_batch(self):
        initial, wire = self.frozen([(0, 1, 2, 3)])
        with self.assertRaises(ValueError):
            record(self.source, self.strip, [(0, 2, 4, 6), (0, 1, 2)], initial)
        self.assert_unchanged(initial, wire)

    def test_scenario_input_boundaries(self):
        initial, wire = self.frozen([(0, 1, 2, 3)])
        other = register(self.source, 'HC-other', self.names)
        foreign = record(self.source, other, [(0, 1, 2, 3)])
        for rows in ([], [(0, 1, 2, 3)] * 17, [(None, 1, 2, 3)],
                     [('1/0', 1, 2, 3)], [(True, 1, 2, 3)], [(0.1, 1, 2, 3)]):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    record(self.source, self.strip, rows, initial)
                self.assert_unchanged(initial, wire, 2)
        with self.assertRaises(ValueError):
            record(self.source, self.strip, [(0, 2, 4, 6)], foreign)
        self.assert_unchanged(initial, wire, 2)
        self.assertEqual(RevisionRepository(self.source).get_current(other).ref, foreign)

    def test_unknown_revision(self):
        missing = RevisionRef(self.strip, 'missing-revision')
        with self.assertRaises(KeyError) as caught:
            issue(self.source, missing)
        self.assertEqual(caught.exception.args, (missing,))
        self.assertEqual(self.source.execute('SELECT count(*) FROM frozen_pieces').fetchone()[0], 0)
