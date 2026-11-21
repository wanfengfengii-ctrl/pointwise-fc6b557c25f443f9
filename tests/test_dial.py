import json
from fractions import Fraction

from archive.history import ReportNotFound, read, read_dial
from archive.publication import PublicationError, publish, publish_dial
from issue.freeze import issue
from issue.transport import decode_envelope
from review.dial import dial_safe_intervals, validate_dial_request
from review.intake import receive
from review.repository import IntakeRepository
from tests import LabTestCase, sample


class DialTests(LabTestCase):
    def fixture(self):
        return sample('dial')

    def dial_pieces(self):
        data = self.fixture()
        first, first_wire, first_intake = self.accepted(data['cases'][0]['rows'])
        second, second_wire, second_intake = self.accepted(data['cases'][1]['rows'], first)
        return data, first, first_wire, first_intake, second, second_wire, second_intake

    def signed(self, intake, case, data=None):
        data = data or self.fixture()
        return publish_dial(self.center, intake, data['base'], data['direction'],
                            case['travel'], case['limit'])

    def test_fixture_initial(self):
        data, _, wire, intake, _, _, _ = self.dial_pieces()
        self.take_source_offline()
        for case in data['cases'][0]['requests']:
            result = self.signed(intake, case, data)
            expected = tuple((Fraction(a), Fraction(b)) for a, b in case['safe_intervals'])
            self.assertEqual(result.report.safe_intervals, expected)
            self.assertEqual(result.report.intake_ref, intake)
            self.assertEqual(result.report.piece_id, decode_envelope(wire).piece_id)
            self.assertEqual(result.receipt.piece_id, result.report.piece_id)
            self.assertEqual((result.receipt.report_id, result.receipt.receipt_id),
                             (result.report.report_id, result.report.receipt_id))

    def test_fixture_corrected(self):
        data, _, _, _, _, wire, intake = self.dial_pieces()
        self.take_source_offline()
        for case in data['cases'][1]['requests']:
            result = self.signed(intake, case, data)
            expected = tuple((Fraction(a), Fraction(b)) for a, b in case['safe_intervals'])
            self.assertEqual(result.report.safe_intervals, expected)
            self.assertEqual(result.report.piece_id, decode_envelope(wire).piece_id)

    def test_empty_set_signed(self):
        data, _, _, _, _, _, intake = self.dial_pieces()
        self.take_source_offline()
        case = next(item for item in data['cases'][1]['requests'] if item['safe_intervals'] == [])
        result = self.signed(intake, case, data)
        self.assertEqual(result.report.safe_intervals, ())

    def test_report_fields(self):
        data, _, _, intake, _, _, _ = self.dial_pieces()
        self.take_source_offline()
        result = self.signed(intake, data['cases'][0]['requests'][0], data)
        report = result.report
        self.assertEqual(report.base, tuple(map(Fraction, data['base'])))
        self.assertEqual(report.direction, tuple(map(Fraction, data['direction'])))
        self.assertEqual(report.travel, (Fraction(0), Fraction(2)))
        self.assertEqual(report.upper_limit, Fraction(0))
        self.assertIsInstance(report.safe_intervals, tuple)
        self.assertTrue(all(isinstance(item, tuple) and len(item) == 2
                            for item in report.safe_intervals))

    def test_read_back_and_reopen(self):
        data, _, _, intake, _, _, _ = self.dial_pieces()
        self.take_source_offline()
        first = self.signed(intake, data['cases'][0]['requests'][0], data)
        second = self.signed(intake, data['cases'][0]['requests'][1], data)
        self.reopen_center()
        self.initialize_center()
        self.center.execute('PRAGMA query_only = ON')
        for publication in (first, second):
            self.assertEqual(read_dial(self.center, publication.report.report_id), publication)

    def test_unknown_report_dial(self):
        missing = 'dial report / night 3'
        with self.assertRaises(ReportNotFound) as caught:
            read_dial(self.center, missing)
        self.assertEqual(caught.exception.report_id, missing)
        self.assertEqual(caught.exception.args, (missing,))
        with self.assertRaises(ValueError):
            read_dial(self.center, 7)

    def test_invalid_request(self):
        data, _, _, intake, _, _, _ = self.dial_pieces()
        self.take_source_offline()
        bad = [
            (intake, (0, 0, 0), data['direction'], (0, 2), 0),
            (intake, data['base'], data['direction'][:3], (0, 2), 0),
            (intake, data['base'], data['direction'], (2, 0), 0),
            (intake, data['base'], data['direction'], (0,), 0),
            (intake, data['base'], data['direction'], (0, 2), '1/0'),
            (intake, (0, 0, 0, True), data['direction'], (0, 2), 0),
            (intake, (0.5, 0, 0, 0), data['direction'], (0, 2), 0),
            ('', data['base'], data['direction'], (0, 2), 0),
        ]
        for args in bad:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    publish_dial(self.center, *args)
                self.assertEqual(self.dial_counts(), (0, 0))

    def test_unknown_intake(self):
        data = self.fixture()
        with self.assertRaises(KeyError):
            publish_dial(self.center, 'missing-intake', data['base'], data['direction'], (0, 2), 0)
        self.assertEqual(self.dial_counts(), (0, 0))

    def test_unusable_piece(self):
        data = self.fixture()
        _, wire = self.frozen([(0, 1, 2, 3)])
        payload = json.loads(wire)
        payload['body'] = {'stations': payload['body']['stations']}
        unusable = receive(self.center, json.dumps({**payload, 'piece_id': payload['piece_id'] + '-bare'}))
        self.take_source_offline()
        with self.assertRaises(ValueError):
            publish_dial(self.center, unusable, data['base'], data['direction'], (0, 2), 0)
        self.assertEqual(self.dial_counts(), (0, 0))

    def test_rollback_and_retry(self):
        data, _, _, intake, _, _, _ = self.dial_pieces()
        self.take_source_offline()
        self.center.executescript('''
            CREATE TABLE dial_check_parent (id INTEGER PRIMARY KEY);
            CREATE TABLE dial_check (
                parent_id INTEGER REFERENCES dial_check_parent(id) DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TEMP TRIGGER reject_at_commit AFTER INSERT ON main.dial_receipts
            BEGIN
                INSERT INTO dial_check(parent_id) VALUES (1);
            END;
        ''')
        with self.assertRaises(PublicationError) as caught:
            self.signed(intake, data['cases'][0]['requests'][0], data)
        import sqlite3
        self.assertIsInstance(caught.exception.__cause__, sqlite3.IntegrityError)
        self.assertFalse(self.center.in_transaction)
        self.reopen_center()
        self.assertEqual(self.dial_counts(), (0, 0))
        self.assertEqual(self.center.execute('SELECT count(*) FROM dial_check').fetchone()[0], 0)
        self.center.execute('DROP TRIGGER IF EXISTS reject_at_commit')
        result = self.signed(intake, data['cases'][0]['requests'][0], data)
        self.assertEqual(self.dial_counts(), (1, 1))
        self.assertEqual(read_dial(self.center, result.report.report_id), result)

    def test_preserves_v1(self):
        first, first_wire, first_intake = self.accepted([(0, 1, 2, 3)])
        old = publish(self.center, first_intake, (0, 0, 0, 0), 1)
        data = self.fixture()
        dial = self.signed(first_intake, data['cases'][0]['requests'][0], data)
        self.take_source_offline()
        self.assertEqual(read(self.center, old.report.report_id), old)
        self.assertEqual(read_dial(self.center, dial.report.report_id), dial)
        self.assertEqual(self.publication_counts(), (1, 1))
        self.assertEqual(self.dial_counts(), (1, 1))

    def dial_counts(self):
        return (
            self.center.execute('SELECT count(*) FROM dial_reports').fetchone()[0],
            self.center.execute('SELECT count(*) FROM dial_receipts').fetchone()[0],
        )

    def test_matches_v1_pointwise(self):
        data, _, _, intake, _, _, _ = self.dial_pieces()
        self.take_source_offline()
        calibration = IntakeRepository(self.center).get(intake)
        request = validate_dial_request(intake, data['base'], data['direction'], (0, 2), 0)
        intervals = dial_safe_intervals(calibration, request)
        for tick, expected in data['cases'][0]['point_upper'].items():
            tick = Fraction(tick)
            safe = any(low <= tick <= high for low, high in intervals)
            self.assertEqual(safe, Fraction(expected) <= 0, tick)

    def test_corrected_reclaim_by_original_id(self):
        data, first, first_wire, first_intake, second, second_wire, second_intake = self.dial_pieces()
        initial_request = data['cases'][0]['requests'][0]
        corrected_request = next(item for item in data['cases'][1]['requests']
                                 if item['travel'] == [0, 2])
        self.take_source_offline()
        initial = self.signed(first_intake, initial_request, data)
        corrected = self.signed(second_intake, corrected_request, data)
        self.reopen_center()
        self.initialize_center()
        self.center.execute('PRAGMA query_only = ON')
        for signed, wire, request in (
            (initial, first_wire, initial_request),
            (corrected, second_wire, corrected_request),
        ):
            claimed = read_dial(self.center, signed.report.report_id)
            self.assertEqual(claimed, signed)
            self.assertEqual(claimed.report.piece_id, decode_envelope(wire).piece_id)
            self.assertEqual(claimed.report.revision_id, decode_envelope(wire).revision_id)
            self.assertEqual(claimed.receipt.piece_id, claimed.report.piece_id)
            self.assertEqual(claimed.receipt.report_id, claimed.report.report_id)
            self.assertEqual(claimed.report.intake_ref, signed.report.intake_ref)
            self.assertEqual([str(v) for v in claimed.report.travel], [str(v) for v in request['travel']])
        self.assertNotEqual(initial.report.piece_id, corrected.report.piece_id)
        self.assertNotEqual(initial.report.revision_id, corrected.report.revision_id)
