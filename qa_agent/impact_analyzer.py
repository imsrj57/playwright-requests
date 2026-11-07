import json
from pathlib import Path
from collections import deque

BRAIN_PATH = Path(__file__).parent / "repo_brain.json"


def _normalize(path):
    return path.replace('\\', '/').lstrip('./')


def load_brain():
    if not BRAIN_PATH.exists():
        return {
            'high_impact_files': {},
            'imported_by': {},
            'test_imports_test': {}
        }
    with BRAIN_PATH.open('r', encoding='utf-8') as handle:
        return json.load(handle)


def _collect_dependents(brain, changed_file):
    imported_by = brain.get('imported_by', {})
    normalized = _normalize(changed_file)
    direct = list(imported_by.get(normalized, []))
    visited = set(direct)
    queue = deque(direct)
    while queue:
        current = queue.popleft()
        for parent in imported_by.get(current, []):
            if parent not in visited:
                visited.add(parent)
                queue.append(parent)
    return sorted(visited)


def _classify_tests(files):
    ui = []
    api = []
    for file in files:
        normalized = _normalize(file)
        if normalized.startswith('ui/tests/') and normalized.endswith('_test.py'):
            ui.append(normalized)
        elif normalized.startswith('api/tests/') and normalized.endswith('_test.py'):
            api.append(normalized)
    return sorted(ui), sorted(api)


def _risk_level(brain, changed_file):
    normalized = _normalize(changed_file)
    score = brain.get('high_impact_files', {}).get(normalized, 0)
    if score >= 20:
        return 'HIGH'
    if score >= 10:
        return 'MEDIUM'
    if score > 0:
        return 'LOW'
    return 'NONE'


def _suggested_command(ui_tests, api_tests):
    if ui_tests and not api_tests:
        return 'pytest -m uiregression --test-env=uat'
    if api_tests and not ui_tests:
        return 'pytest -m apiregression --test-env=uat'
    if ui_tests and api_tests:
        return 'pytest -m regression --test-env=uat'
    return None


def get_impact(changed_files):
    brain = load_brain()
    all_dependents = set()
    warnings = []
    for changed_file in changed_files:
        normalized = _normalize(changed_file)
        dependents = _collect_dependents(brain, normalized)
        all_dependents.update(dependents)
        if brain.get('test_imports_test', {}).get(normalized):
            warnings.append(normalized)
    ui_tests, api_tests = _classify_tests(all_dependents)
    suggested_command = _suggested_command(ui_tests, api_tests)
    risk_levels = set(_risk_level(brain, f) for f in changed_files)
    if 'HIGH' in risk_levels:
        risk = 'HIGH'
    elif 'MEDIUM' in risk_levels:
        risk = 'MEDIUM'
    elif 'LOW' in risk_levels:
        risk = 'LOW'
    else:
        risk = 'NONE'
    return {
        'changed_files': [ _normalize(f) for f in changed_files ],
        'total_impacted': len(all_dependents),
        'risk_level': risk,
        'direct_dependents': sorted(set(sum((brain.get('imported_by', {}).get(_normalize(f), []) for f in changed_files), []))),
        'all_dependents': sorted(all_dependents),
        'impacted_ui_tests': ui_tests,
        'impacted_api_tests': api_tests,
        'test_imports_test_warnings': [brain.get('test_imports_test', {}).get(_normalize(f), []) for f in changed_files if brain.get('test_imports_test', {}).get(_normalize(f))],
        'suggested_command': suggested_command
    }
