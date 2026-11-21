import json
import sqlite3
from dataclasses import dataclass

from strips.stations import StationMap


@dataclass(frozen=True, slots=True)
class StripRecord:
    strip_id: str
    station_map: StationMap
    enabled: bool


class StripRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def initialize(self) -> None:
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS strips (
                strip_id TEXT PRIMARY KEY NOT NULL,
                station_map TEXT NOT NULL,
                enabled INTEGER NOT NULL CHECK (enabled IN (0, 1))
            )
        ''')

    def add(self, strip_id: str, station_map: StationMap) -> str:
        raw_map = json.dumps(station_map.to_payload(), ensure_ascii=True)
        self.db.execute('BEGIN IMMEDIATE')
        with self.db:
            result = self.db.execute('''
                INSERT INTO strips (strip_id, station_map, enabled) VALUES (?, ?, 1)
                ON CONFLICT(strip_id) DO NOTHING
            ''', (strip_id, raw_map))
            if result.rowcount != 1:
                raise ValueError(f'strip already registered: {strip_id}')
        return strip_id

    def get(self, strip_id: str) -> StripRecord:
        row = self.db.execute('''
            SELECT station_map, enabled FROM strips WHERE strip_id = ?
        ''', (strip_id,)).fetchone()
        if row is None:
            raise KeyError(strip_id)
        return StripRecord(strip_id, StationMap.from_payload(json.loads(row[0])), bool(row[1]))
