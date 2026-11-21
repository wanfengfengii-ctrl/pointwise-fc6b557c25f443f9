"""Continuous, exact free-retest certification over a closed dial travel.

A tick is exempt from retesting when every feasible joint calibration keeps the
third smallest of the six signed slopes at or below the limit.  That is the
same as saying no common convex mixture can drive four of the six slopes all
strictly above the limit.

For one fixed set of four pairs the unsafe ticks form an open interval: the
interior of the feasible ticks at which those four slopes stay at or above the
limit.  The free tick is not clamped to travel, so the interval may be a ray or
the whole line.  Within the approved travel the safe ticks are the closed
complement of the union of those open intervals, which keeps isolated ticks and
returns the empty set when nothing survives.
"""

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from calibration.scenarios import parse_rational, rational_row
from review.exact_lp import INFEASIBLE, OPTIMAL, UNBOUNDED, optimize
from review.repository import AcceptedCalibration
from review.slope_range import _relative_points

PAIRS = tuple(combinations(range(4), 2))
SUBSETS = tuple(combinations(range(len(PAIRS)), 4))


@dataclass(frozen=True, slots=True)
class DialRequest:
    intake_ref: str
    base: tuple[Fraction, ...]
    direction: tuple[Fraction, ...]
    travel: tuple[Fraction, Fraction]
    upper_limit: Fraction


def validate_dial_request(intake_ref, base, direction, travel, limit) -> DialRequest:
    if not isinstance(intake_ref, str) or not intake_ref.strip():
        raise ValueError('intake reference must be a nonempty string')
    base_values = rational_row(base, 4)
    direction_values = rational_row(direction, 4)
    if not isinstance(travel, (list, tuple)) or len(travel) != 2:
        raise ValueError('travel must be a closed interval of two rational endpoints')
    left = parse_rational(travel[0])
    right = parse_rational(travel[1])
    if left > right:
        raise ValueError('travel endpoints must be in nondecreasing order')
    return DialRequest(intake_ref, base_values, direction_values, (left, right),
                       parse_rational(limit))


def _affine_offsets(stations, base, direction):
    offsets = []
    for left, right in PAIRS:
        distance = stations.distance(left, right)
        offsets.append(((base[right] - base[left]) / distance,
                        (direction[right] - direction[left]) / distance))
    return offsets


def _point_relatives(stations, calibration):
    values = []
    for point in _relative_points(calibration):
        readings = (Fraction(0), *point)
        values.append(tuple(
            (readings[right] - readings[left]) / stations.distance(left, right)
            for left, right in PAIRS
        ))
    return values


class _Problem:
    """Linear programs over a mixture ``w`` and a free tick ``t = u - v``.

    Unsafe ticks are those where some four chosen slopes can all be pushed
    *strictly* above the limit by one common mixture.  The strict requirement is
    essential: a slope sitting exactly on the limit still leaves a safe tick.  A
    max-margin program decides whether any strict point exists at all; only then
    are the closed feasible extremes meaningful, and their interior is unsafe.
    """

    def __init__(self, relative, offsets, request):
        self.relative = relative
        self.offsets = offsets
        self.limit = request.upper_limit
        self.points = len(relative)

    def _mix(self, width):
        return [Fraction(1)] * self.points + [Fraction(0)] * (width - self.points)

    def _feasible_rows(self, subset):
        rows = [(self._mix(self.points + 2), '=', Fraction(1))]
        for pair in subset:
            base, direction = self.offsets[pair]
            rows.append(([point[pair] for point in self.relative] + [direction, -direction],
                         '>=', self.limit - base))
        return rows

    def _max_margin(self, subset):
        rows = [(self._mix(self.points + 3), '=', Fraction(1))]
        for pair in subset:
            base, direction = self.offsets[pair]
            rows.append(([point[pair] for point in self.relative]
                         + [direction, -direction, Fraction(-1)], '>=', self.limit - base))
        objective = [Fraction(0)] * (self.points + 2) + [Fraction(1)]
        return optimize(objective, rows)

    def _extreme(self, subset, maximize):
        objective = [Fraction(0)] * self.points + [Fraction(1), Fraction(-1)]
        status, value = optimize(objective, self._feasible_rows(subset), maximize=maximize)
        if status == UNBOUNDED:
            return None
        if status != OPTIMAL:
            return False
        return value

    def forbidden(self, subset):
        """Return this subset's unsafe ticks as ``('open', low, high)`` or a
        degenerate ``('point', tick)``; ``None`` bounds mean an unbounded ray.

        The strict-feasible set is the relative interior of the closed feasible
        set, so its tick projection is open whenever that projection has more
        than one point, and collapses to the single tick otherwise.
        """
        status, margin = self._max_margin(subset)
        if status == INFEASIBLE:
            return None
        if status == OPTIMAL and margin <= 0:
            return None
        low = self._extreme(subset, maximize=False)
        high = self._extreme(subset, maximize=True)
        if low is False or high is False:
            return None
        if low is not None and high is not None:
            if low > high:
                return None
            if low == high:
                return ('point', low)
        return ('open', low, high)


def _conflict(entry, tick):
    if entry[0] == 'point':
        return tick == entry[1]
    _, low, high = entry
    return (low is None or tick > low) and (high is None or tick < high)


def dial_safe_intervals(calibration: AcceptedCalibration, request: DialRequest):
    if calibration.intake_ref != request.intake_ref:
        raise ValueError('request does not name this accepted piece')
    stations = calibration.envelope.station_map
    relative = _point_relatives(stations, calibration)
    offsets = _affine_offsets(stations, request.base, request.direction)
    problem = _Problem(relative, offsets, request)
    forbidden = [item for item in (problem.forbidden(subset) for subset in SUBSETS)
                 if item is not None]
    left, right = request.travel

    def unsafe(tick):
        return any(_conflict(entry, tick) for entry in forbidden)

    if left == right:
        return () if unsafe(left) else ((left, left),)

    cut = {left, right}
    for entry in forbidden:
        boundaries = (entry[1],) if entry[0] == 'point' else entry[1:]
        for boundary in boundaries:
            if boundary is not None and left < boundary < right:
                cut.add(boundary)
    ordered = sorted(cut)

    result = []
    run = None
    for index, tick in enumerate(ordered):
        if unsafe(tick):
            if run is not None:
                result.append(tuple(run))
                run = None
        elif run is None:
            run = [tick, tick]
        else:
            run[1] = tick
        if index + 1 < len(ordered):
            following = ordered[index + 1]
            if unsafe((tick + following) / 2):
                if run is not None:
                    result.append(tuple(run))
                    run = None
            elif run is None:
                run = [tick, following]
            else:
                run[1] = following
    if run is not None:
        result.append(tuple(run))
    return tuple(result)
