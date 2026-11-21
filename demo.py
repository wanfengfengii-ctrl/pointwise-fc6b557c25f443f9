import json
import sqlite3
from contextlib import closing
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.history import read, read_dial
from archive.publication import publish, publish_dial
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
DIAL_SAMPLE = Path(__file__).resolve().parent / 'samples' / 'dial.json'


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


def run_dial(directory: Path, sample: dict):
    """Sign a dial report with the source closed, then reopen and reclaim it."""
    source_path = directory / 'dial-source.sqlite'
    center_path = directory / 'dial-center.sqlite'
    base = tuple(Fraction(value) for value in sample['base'])
    direction = tuple(Fraction(value) for value in sample['direction'])
    with closing(sqlite3.connect(center_path)) as center:
        IntakeRepository(center).initialize()
        ArchiveRepository(center).initialize()
        with closing(sqlite3.connect(source_path)) as source:
            StripRepository(source).initialize()
            RevisionRepository(source).initialize()
            FrozenPieceRepository(source).initialize()
            strip = register(source, sample['strip_id'], sample['station_names'])
            revision = None
            intake = None
            pieces = []
            for case in sample['cases']:
                revision = record(source, strip, case['rows'], previous=revision)
                wire = issue(source, revision)
                intake = receive(center, wire)
                pieces.append((case, wire, revision, intake))
        source_path.unlink()
        signed = []
        for case, _, revision, intake in pieces:
            for request in case['requests']:
                signed.append((case, revision, publish_dial(
                    center, intake, base, direction, request['travel'], request['limit'])))
    with closing(sqlite3.connect(center_path)) as center:
        center.execute('PRAGMA query_only = ON')
        retrieved = tuple(read_dial(center, item.report.report_id) for _, _, item in signed)
    return signed, retrieved, pieces


def _dial_intervals(report) -> list:
    return [[str(left), str(right)] for left, right in report.safe_intervals]


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

    dial = json.loads(DIAL_SAMPLE.read_text(encoding='utf-8'))
    with TemporaryDirectory(prefix='strip-dial-') as directory:
        dial_signed, dial_retrieved, dial_pieces = run_dial(Path(directory), dial)
    actual_intervals = [_dial_intervals(item.report) for _, _, item in dial_signed]
    claimed_intervals = [_dial_intervals(item.report) for item in dial_retrieved]
    expected_intervals = [request['safe_intervals']
                          for case in dial['cases'] for request in case['requests']]
    if actual_intervals != expected_intervals or claimed_intervals != expected_intervals:
        raise AssertionError(f'dial results differ: {actual_intervals} vs {expected_intervals}')
    if tuple(item for _, _, item in dial_signed) != dial_retrieved:
        raise AssertionError('dial history differs from signed publications')
    for (case, revision, signed), claimed in zip(dial_signed, dial_retrieved):
        report = signed.report
        safe = ', '.join(f'[{left}, {right}]' for left, right in report.safe_intervals) or '空集'
        print(f'{case["name"]} 行程 [{report.travel[0]}, {report.travel[1]}] 上限 {report.upper_limit} '
              f'免复测 {safe} 报告 {report.report_id} 固定件 {report.piece_id} '
              f'修订 {report.revision_id} 首执 {signed.receipt.receipt_id} '
              f'重开领回 {"一致" if claimed == signed else "不一致"}')
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': 'dial',
        'input': {'base': dial['base'], 'direction': dial['direction']},
        'expected': expected_intervals, 'actual': actual_intervals,
        'downstream_expected': expected_intervals, 'downstream_actual': claimed_intervals,
        'code_paths': ['review/dial.py', 'review/exact_lp.py', 'archive/publication.py',
                       'archive/history.py'],
        'oracle': 'Every tick of each fixture request is certified continuous over all joint mixtures. '
                  'Source database is deleted before signing and reports are reclaimed by id.',
    }, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
