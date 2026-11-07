import ast
import re
from pathlib import Path

# Keep in sync with the markers registered in pytest.ini
VALID_MARKERS = [
    "sanity", "regression", "apisanity", "apiregression",
    "uisanity", "uiregression", "db", "example",
]

HARDCODE_PATTERNS = [
    r'https?://',
    r'password\s*=\s*["\'][^"\']+',
    r'client_id\s*=\s*["\'][^"\']+',
    r'username\s*=\s*["\'][^"\']+'
]

FIXTURE_NAMES = [
    "base", "config", "ui_config", "api_config", "api_client", "db_conn",
]


def _get_functions(tree):
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            functions.append(node)
    return functions


def _has_marker(node):
    for deco in node.decorator_list:
        if isinstance(deco, ast.Attribute) and getattr(deco.value, 'id', '') == 'pytest':
            if deco.attr in VALID_MARKERS or deco.attr == 'mark':
                return True
        if isinstance(deco, ast.Call):
            func = deco.func
            if isinstance(func, ast.Attribute) and getattr(func.value, 'id', '') == 'pytest':
                if func.attr in VALID_MARKERS or func.attr == 'mark':
                    return True
    return False


def _has_asyncio_marker(node):
    for deco in node.decorator_list:
        if isinstance(deco, ast.Attribute):
            if getattr(deco.value, 'id', '') == 'pytest' and deco.attr == 'mark':
                return True
        if isinstance(deco, ast.Call):
            func = deco.func
            if isinstance(func, ast.Attribute):
                if getattr(func.value, 'id', '') == 'pytest' and func.attr == 'mark':
                    for arg in deco.args:
                        if isinstance(arg, ast.Attribute) and arg.attr == 'asyncio':
                            return True
                        if isinstance(arg, ast.Name) and arg.id == 'asyncio':
                            return True
    return False


def _has_allure_step(node):
    for deco in node.decorator_list:
        if isinstance(deco, ast.Attribute):
            if getattr(deco.value, 'id', '') == 'allure' and deco.attr == 'step':
                return True
        if isinstance(deco, ast.Call):
            func = deco.func
            if isinstance(func, ast.Attribute):
                if getattr(func.value, 'id', '') == 'allure' and func.attr == 'step':
                    return True
    return False


def _extract_source_lines(source):
    return source.splitlines()


def _line_contains_hardcode(line):
    if line.strip().startswith('#'):
        return False
    for pattern in HARDCODE_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def _find_function_calls(tree):
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.add(func.id)
            elif isinstance(func, ast.Attribute):
                calls.add(func.attr)
    return calls


def _collect_function_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            names.add(node.name)
    return names


def check_file(filepath):
    filepath = Path(filepath)
    if filepath.suffix != '.py' or not filepath.name.endswith('_test.py'):
        return []

    source = filepath.read_text(encoding='utf-8', errors='ignore')
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [{
            'rule': 'SYNTAX',
            'line': 0,
            'message': 'Unable to parse file for quality checks',
            'severity': 'error'
        }]

    violations = []
    function_nodes = _get_functions(tree)
    call_map = _find_function_calls(tree)
    defined_names = _collect_function_names(tree)
    lines = _extract_source_lines(source)

    for node in function_nodes:
        name = node.name
        is_test = name.startswith('test_')
        if is_test:
            if not _has_marker(node):
                violations.append({
                    'rule': 'MARKER',
                    'line': node.lineno,
                    'message': 'Add one of: @pytest.mark.uiregression, @pytest.mark.sanity, @pytest.mark.regression, etc.',
                    'severity': 'error'
                })
            if isinstance(node, ast.AsyncFunctionDef) and not _has_asyncio_marker(node):
                violations.append({
                    'rule': 'ASYNC_MARKER',
                    'line': node.lineno,
                    'message': 'Add @pytest.mark.asyncio to async test function',
                    'severity': 'error'
                })
            for child in ast.walk(node):
                if isinstance(child, ast.Assert):
                    test_source = ast.get_source_segment(source, child) or ''
                    if any(token in test_source for token in ('assert True', 'assert False', 'assert 1==1', 'assert None')):
                        violations.append({
                            'rule': 'ASSERTION',
                            'line': child.lineno,
                            'message': 'Replace with a meaningful assertion',
                            'severity': 'error'
                        })
                if isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant):
                    pass
            for lineno in range(node.lineno - 1, getattr(node, 'end_lineno', node.lineno)):
                if lineno < 0 or lineno >= len(lines):
                    continue
                line = lines[lineno]
                if _line_contains_hardcode(line):
                    if not any(name in line for name in FIXTURE_NAMES):
                        violations.append({
                            'rule': 'HARDCODE',
                            'line': lineno + 1,
                            'message': 'Move to config/qa.json or uat.json and use the config fixture instead',
                            'severity': 'error'
                        })
                        break
        elif name not in ('__init__', '__str__'):
            if name in call_map and not _has_allure_step(node):
                violations.append({
                    'rule': 'ALLURE_STEP',
                    'line': node.lineno,
                    'message': 'Add @allure.step decorator for Allure reporting',
                    'severity': 'warning'
                })

    return violations


def check_changed_files(changed_files):
    violations = {}
    total_errors = 0
    total_warnings = 0
    for filepath in changed_files:
        if not filepath.endswith('_test.py'):
            continue
        file_path = Path(filepath)
        if not file_path.exists():
            continue
        file_violations = check_file(file_path)
        if file_violations:
            violations[filepath] = file_violations
            for violation in file_violations:
                if violation['severity'] == 'error':
                    total_errors += 1
                else:
                    total_warnings += 1
    return {
        'violations': violations,
        'total_errors': total_errors,
        'total_warnings': total_warnings,
        'has_blocking_errors': total_errors > 0
    }
