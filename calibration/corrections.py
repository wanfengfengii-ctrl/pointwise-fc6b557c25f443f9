import sqlite3

from calibration.repository import RevisionRepository
from calibration.revisions import RevisionRef, build_revision
from calibration.scenarios import validate_scenarios
from strips.catalog import resolve_strip


def record(db: sqlite3.Connection, strip_id: str, rows, previous: RevisionRef | None = None) -> RevisionRef:
    strip = resolve_strip(db, strip_id)
    batch = validate_scenarios(rows, strip.station_map)
    revision = build_revision(strip.strip_id, batch, previous)
    return RevisionRepository(db).append(revision)
