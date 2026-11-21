import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from demo import run_workday
from tests import sample


class WorkdayTests(unittest.TestCase):
    def test_workday_reopens_with_original_lineage(self):
        with TemporaryDirectory(prefix='strip-integration-') as directory:
            publications, history, pieces = run_workday(Path(directory), sample('workday'))
        self.assertEqual(history, publications)
        self.assertNotEqual(history[0].report.report_id, history[1].report.report_id)
        self.assertNotEqual(history[0].receipt.receipt_id, history[1].receipt.receipt_id)
        for publication, piece, slope, exempt in zip(history, pieces, (1, 2), (True, False)):
            report = publication.report
            self.assertEqual(piece.station_map.names, ('P4', 'P2', 'P1', 'P3'))
            self.assertEqual((report.bounds.lower, report.bounds.upper), (slope, slope))
            self.assertIs(report.exempt, exempt)
            self.assertEqual((report.piece_id, report.revision_id), (piece.piece_id, piece.revision_id))
            self.assertEqual(publication.receipt.piece_id, piece.piece_id)
