import sqlite3

from strips.repository import StripRecord, StripRepository
from strips.stations import make_station_map


def _check_strip_id(strip_id: str) -> None:
    if not isinstance(strip_id, str) or not strip_id.strip():
        raise ValueError('strip reference must be a nonempty string')


def register(db: sqlite3.Connection, strip_id: str, names, positions=(0, 1, 2, 3)) -> str:
    _check_strip_id(strip_id)
    stations = make_station_map(names, positions)
    return StripRepository(db).add(strip_id, stations)


def resolve_strip(db: sqlite3.Connection, strip_id: str, *, require_enabled: bool = True) -> StripRecord:
    _check_strip_id(strip_id)
    strip = StripRepository(db).get(strip_id)
    if require_enabled and not strip.enabled:
        raise ValueError(f'strip is not available for recording: {strip_id}')
    return strip
