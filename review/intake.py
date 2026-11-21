import sqlite3

from issue.transport import decode_envelope
from review.repository import IntakeRepository
from strips.identity import same_station_order
from strips.stations import StationMap


def receive(db: sqlite3.Connection, wire: str) -> str:
    envelope = decode_envelope(wire)
    used = StationMap.from_payload(envelope.body.get('stations'))
    if not same_station_order(envelope.station_map.stations, used.stations):
        raise ValueError('evidence stations differ from the declared station order')
    return IntakeRepository(db).accept(envelope)
