from dataclasses import dataclass
from fractions import Fraction

from calibration.scenarios import parse_rational, rational_row
from strips.stations import StationMap


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    intake_ref: str
    offsets: tuple[Fraction, ...]
    upper_limit: Fraction


def validate_request(intake_ref: str, offsets, limit, stations: StationMap) -> ReviewRequest:
    if not isinstance(intake_ref, str) or not intake_ref.strip():
        raise ValueError('intake reference must be a nonempty string')
    return ReviewRequest(intake_ref, rational_row(offsets, len(stations.stations)), parse_rational(limit))
