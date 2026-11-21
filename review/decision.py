import sqlite3
from dataclasses import dataclass

from review.repository import AcceptedCalibration, IntakeRepository
from review.request import ReviewRequest, validate_request
from review.slope_range import SlopeRange, certify_slope_range


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    calibration: AcceptedCalibration
    request: ReviewRequest
    bounds: SlopeRange
    exempt: bool


def assess(db: sqlite3.Connection, intake_ref: str, offsets, limit) -> ReviewDecision:
    calibration = IntakeRepository(db).get(intake_ref)
    request = validate_request(intake_ref, offsets, limit, calibration.envelope.station_map)
    bounds = certify_slope_range(calibration, request)
    return ReviewDecision(calibration, request, bounds, bounds.upper <= request.upper_limit)
