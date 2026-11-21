import json
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.history import read
from archive.publication import publish
from archive.repository import ArchiveRepository
from calibration.corrections import record
from calibration.repository import RevisionRepository
from issue.freeze import issue
from issue.repository import FrozenPieceRepository
from issue.transport import decode_envelope
from review.intake import receive
from review.repository import IntakeRepository
from strips.catalog import register
from strips.repository import StripRepository


SAMPLE = Path(__file__).resolve().parent / 'samples' / 'workday.json'


def run_workday(directory: Path, sample: dict):
    source_path = directory / 'source.sqlite'
    center_path = directory / 'center.sqlite'
    with closing(sqlite3.connect(center_path)) as center:
        IntakeRepository(center).initialize()
        ArchiveRepository(center).initialize()
        with closing(sqlite3.connect(source_path)) as source:
            StripRepository(source).initialize()
            RevisionRepository(source).initialize()
            FrozenPieceRepository(source).initialize()
            strip = register(source, sample['strip_id'], sample['station_names'], sample['positions'])
            initial = record(source, strip, sample['initial'])
            initial_wire = issue(source, initial)
            initial_intake = receive(center, initial_wire)
        first = publish(center, initial_intake, sample['offsets'], sample['limit'])
        with closing(sqlite3.connect(source_path)) as source:
            corrected = record(source, strip, sample['correction'], previous=initial)
            corrected_wire = issue(source, corrected)
            corrected_intake = receive(center, corrected_wire)
            if issue(source, initial) != initial_wire:
                raise AssertionError('initial piece changed after correction')
        second = publish(center, corrected_intake, sample['offsets'], sample['limit'])
    signed = (first, second)
    with closing(sqlite3.connect(center_path)) as center:
        center.execute('PRAGMA query_only = ON')
        retrieved = tuple(read(center, item.report.report_id) for item in signed)
    return signed, retrieved, (decode_envelope(initial_wire), decode_envelope(corrected_wire))


def _result(publication) -> dict:
    report = publication.report
    return {'range': [str(report.bounds.lower), str(report.bounds.upper)], 'exempt': report.exempt}


def main() -> None:
    sample = json.loads(SAMPLE.read_text(encoding='utf-8'))
    with TemporaryDirectory(prefix='strip-workday-') as directory:
        signed, retrieved, pieces = run_workday(Path(directory), sample)
    actual = [_result(item) for item in signed]
    downstream = {
        'ranges_and_decisions': [_result(item) for item in retrieved],
        'same_publications': retrieved == signed,
        'actual_parents': all(
            (item.report.piece_id, item.report.revision_id, item.receipt.piece_id)
            == (piece.piece_id, piece.revision_id, piece.piece_id)
            for item, piece in zip(retrieved, pieces)
        ),
        'distinct_parents': pieces[0].piece_id != pieces[1].piece_id,
    }
    downstream_expected = {
        'ranges_and_decisions': sample['expected'], 'same_publications': True,
        'actual_parents': True, 'distinct_parents': True,
    }
    if actual != sample['expected'] or downstream != downstream_expected:
        raise AssertionError(f'workday results differ: {actual}, {downstream}')
    for name, item in zip(('初版', '勘误版'), retrieved):
        label = '免复测' if item.report.exempt else '须复测'
        print(f'{name} [{item.report.bounds.lower}, {item.report.bounds.upper}] {label} '
              f'报告 {item.report.report_id} 固定件 {item.report.piece_id} 首执 {item.receipt.receipt_id}')
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': 'history',
        'input': {key: value for key, value in sample.items() if key != 'expected'},
        'expected': sample['expected'], 'actual': actual,
        'downstream_expected': downstream_expected, 'downstream_actual': downstream,
        'code_paths': ['issue/freeze.py', 'review/intake.py', 'review/slope_range.py',
                       'archive/publication.py', 'archive/history.py'],
        'oracle': 'Each sample is linear in position, so all six pairs give 1 or 2. Compare to 1 and check stored identifiers.',
    }, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
