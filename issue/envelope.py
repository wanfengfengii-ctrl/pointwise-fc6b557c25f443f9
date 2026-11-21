import json
from dataclasses import dataclass

from strips.stations import StationMap


@dataclass(frozen=True, slots=True)
class V1Envelope:
    version: int
    piece_id: str
    strip_id: str
    revision_id: str
    station_map: StationMap
    body_json: str

    @property
    def body(self) -> dict:
        return json.loads(self.body_json)


def validate_envelope(envelope: V1Envelope) -> None:
    if type(envelope.version) is not int or envelope.version != 1:
        raise ValueError('expected version 1')
    for value in (envelope.piece_id, envelope.strip_id, envelope.revision_id):
        if not isinstance(value, str) or not value.strip():
            raise ValueError('piece, strip and revision identifiers must be nonempty strings')
    if not isinstance(envelope.station_map, StationMap):
        raise ValueError('expected a validated station declaration')
    if not isinstance(envelope.body, dict):
        raise ValueError('piece body must be a JSON object')


def make_envelope(
    piece_id: str, strip_id: str, revision_id: str, station_map: StationMap, body: dict
) -> V1Envelope:
    body_json = json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False)
    envelope = V1Envelope(1, piece_id, strip_id, revision_id, station_map, body_json)
    validate_envelope(envelope)
    return envelope
