from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from calibration.scenarios import rational_row
from review.repository import AcceptedCalibration
from review.request import ReviewRequest
from review.slopes import add_point_offsets, pair_slopes, third_smallest_slope


@dataclass(frozen=True, slots=True)
class SlopeRange:
    lower: Fraction
    upper: Fraction


def _relative_points(calibration: AcceptedCalibration) -> tuple[tuple[Fraction, ...], ...]:
    points = calibration.envelope.body.get('relative_points')
    if not isinstance(points, list) or not 1 <= len(points) <= 16:
        raise ValueError('piece has no usable joint relative readings')
    return tuple(dict.fromkeys(rational_row(row, 3) for row in points))


def _maximize_minimum(scores) -> Fraction:
    # Each affine score uses the same convex weights. Eliminate the last weight
    # and shift the objective down to a known lower bound for a feasible start.
    floor = min(map(min, scores))
    base = scores[-1]
    count = len(scores)
    conditions = [
        [*(base[j] - row[j] for row in scores[:-1]), Fraction(1), base[j] - floor]
        for j in range(len(base))
    ]
    conditions.append([*([Fraction(1)] * (count - 1)), Fraction(0), Fraction(1)])
    basic = list(range(count, count + len(conditions)))
    table = [
        [*row[:-1], *(Fraction(i == j) for j in range(len(conditions))), row[-1]]
        for i, row in enumerate(conditions)
    ]
    objective = [Fraction(0)] * len(table[0])
    objective[count - 1] = Fraction(-1)
    table.append(objective)

    # Bland's rule resolves ties even on degenerate or lower dimensional domains.
    while True:
        entering = next((j for j, value in enumerate(table[-1][:-1]) if value < 0), None)
        if entering is None:
            return floor + table[-1][-1]
        _, _, leaving = min(
            (row[-1] / row[entering], basic[i], i)
            for i, row in enumerate(table[:-1]) if row[entering] > 0
        )
        pivot = [value / table[leaving][entering] for value in table[leaving]]
        table[leaving] = pivot
        for i, row in enumerate(table):
            if i != leaving and row[entering]:
                table[i] = [value - row[entering] * step for value, step in zip(row, pivot)]
        basic[leaving] = entering


def marginal_slope_ranges(calibration: AcceptedCalibration) -> tuple[SlopeRange, ...]:
    stations = calibration.envelope.station_map
    columns = zip(*(pair_slopes(stations, (0, *point)) for point in _relative_points(calibration)))
    return tuple(SlopeRange(min(column), max(column)) for column in columns)


def supports_relative_readings(calibration: AcceptedCalibration, readings) -> bool:
    target = rational_row(readings, 3)
    scores = [
        tuple(sign * (value - wanted) for value, wanted in zip(point, target) for sign in (-1, 1))
        for point in _relative_points(calibration)
    ]
    return _maximize_minimum(scores) == 0


def certify_slope_range(calibration: AcceptedCalibration, request: ReviewRequest) -> SlopeRange:
    if calibration.intake_ref != request.intake_ref:
        raise ValueError('request does not name this accepted piece')
    stations = calibration.envelope.station_map
    points = _relative_points(calibration)
    if len(points) == 1:
        value = third_smallest_slope(stations, (0, *points[0]), request.offsets)
        return SlopeRange(value, value)
    scores = [pair_slopes(stations, add_point_offsets((0, *point), request.offsets)) for point in points]

    # At least three slopes must be at or below a candidate for the lower end.
    # At least four must be at or above a candidate for the upper end.
    pair_indexes = range(len(scores[0]))
    lower = -max(
        _maximize_minimum([tuple(-row[index] for index in group) for row in scores])
        for group in combinations(pair_indexes, 3)
    )
    upper = max(
        _maximize_minimum([tuple(row[index] for index in group) for row in scores])
        for group in combinations(pair_indexes, 4)
    )
    return SlopeRange(lower, upper)
