import sqlite3
from uuid import uuid4

from calibration.repository import RevisionRepository
from calibration.revisions import RevisionRef
from issue.envelope import make_envelope
from issue.relation import freeze_relative_evidence
from issue.repository import FrozenPieceRepository
from issue.transport import encode_envelope
from strips.catalog import resolve_strip


def issue(db: sqlite3.Connection, revision_ref: RevisionRef) -> str:
    if not isinstance(revision_ref, RevisionRef):
        raise ValueError('expected a revision reference')
    pieces = FrozenPieceRepository(db)
    existing = pieces.find_by_revision(revision_ref)
    if existing is not None:
        return existing
    revision = RevisionRepository(db).get(revision_ref)
    strip = resolve_strip(db, revision.ref.strip_id, require_enabled=False)
    body = freeze_relative_evidence(revision, strip.station_map)
    piece = make_envelope(
        f'piece-{uuid4().hex}', strip.strip_id, revision.ref.revision_id, strip.station_map, body
    )
    return pieces.save_once(revision.ref, piece.piece_id, encode_envelope(piece))
