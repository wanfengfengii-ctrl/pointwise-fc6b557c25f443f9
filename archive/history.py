import sqlite3

from archive.report import SignedDialPublication, SignedPublication
from archive.repository import ArchiveRepository


class ReportNotFound(KeyError):
    def __init__(self, report_id: str):
        super().__init__(report_id)
        self.report_id = report_id


def read(db: sqlite3.Connection, report_id: str) -> SignedPublication:
    if not isinstance(report_id, str):
        raise ValueError('report reference must be a string')
    publication = ArchiveRepository(db).read_publication(report_id)
    if publication is None:
        raise ReportNotFound(report_id)
    return publication


def read_dial(db: sqlite3.Connection, report_id: str) -> SignedDialPublication:
    if not isinstance(report_id, str):
        raise ValueError('report reference must be a string')
    publication = ArchiveRepository(db).read_dial(report_id)
    if publication is None:
        raise ReportNotFound(report_id)
    return publication
