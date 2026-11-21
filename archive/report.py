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


def build_report(decision: ReviewDecision, receipt: FirstReceipt) -> TrendReport:
    piece = decision.calibration.envelope
    if receipt.piece_id != piece.piece_id:
        raise ValueError('receipt does not refer to the assessed piece')
    return TrendReport(
        receipt.report_id, receipt.receipt_id, decision.calibration.intake_ref,
        piece.piece_id, piece.strip_id, piece.revision_id, decision.request.offsets,
        decision.request.upper_limit, decision.bounds, decision.exempt,
    )
