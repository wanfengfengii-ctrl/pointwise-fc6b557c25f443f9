from dataclasses import dataclass
from fractions import Fraction

from archive.receipts import FirstReceipt
from review.decision import ReviewDecision
from review.slope_range import SlopeRange


@dataclass(frozen=True, slots=True)
class TrendReport:
    report_id: str
    receipt_id: str
    intake_ref: str
    piece_id: str
    strip_id: str
    revision_id: str
    offsets: tuple[Fraction, ...]
    upper_limit: Fraction
    bounds: SlopeRange
    exempt: bool


@dataclass(frozen=True, slots=True)
class SignedPublication:
    report: TrendReport
    receipt: FirstReceipt


@dataclass(frozen=True, slots=True)
class DialReport:
    report_id: str
    receipt_id: str
    intake_ref: str
    piece_id: str
    revision_id: str
    base: tuple[Fraction, ...]
    direction: tuple[Fraction, ...]
    travel: tuple[Fraction, Fraction]
    upper_limit: Fraction
    safe_intervals: tuple[tuple[Fraction, Fraction], ...]


@dataclass(frozen=True, slots=True)
class SignedDialPublication:
    report: DialReport
    receipt: FirstReceipt


def build_dial_report(
    intake_ref: str, piece, request, safe_intervals, receipt: FirstReceipt
) -> DialReport:
    if receipt.piece_id != piece.piece_id:
        raise ValueError('receipt does not refer to the assessed piece')
    return DialReport(
        receipt.report_id, receipt.receipt_id, intake_ref,
        piece.piece_id, piece.revision_id,
        request.base, request.direction, request.travel,
        request.upper_limit, tuple(safe_intervals),
    )


def build_report(decision: ReviewDecision, receipt: FirstReceipt) -> TrendReport:
    piece = decision.calibration.envelope
    if receipt.piece_id != piece.piece_id:
        raise ValueError('receipt does not refer to the assessed piece')
    return TrendReport(
        receipt.report_id, receipt.receipt_id, decision.calibration.intake_ref,
        piece.piece_id, piece.strip_id, piece.revision_id, decision.request.offsets,
        decision.request.upper_limit, decision.bounds, decision.exempt,
    )
