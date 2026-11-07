import ast
import json
import re
import glob
from pathlib import Path
from datetime import date

SCAN_DIRS = [
    'api/tests', 'api/utils', 'api/data',
    'ui/tests', 'ui/pages', 'ui/utils', 'common', 'DB'
]
CONFTEST_FILES = ['conftest.py', 'api/conftest.py']
INTERNAL_PREFIXES = ('api', 'ui', 'common', 'DB')
BRAIN_PATH = Path(__file__).parent / 'repo_brain.json'


def _normalize_module(name):
    if name.startswith('api.') or name.startswith('ui.') or name.startswith('common.') or name.startswith('DB.'):
        return name.replace('.', '/') + '.py'
    return None


def _scan_files():
    root = Path.cwd()
    files = []
    for scan_dir in SCAN_DIRS:
        for path in sorted(root.glob(f'{scan_dir}/**/*.py')):
            files.append(path)
    for filename in CONFTEST_FILES:
        path = root / filename
        if path.exists():
            files.append(path)
    return sorted(set(files))


def _parse_imports(path):
    imports = []
    text = path.read_text(encoding='utf-8', errors='ignore')
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(INTERNAL_PREFIXES):
                    normalized = _normalize_module(alias.name)
                    if normalized:
                        imports.append(normalized)
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            if module and module.startswith(INTERNAL_PREFIXES):
                normalized = _normalize_module(module)
                if normalized:
                    imports.append(normalized)
    return sorted(set(imports))


def _collect_dependencies(files):
    imports = {}
    imported_by = {}
    for path in files:
        key = str(path.relative_to(Path.cwd())).replace('\\', '/')
        imports[key] = _parse_imports(path)
        for target in imports[key]:
            imported_by.setdefault(target, []).append(key)
    return imports, imported_by


def _bfs_dependent_counts(imported_by):
    counts = {}
    for node in imported_by:
        visited = set()
        queue = list(imported_by.get(node, []))
        while queue:
            current = queue.pop(0)
            if current not in visited:
                visited.add(current)
                for parent in imported_by.get(current, []):
                    if parent not in visited:
                        queue.append(parent)
        counts[node] = len(visited)
    return counts


def _detect_circular(imports):
    circular = []
    for src, targets in imports.items():
        for target in targets:
            if target in imports and src in imports.get(target, []):
                circular.append([src, target, src])
    unique = []
    seen = set()
    for entry in circular:
        key = tuple(entry)
        if key not in seen:
            seen.add(key)
            unique.append(entry)
    return unique


def _detect_test_imports(imports):
    test_imports = {}
    for src, targets in imports.items():
        if src.endswith('_test.py'):
            imported_tests = [t for t in targets if t.endswith('_test.py')]
            if imported_tests:
                test_imports[src] = imported_tests
    return test_imports


def _load_existing_markers():
    if not BRAIN_PATH.exists():
        return []
    try:
        payload = json.loads(BRAIN_PATH.read_text(encoding='utf-8'))
        return payload.get('markers', [])
    except ValueError:
        return []


def main():
    files = _scan_files()
    imports, imported_by = _collect_dependencies(files)
    counts = _bfs_dependent_counts(imported_by)
    high_impact = dict(sorted(
        ((k, v) for k, v in counts.items()),
        key=lambda item: (-item[1], item[0])
    )[:15])
    circular_dependencies = _detect_circular(imports)
    test_imports_test = _detect_test_imports(imports)
    markers = _load_existing_markers()
    brain = {
        'version': '1.0',
        'generated': date.today().isoformat(),
        'high_impact_files': high_impact,
        'circular_dependencies': circular_dependencies,
        'test_imports_test': test_imports_test,
        'imports': imports,
        'imported_by': imported_by,
        'markers': markers
    }
    BRAIN_PATH.write_text(json.dumps(brain, indent=2), encoding='utf-8')
    print(f'[update_brain] Scanned {len(files)} files')
    print(f'[update_brain] High impact files: {len(high_impact)}')
    print(f'[update_brain] Circular deps: {len(circular_dependencies)}')
    print(f'[update_brain] Test-imports-test: {len(test_imports_test)}')
    print(f'[update_brain] Brain updated: {BRAIN_PATH}')


if __name__ == '__main__':
    main()
