import json
import os
import time
from pathlib import Path
from datetime import datetime, date

# ── Thresholds ────────────────────────────────────────────────────────────────
PASS_RATE_THRESHOLD = 0.80      # 80 % pass rate required — hard block below this
MINIMUM_TEST_COUNT  = 10        # Minimum number of test results to be valid
ALLURE_BASE         = "allure-results"
OVERRIDE_FILE       = "qa_agent/.qa_override"

# Results must have been produced TODAY (same calendar date).
# An 8-hour stale window is no longer used — yesterday's results never count.
TODAY_ONLY = True

# At least one of these tags must appear in the allure results.
# Sanity / ad-hoc runs are NOT sufficient to unblock a push.
REGRESSION_TAGS = {"regression", "uiregression", "apiregression"}


# ── Result discovery ──────────────────────────────────────────────────────────

def find_latest_results_dir():
    base = Path(ALLURE_BASE)
    if not base.exists() or not base.is_dir():
        return None, None, 0

    best_dir   = None
    best_time  = 0
    best_count = 0

    for subdir in base.iterdir():
        if not subdir.is_dir():
            continue
        result_files = list(subdir.glob("*-result.json"))
        if not result_files:
            continue
        newest = max(p.stat().st_mtime for p in result_files)
        if newest > best_time:
            best_time  = newest
            best_dir   = subdir
            best_count = len(result_files)

    # Also check the base dir itself
    result_files = list(base.glob("*-result.json"))
    if result_files:
        newest = max(p.stat().st_mtime for p in result_files)
        if newest > best_time:
            best_time  = newest
            best_dir   = base
            best_count = len(result_files)

    if best_dir is None:
        return None, None, 0

    age_hours = (time.time() - best_time) / 3600.0
    return str(best_dir), age_hours, best_count


def _is_today(age_hours: float) -> bool:
    """Return True if the result timestamp falls on today's calendar date."""
    from datetime import timedelta
    result_dt = datetime.now() - timedelta(hours=age_hours)
    return result_dt.date() == date.today()


# ── Allure result parsing ──────────────────────────────────────────────────────

def _derive_test_file(full_name):
    if not full_name:
        return None
    parts = full_name.split('.')
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].endswith('_test'):
            return '/'.join(parts[: i + 1]) + '.py'
    return None


def read_allure_results(results_dir):
    total        = 0
    passed       = 0
    failed       = 0
    broken       = 0
    skipped      = 0
    failed_tests = []
    all_tests    = []
    files_covered = set()
    tags_found   = set()

    for path in Path(results_dir).glob("*-result.json"):
        try:
            payload = json.loads(path.read_text(encoding='utf-8', errors='ignore'))
        except ValueError:
            continue

        status = payload.get('status')
        if status is None:
            continue

        total += 1
        name      = payload.get('name', '')
        full_name = payload.get('fullName', '')
        test_file = _derive_test_file(full_name)
        if test_file:
            files_covered.add(test_file)

        # Collect pytest markers stored as allure tag labels
        for label in payload.get('labels', []):
            if label.get('name') == 'tag':
                val = label.get('value', '').lower().strip()
                if val:
                    tags_found.add(val)

        entry = {'name': name, 'file': test_file, 'status': status}
        all_tests.append(entry)

        if status == 'passed':
            passed += 1
        elif status == 'failed':
            failed += 1
            failed_tests.append(entry)
        elif status == 'broken':
            broken += 1
            failed_tests.append(entry)
        elif status == 'skipped':
            skipped += 1

    effective_total = (total - skipped) if (total - skipped) > 0 else total
    pass_rate = (passed / effective_total) if effective_total else 0.0

    return {
        'total':         total,
        'passed':        passed,
        'failed':        failed,
        'broken':        broken,
        'skipped':       skipped,
        'pass_rate':     pass_rate,
        'failed_tests':  failed_tests,
        'all_tests':     all_tests,
        'files_covered': files_covered,
        'tags_found':    tags_found,
    }


# ── New-test validation ────────────────────────────────────────────────────────

def check_new_tests_ran(changed_files, results):
    new_test_files = [f for f in changed_files if f.endswith('_test.py')]
    not_run        = [f for f in new_test_files if f not in results['files_covered']]
    run_but_failed = sorted(set(
        e['file'] for e in results['failed_tests'] if e['file'] in new_test_files
    ))
    return {
        'new_test_files':      new_test_files,
        'not_run':             not_run,
        'run_but_failed':      run_but_failed,
        'all_new_tests_passed': not not_run and not run_but_failed,
    }


# ── Override file ─────────────────────────────────────────────────────────────

def check_override_exists():
    path = Path(OVERRIDE_FILE)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8', errors='ignore'))
    except ValueError:
        return None
    try:
        path.unlink()
    except OSError:
        pass
    return payload


# ── Main check ────────────────────────────────────────────────────────────────

def _base_result(status, block, override_allowed, results_dir, age_hours,
                 results=None, new_test_check=None, override=None, tag_info=None):
    r = results or {}
    return {
        'status':           status,
        'block':            block,
        'override_allowed': override_allowed,
        'results_dir':      results_dir,
        'age_hours':        age_hours,
        'pass_rate':        r.get('pass_rate', 0.0),
        'total':            r.get('total', 0),
        'passed':           r.get('passed', 0),
        'failed':           r.get('failed', 0) + r.get('broken', 0) if r else 0,
        'failed_tests':     r.get('failed_tests', []),
        'tags_found':       r.get('tags_found', set()),
        'new_test_check':   new_test_check or {},
        'override':         override,
        'tag_info':         tag_info or {},
    }


def check_results(changed_files, required_tests=None):
    """
    required_tests: list of specific test file paths (e.g. ['ui/tests/example_ui_test.py'])
                    that must appear in the allure results.  When None, only the tag + pass rate
                    checks are applied.  When the list has > 15 entries the specific coverage
                    check is skipped (full regression tag + count is sufficient for large sets).
    """
    results_dir, age_hours, result_count = find_latest_results_dir()

    # ── 1. No results at all ──────────────────────────────────────────────────
    if results_dir is None:
        return _base_result(
            'NO_RESULTS', block=True, override_allowed=False,
            results_dir=None, age_hours=0.0
        )

    # ── 2. Results not from today ─────────────────────────────────────────────
    if TODAY_ONLY and not _is_today(age_hours):
        override = check_override_exists()
        if override:
            return _base_result(
                'OVERRIDE_ACCEPTED', block=False, override_allowed=True,
                results_dir=results_dir, age_hours=age_hours, override=override
            )
        return _base_result(
            'NOT_TODAY', block=True, override_allowed=True,
            results_dir=results_dir, age_hours=age_hours
        )

    results = read_allure_results(results_dir)

    # ── 3. Insufficient test count ────────────────────────────────────────────
    effective_total = results['total'] - results['skipped']
    if effective_total < MINIMUM_TEST_COUNT:
        return _base_result(
            'INSUFFICIENT_RESULTS', block=True, override_allowed=False,
            results_dir=results_dir, age_hours=age_hours, results=results
        )

    # ── 4. Tag must be regression ─────────────────────────────────────────────
    regression_tags_present = REGRESSION_TAGS & results['tags_found']
    tag_info = {
        'required':  sorted(REGRESSION_TAGS),
        'found':     sorted(results['tags_found']),
        'matched':   sorted(regression_tags_present),
    }
    if not regression_tags_present:
        return _base_result(
            'WRONG_TAG', block=True, override_allowed=False,
            results_dir=results_dir, age_hours=age_hours,
            results=results, tag_info=tag_info
        )

    # ── 5. Specific test coverage check ──────────────────────────────────────
    #   When the impact set is small (≤ 15 tests), verify those exact test files
    #   appear in the allure results.  For large sets the tag + count check is
    #   sufficient — we don't require every single impacted test to have been run.
    new_test_check = check_new_tests_ran(changed_files, results)

    if required_tests and len(required_tests) <= 15:
        not_covered = [
            t for t in required_tests
            # Normalise both sides so path separators don't cause false misses
            if not any(t.replace('\\', '/') in c.replace('\\', '/')
                       or c.replace('\\', '/') in t.replace('\\', '/')
                       for c in results['files_covered'])
        ]
        if not_covered:
            override = check_override_exists()
            if override:
                return _base_result(
                    'OVERRIDE_ACCEPTED', block=False, override_allowed=True,
                    results_dir=results_dir, age_hours=age_hours,
                    results=results, new_test_check=new_test_check,
                    override=override, tag_info=tag_info
                )
            return {
                **_base_result(
                    'REQUIRED_TESTS_NOT_RUN', block=True, override_allowed=True,
                    results_dir=results_dir, age_hours=age_hours,
                    results=results, new_test_check=new_test_check, tag_info=tag_info
                ),
                'not_covered': not_covered,
                'suggested_command': (
                    'pytest ' +
                    ' '.join(t for t in not_covered) +
                    ' --test-env=uat --alluredir=allure-results/local'
                ),
            }
    else:
        # Fall back to the original new-test check for large / unconstrained sets
        if new_test_check['not_run']:
            return _base_result(
                'NEW_TESTS_NOT_RUN', block=True, override_allowed=False,
                results_dir=results_dir, age_hours=age_hours,
                results=results, new_test_check=new_test_check, tag_info=tag_info
            )

    if new_test_check['run_but_failed']:
        return _base_result(
            'NEW_TESTS_FAILED', block=True, override_allowed=False,
            results_dir=results_dir, age_hours=age_hours,
            results=results, new_test_check=new_test_check, tag_info=tag_info
        )

    if results['failed'] > 0:
        return _base_result(
            'FAILED_TESTS', block=True, override_allowed=False,
            results_dir=results_dir, age_hours=age_hours,
            results=results, new_test_check=new_test_check, tag_info=tag_info
        )

    # ── 6. Pass rate must be >= 80 % — hard block (no silent warning) ─────────
    override = check_override_exists()
    if results['pass_rate'] < PASS_RATE_THRESHOLD:
        if override:
            return _base_result(
                'OVERRIDE_ACCEPTED', block=False, override_allowed=True,
                results_dir=results_dir, age_hours=age_hours,
                results=results, new_test_check=new_test_check,
                override=override, tag_info=tag_info
            )
        return _base_result(
            'BELOW_THRESHOLD', block=True, override_allowed=True,
            results_dir=results_dir, age_hours=age_hours,
            results=results, new_test_check=new_test_check, tag_info=tag_info
        )

    # ── All checks passed ─────────────────────────────────────────────────────
    return _base_result(
        'PASSED', block=False, override_allowed=False,
        results_dir=results_dir, age_hours=age_hours,
        results=results, new_test_check=new_test_check,
        override=override, tag_info=tag_info
    )
