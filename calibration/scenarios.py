from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from strips.stations import StationMap


@dataclass(frozen=True, slots=True)
class ScenarioBatch:
    rows: tuple[tuple[Fraction, ...], ...]


def parse_rational(value: object) -> Fraction:
    if type(value) is int or isinstance(value, (str, Fraction)):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as error:
            raise ValueError('invalid rational value') from error
    raise ValueError('expected an integer, rational string, or Fraction')


def rational_row(values, size: int) -> tuple[Fraction, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        raise ValueError('expected an ordered row of values')
    if len(values) != size:
        raise ValueError(f'expected exactly {size} values')
    return tuple(parse_rational(value) for value in values)


def validate_scenarios(rows, stations: StationMap) -> ScenarioBatch:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise ValueError('expected an ordered batch of scenarios')
    if not 1 <= len(rows) <= 16:
        raise ValueError('a batch must contain one to sixteen scenarios')
    checked = []
    for number, row in enumerate(rows, start=1):
        try:
            checked.append(rational_row(row, len(stations.stations)))
        except ValueError as error:
            raise ValueError(f'invalid scenario {number}: {error}') from error
    return ScenarioBatch(tuple(checked))
