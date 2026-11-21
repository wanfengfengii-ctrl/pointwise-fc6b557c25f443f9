from fractions import Fraction
from itertools import combinations

from strips.stations import StationMap


def add_point_offsets(readings, offsets) -> tuple[Fraction, ...]:
    if len(readings) != 4 or len(offsets) != 4:
        raise ValueError('exactly four readings and offsets are required')
    return tuple(Fraction(reading) + Fraction(offset) for reading, offset in zip(readings, offsets))


def pair_slopes(stations: StationMap, readings) -> tuple[Fraction, ...]:
    count = len(stations.stations)
    if len(readings) != count:
        raise ValueError('readings must match the station map')
    exact = tuple(map(Fraction, readings))
    return tuple(
        (exact[right] - exact[left]) / stations.distance(left, right)
        for left, right in combinations(range(count), 2)
    )


def third_smallest_slope(stations: StationMap, readings, offsets) -> Fraction:
    return sorted(pair_slopes(stations, add_point_offsets(readings, offsets)))[2]
