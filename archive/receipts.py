from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class FirstReceipt:
    receipt_id: str
    report_id: str
    piece_id: str


def make_first_receipt(report_id: str, piece_id: str) -> FirstReceipt:
    return FirstReceipt(f'receipt-{uuid4().hex}', report_id, piece_id)
