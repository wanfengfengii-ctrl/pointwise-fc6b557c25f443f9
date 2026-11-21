from collections.abc import Sequence
from dataclasses import dataclass

from strips.identity import StationIdentity, validate_station_identities


@dataclass(frozen=True, slots=True)
class StationMap:
    stations: tuple[StationIdentity, ...]

    def __post_init__(self) -> None:
        validate_station_identities(self.stations)
        if any(type(position) is not int for position in self.positions):
            raise ValueError('station positions must be integer millimetres')
        if self.positions != (0, 1, 2, 3):
            raise ValueError('station positions must be ordered as 0, 1, 2, 3')

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(station.name for station in self.stations)

    @property
    def positions(self) -> tuple[int, ...]:
        return tuple(station.position for station in self.stations)

    def distance(self, left: int, right: int) -> int:
        if not 0 <= left < right < len(self.stations):
            raise ValueError('station pair must be in increasing order')
        return self.stations[right].position - self.stations[left].position

    def to_payload(self) -> dict:
        return {'names': list(self.names), 'positions': list(self.positions)}

    @classmethod
    def from_payload(cls, payload: object) -> 'StationMap':
        if not isinstance(payload, dict) or set(payload) != {'names', 'positions'}:
            raise ValueError('invalid station map')
        return make_station_map(payload['names'], payload['positions'])


def make_station_map(names, positions=(0, 1, 2, 3)) -> StationMap:
    for sequence in (names, positions):
        if not isinstance(sequence, Sequence) or isinstance(sequence, (str, bytes, bytearray)):
            raise ValueError('station names and positions must be sequences')
        if len(sequence) != 4:
            raise ValueError('exactly four station names and positions are required')
    return StationMap(tuple(StationIdentity(name, position) for name, position in zip(names, positions)))
