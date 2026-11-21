import json

from issue.envelope import V1Envelope, make_envelope, validate_envelope
from strips.stations import StationMap


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON field: {key}')
        result[key] = value
    return result


def encode_envelope(envelope: V1Envelope) -> str:
    validate_envelope(envelope)
    return json.dumps({
        'version': envelope.version,
        'piece_id': envelope.piece_id,
        'strip_id': envelope.strip_id,
        'revision_id': envelope.revision_id,
        'station_map': envelope.station_map.to_payload(),
        'body': envelope.body,
    }, sort_keys=True, separators=(',', ':'), allow_nan=False)


def decode_envelope(wire: str) -> V1Envelope:
    if not isinstance(wire, str):
        raise ValueError('expected JSON text')
    try:
        payload = json.loads(wire, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError) as error:
        raise ValueError('invalid V1 JSON') from error
    fields = {'version', 'piece_id', 'strip_id', 'revision_id', 'station_map', 'body'}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ValueError('invalid V1 envelope fields')
    if type(payload['version']) is not int or payload['version'] != 1:
        raise ValueError('expected version 1')
    station_map = StationMap.from_payload(payload['station_map'])
    try:
        return make_envelope(payload['piece_id'], payload['strip_id'], payload['revision_id'], station_map, payload['body'])
    except (TypeError, RecursionError) as error:
        raise ValueError('invalid V1 body') from error
