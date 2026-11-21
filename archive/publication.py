import sqlite3
from uuid import uuid4

from archive.receipts import make_first_receipt
from archive.report import SignedPublication, build_report
from archive.repository import ArchiveRepository
from review.decision import assess


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
