import json
from fractions import Fraction

from archive.publication import publish
from issue.transport import decode_envelope
from review.intake import receive
from review.slopes import pair_slopes, third_smallest_slope
from tests import LabTestCase, ZERO, sample


class ReviewTests(LabTestCase):
    def assert_result(self, publication, wire, intake, expected, exempt):
        report = publication.report
        piece = decode_envelope(wire)
        self.assertEqual((report.bounds.lower, report.bounds.upper), expected, 'COMMON_CALIBRATION_RANGE')
        self.assertIs(report.exempt, exempt)
        self.assertEqual((report.intake_ref, report.piece_id, report.revision_id),
                         (intake, piece.piece_id, piece.revision_id))
        self.assertEqual((publication.receipt.piece_id, publication.receipt.report_id, publication.receipt.receipt_id),
                         (report.piece_id, report.report_id, report.receipt_id))

    def test_threshold_equality(self):
        _, wire, received = self.accepted([(0, 1, 2, 3)])
        self.assertEqual(receive(self.center, wire), received)
        self.take_source_offline()
        signed = publish(self.center, received, ZERO, 1)
        self.assert_result(signed, wire, received, (1, 1), True)
        self.assertEqual(signed.report.offsets, ZERO)
        self.assertEqual(signed.report.upper_limit, 1)

    def test_point_offsets(self):
        data = sample('boundaries')
        _, wire, received = self.accepted(data['zero'])
        self.take_source_offline()
        uneven = publish(self.center, received, data['nonuniform_offsets'], 0)
        actual_slopes = pair_slopes(decode_envelope(wire).station_map, data['nonuniform_offsets'])
        self.assertEqual(actual_slopes, (0, 0, 1, 0, Fraction(3, 2), 3))
        self.assert_result(uneven, wire, received, (0, 0), True)
        linear = publish(self.center, received, data['linear_offsets'], 1)
        self.assert_result(linear, wire, received, (1, 1), True)

    def test_invalid_request(self):
        _, wire, received = self.accepted([(0, 1, 2, 3)])
        malformed = json.loads(wire)
        piece_id = malformed['piece_id'] + '-unusable'
        invalid_wire = json.dumps({**malformed, 'piece_id': piece_id,
                                   'body': {'stations': malformed['body']['stations']}})
        unusable = receive(self.center, invalid_wire)
        for error, parent, offsets, limit in (
            (KeyError, 'unknown-intake', ZERO, 1),
            (ValueError, received, ZERO[:3], 1),
            (ValueError, received, ZERO, '1/0'),
            (ValueError, unusable, ZERO, 1),
        ):
            with self.subTest(parent=parent, offsets=offsets, limit=limit):
                with self.assertRaises(error):
                    publish(self.center, parent, offsets, limit)
                self.assertEqual(self.publication_counts(), (0, 0))

    def test_mixed_calibration(self):
        data = sample('boundaries')
        first, first_wire, first_intake = self.accepted(data['simplex'])
        _, second_wire, second_intake = self.accepted(data['cube'], first)
        self.take_source_offline()
        self.assertFalse(self.source_path.exists())
        first_result = publish(self.center, first_intake, ZERO, data['limit'])
        self.assert_result(first_result, first_wire, first_intake, (Fraction(-1, 3), Fraction(1, 4)), True)
        second_result = publish(self.center, second_intake, ZERO, data['limit'])
        self.assert_result(second_result, second_wire, second_intake, (Fraction(-1, 2), Fraction(1, 3)), False)
        self.assertFalse(self.source_path.exists())
        self.assertEqual(self.publication_counts(), (2, 2))
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 'common_calibration',
            'input': {'initial': data['simplex'], 'correction': data['cube'], 'offsets': ZERO, 'limit': data['limit']},
            'expected': [['-1/3', '1/4'], ['-1/2', '1/3']],
            'actual': [[str(result.report.bounds.lower), str(result.report.bounds.upper)]
                       for result in (first_result, second_result)],
            'downstream_expected': [True, False],
            'downstream_actual': [first_result.report.exempt, second_result.report.exempt],
            'code_paths': ['issue/relation.py', 'review/slope_range.py', 'review/decision.py', 'archive/publication.py'],
            'oracle': 'Independent fixture endpoints with explicit mixed witnesses and the exact 3/10 decision boundary.',
        }, sort_keys=True))

    def test_interior_witness(self):
        data = sample('boundaries')
        _, wire, received = self.accepted(data['simplex'])
        stations = decode_envelope(wire).station_map
        witness = tuple(map(Fraction, data['simplex_upper_witness']))
        self.assertEqual(sum(witness), 1)
        self.assertTrue(all(value >= 0 for value in witness))
        self.assertEqual(pair_slopes(stations, witness), tuple(map(Fraction, ('1/4', '0', '1/4', '-1/4', '1/4', '3/4'))))
        self.assertEqual(third_smallest_slope(stations, witness, ZERO), Fraction(1, 4))
        self.assertEqual(max(third_smallest_slope(stations, row, ZERO) for row in data['simplex']), 0)
        self.take_source_offline()
        self.assert_result(publish(self.center, received, ZERO, data['limit']), wire, received,
                           (Fraction(-1, 3), Fraction(1, 4)), True)

    def test_low_dimensional_exact_range(self):
        _, wire, received = self.accepted([(0, 0, 0, 0), (0, 1, 2, 3), (3, 4, 5, 6)])
        self.take_source_offline()
        result = publish(self.center, received, (0, '1/7', '2/7', '3/7'), '8/7')
        self.assert_result(result, wire, received, (Fraction(1, 7), Fraction(8, 7)), True)

    def assert_rejected_wire(self, payload):
        count = self.intake_count()
        with self.assertRaises(ValueError):
            receive(self.center, json.dumps(payload))
        self.assertEqual(self.intake_count(), count)
        self.assertEqual(self.publication_counts(), (0, 0))

    def test_wrong_station_map(self):
        _, wire = self.frozen([(0, 1, 2, 3)])
        payload = json.loads(wire)
        payload['body']['stations']['names'][0] = 'P-other'
        self.assert_rejected_wire(payload)

    def test_permuted_stations(self):
        _, wire, original = self.accepted([(0, 1, 2, 3)])
        payload = json.loads(wire)
        names = payload['body']['stations']['names']
        names[0], names[1] = names[1], names[0]
        self.assert_rejected_wire(payload)
        self.assertEqual(receive(self.center, wire), original)

    def test_invalid_envelope(self):
        _, wire = self.frozen([(0, 1, 2, 3)])
        payload = json.loads(wire)
        self.assert_rejected_wire({**payload, 'version': 2})
        self.assert_rejected_wire({**payload, 'version': True})
        del payload['revision_id']
        self.assert_rejected_wire(payload)
