"""Run this project's full unittest suite and the dial business check.

From the repository root: ``python3 -B check_project.py``.  Exits nonzero when
any regression test fails or the dial fixture no longer matches its approved
safe sets.
"""
import sys
import unittest


def run_suite() -> bool:
    suite = unittest.defaultTestLoader.discover('tests', top_level_dir='.')
    if suite.countTestCases():
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    else:
        print('No tests discovered in tests/', file=sys.stderr)
        result = unittest.TestResult()
    for status, failed_cases in (
        ('FAIL', (test for test, _ in result.failures)),
        ('ERROR', (test for test, _ in result.errors)),
        ('UNEXPECTED_SUCCESS', result.unexpectedSuccesses),
    ):
        for test in failed_cases:
            print(f'{status} {test.id()}')
    successful = result.testsRun > 0 and result.wasSuccessful()
    print(f'TEST SUMMARY total={result.testsRun} failures={len(result.failures)} '
          f'errors={len(result.errors)} skipped={len(result.skipped)} '
          f'expected_failures={len(result.expectedFailures)} '
          f'unexpected_successes={len(result.unexpectedSuccesses)} '
          f'result={"PASS" if successful else "FAIL"}')
    return successful


def run_dial_check() -> bool:
    import dial_fixture
    try:
        dial_fixture.main()
    except AssertionError as error:
        print(f'DIAL FIXTURE FAIL {error}')
        return False
    print('DIAL FIXTURE PASS')
    return True


def main() -> int:
    suite_ok = run_suite()
    dial_ok = run_dial_check()
    return 0 if suite_ok and dial_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
