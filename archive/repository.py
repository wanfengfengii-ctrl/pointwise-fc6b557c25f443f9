import json
import sqlite3
from fractions import Fraction

from archive.receipts import FirstReceipt
from archive.report import SignedDialPublication, SignedPublication, DialReport, TrendReport
from review.slope_range import SlopeRange


def _interval_payload(intervals) -> str:
    return json.dumps([[str(left), str(right)] for left, right in intervals])


def _interval_rows(payload: str) -> tuple[tuple[Fraction, Fraction], ...]:
    return tuple((Fraction(left), Fraction(right)) for left, right in json.loads(payload))


class ArchiveRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def initialize(self) -> None:
        self.db.execute('BEGIN IMMEDIATE')
        with self.db:
            self.db.execute('''
                CREATE TABLE IF NOT EXISTS trend_reports (
                    report_id TEXT PRIMARY KEY NOT NULL,
                    receipt_id TEXT UNIQUE NOT NULL,
                    intake_ref TEXT NOT NULL REFERENCES accepted_calibrations(intake_ref),
                    piece_id TEXT NOT NULL,
                    strip_id TEXT NOT NULL,
                    revision_id TEXT NOT NULL,
                    offsets TEXT NOT NULL,
                    upper_limit TEXT NOT NULL,
                    lower_slope TEXT NOT NULL,
                    upper_slope TEXT NOT NULL,
                    exempt INTEGER NOT NULL CHECK (exempt IN (0, 1))
                )
            ''')
            self.db.execute('''
                CREATE TABLE IF NOT EXISTS first_receipts (
                    receipt_id TEXT PRIMARY KEY NOT NULL,
                    report_id TEXT UNIQUE NOT NULL REFERENCES trend_reports(report_id),
                    piece_id TEXT NOT NULL
                )
            ''')
            self.db.execute('''
                CREATE TABLE IF NOT EXISTS dial_reports (
                    report_id TEXT PRIMARY KEY NOT NULL,
                    receipt_id TEXT UNIQUE NOT NULL,
                    intake_ref TEXT NOT NULL REFERENCES accepted_calibrations(intake_ref),
                    piece_id TEXT NOT NULL,
                    revision_id TEXT NOT NULL,
                    base TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    travel TEXT NOT NULL,
                    upper_limit TEXT NOT NULL,
                    safe_intervals TEXT NOT NULL
                )
            ''')
            self.db.execute('''
                CREATE TABLE IF NOT EXISTS dial_receipts (
                    receipt_id TEXT PRIMARY KEY NOT NULL,
                    report_id TEXT UNIQUE NOT NULL REFERENCES dial_reports(report_id),
                    piece_id TEXT NOT NULL
                )
            ''')

    def commit_publication(self, report: TrendReport, receipt: FirstReceipt) -> SignedPublication:
        if (report.receipt_id, report.report_id, report.piece_id) != (
            receipt.receipt_id, receipt.report_id, receipt.piece_id
        ):
            raise ValueError('report and receipt do not describe the same publication')
        offsets = json.dumps([str(value) for value in report.offsets])
        self.db.execute('BEGIN IMMEDIATE')
        with self.db:
            self.db.execute('''
                INSERT INTO trend_reports (
                    report_id, receipt_id, intake_ref, piece_id, strip_id, revision_id,
                    offsets, upper_limit, lower_slope, upper_slope, exempt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (report.report_id, report.receipt_id, report.intake_ref, report.piece_id,
                  report.strip_id, report.revision_id, offsets, str(report.upper_limit),
                  str(report.bounds.lower), str(report.bounds.upper), int(report.exempt)))
            self.db.execute('''
                INSERT INTO first_receipts (receipt_id, report_id, piece_id) VALUES (?, ?, ?)
            ''', (receipt.receipt_id, receipt.report_id, receipt.piece_id))
        return SignedPublication(report, receipt)

    def read_publication(self, report_id: str) -> SignedPublication | None:
        row = self.db.execute('''
            SELECT r.report_id, r.receipt_id, r.intake_ref, r.piece_id, r.strip_id, r.revision_id,
                   r.offsets, r.upper_limit, r.lower_slope, r.upper_slope, r.exempt,
                   f.receipt_id, f.report_id, f.piece_id
            FROM trend_reports AS r
            JOIN first_receipts AS f
              ON f.report_id = r.report_id AND f.receipt_id = r.receipt_id AND f.piece_id = r.piece_id
            WHERE r.report_id = ?
        ''', (report_id,)).fetchone()
        if row is None:
            return None
        report = TrendReport(
            *row[:6], tuple(map(Fraction, json.loads(row[6]))), Fraction(row[7]),
            SlopeRange(Fraction(row[8]), Fraction(row[9])), bool(row[10]),
        )
        return SignedPublication(report, FirstReceipt(*row[11:]))

    def commit_dial(self, report: DialReport, receipt: FirstReceipt) -> SignedDialPublication:
        if (report.receipt_id, report.report_id, report.piece_id) != (
            receipt.receipt_id, receipt.report_id, receipt.piece_id
        ):
            raise ValueError('report and receipt do not describe the same publication')
        self.db.execute('BEGIN IMMEDIATE')
        with self.db:
            self.db.execute('''
                INSERT INTO dial_reports (
                    report_id, receipt_id, intake_ref, piece_id, revision_id,
                    base, direction, travel, upper_limit, safe_intervals
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (report.report_id, report.receipt_id, report.intake_ref, report.piece_id,
                  report.revision_id,
                  json.dumps([str(value) for value in report.base]),
                  json.dumps([str(value) for value in report.direction]),
                  json.dumps([str(value) for value in report.travel]),
                  str(report.upper_limit), _interval_payload(report.safe_intervals)))
            self.db.execute('''
                INSERT INTO dial_receipts (receipt_id, report_id, piece_id) VALUES (?, ?, ?)
            ''', (receipt.receipt_id, receipt.report_id, receipt.piece_id))
        return SignedDialPublication(report, receipt)

    def read_dial(self, report_id: str) -> SignedDialPublication | None:
        row = self.db.execute('''
            SELECT r.report_id, r.receipt_id, r.intake_ref, r.piece_id, r.revision_id,
                   r.base, r.direction, r.travel, r.upper_limit, r.safe_intervals,
                   f.receipt_id, f.report_id, f.piece_id
            FROM dial_reports AS r
            JOIN dial_receipts AS f
              ON f.report_id = r.report_id AND f.receipt_id = r.receipt_id AND f.piece_id = r.piece_id
            WHERE r.report_id = ?
        ''', (report_id,)).fetchone()
        if row is None:
            return None
        report = DialReport(
            *row[:5],
            tuple(map(Fraction, json.loads(row[5]))),
            tuple(map(Fraction, json.loads(row[6]))),
            tuple(map(Fraction, json.loads(row[7]))),
            Fraction(row[8]), _interval_rows(row[9]),
        )
        return SignedDialPublication(report, FirstReceipt(*row[10:]))
