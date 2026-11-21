import json
import sqlite3
from contextlib import closing
from fractions import Fraction
from pathlib import Path

from calibration.corrections import record
from calibration.repository import RevisionRepository
from issue.freeze import issue
from issue.repository import FrozenPieceRepository
from review.decision import assess
from review.intake import receive
from review.repository import IntakeRepository
from strips.catalog import register
from strips.repository import StripRepository


SAMPLE = Path(__file__).resolve().parent / "samples" / "dial.json"


def main() -> None:
    fixture = json.loads(SAMPLE.read_text(encoding="utf-8"))
    with closing(sqlite3.connect(":memory:")) as center:
        center.execute("PRAGMA foreign_keys = ON")
        IntakeRepository(center).initialize()
        with closing(sqlite3.connect(":memory:")) as source:
            source.execute("PRAGMA foreign_keys = ON")
            StripRepository(source).initialize()
            RevisionRepository(source).initialize()
            FrozenPieceRepository(source).initialize()
            strip = register(source, fixture["strip_id"], fixture["station_names"])
            revision = None
            pieces = []
            for case in fixture["cases"]:
                revision = record(source, strip, case["rows"], previous=revision)
                pieces.append((case, receive(center, issue(source, revision))))
        for case, intake in pieces:
            name = case["name"]
            for tick, expected in case["point_upper"].items():
                offsets = tuple(
                    Fraction(base) + Fraction(tick) * Fraction(direction)
                    for base, direction in zip(fixture["base"], fixture["direction"])
                )
                upper = assess(center, intake, offsets, 0).bounds.upper
                if upper != Fraction(expected):
                    raise AssertionError(f"{name} at {tick}: expected {expected}, got {upper}")
                print(f"{name} at {tick}: V1 upper {upper}")


if __name__ == "__main__":
    main()
