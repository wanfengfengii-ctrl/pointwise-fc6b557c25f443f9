from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StationIdentity:
    name: str
    position: int


def validate_station_identities(stations: tuple[StationIdentity, ...]) -> None:
    if len(stations) != 4:
        raise ValueError('exactly four stations are required')
    names = [station.name for station in stations]
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError('station names must be nonempty strings')
    if len(set(names)) != len(names):
        raise ValueError('station names must be distinct within a strip')


def same_station_order(
    declared: tuple[StationIdentity, ...], used: tuple[StationIdentity, ...]
) -> bool:
    return declared == used
