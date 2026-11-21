import sqlite3
from uuid import uuid4

from archive.receipts import make_first_receipt
from archive.report import SignedDialPublication, SignedPublication, build_dial_report, build_report
from archive.repository import ArchiveRepository
from review.decision import assess
from review.dial import dial_safe_intervals, validate_dial_request
from review.repository import IntakeRepository


class PublicationError(RuntimeError):
    pass


def publish(db: sqlite3.Connection, intake_ref: str, offsets, limit) -> SignedPublication:
    decision = assess(db, intake_ref, offsets, limit)
    receipt = make_first_receipt(f'report-{uuid4().hex}', decision.calibration.envelope.piece_id)
    report = build_report(decision, receipt)
    try:
        return ArchiveRepository(db).commit_publication(report, receipt)
    except sqlite3.Error as error:
        raise PublicationError('report and receipt could not be committed') from error


def publish_dial(
    db: sqlite3.Connection, intake_ref: str, base, direction, travel, limit
) -> SignedDialPublication:
    request = validate_dial_request(intake_ref, base, direction, travel, limit)
    calibration = IntakeRepository(db).get(intake_ref)
    intervals = dial_safe_intervals(calibration, request)
    receipt = make_first_receipt(f'report-{uuid4().hex}', calibration.envelope.piece_id)
    report = build_dial_report(calibration.intake_ref, calibration.envelope, request, intervals, receipt)
    try:
        return ArchiveRepository(db).commit_dial(report, receipt)
    except sqlite3.Error as error:
        raise PublicationError('report and receipt could not be committed') from error
