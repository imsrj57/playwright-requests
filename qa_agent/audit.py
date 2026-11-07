import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

AUDIT_FILE = Path(__file__).parent / "qa_push_audit.json"
ORIGIN_MAIN = "origin/main"


def _run_git(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        check=check
    )


def get_current_branch() -> str | None:
    try:
        result = _run_git(['rev-parse', '--abbrev-ref', 'HEAD'])
        if result.returncode != 0:
            return None
        branch = result.stdout.strip()
        return branch if branch else None
    except Exception:
        return None


def get_head_sha() -> str | None:
    try:
        result = _run_git(['rev-parse', 'HEAD'])
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception:
        return None


def has_origin_remote() -> bool:
    try:
        result = _run_git(['remote', 'get-url', 'origin'])
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def fetch_origin_main() -> bool:
    if not has_origin_remote():
        return False
    try:
        result = _run_git(['fetch', '--quiet', 'origin', 'main'])
        return result.returncode == 0
    except Exception:
        return False


def get_origin_main_sha() -> str | None:
    try:
        result = _run_git(['rev-parse', '--verify', ORIGIN_MAIN])
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception:
        return None


def check_branch_alignment() -> dict[str, Any]:
    branch = get_current_branch() or 'DETACHED'
    head = get_head_sha() or 'unknown'
    origin_main = get_origin_main_sha()
    if origin_main is None:
        fetched = fetch_origin_main()
        origin_main = get_origin_main_sha()
        if origin_main is None:
            return {
                'branch': branch,
                'head': head,
                'origin_main': None,
                'status': 'origin_main_missing',
                'aligned': False,
                'behind': None,
                'ahead': None,
                'fetch_attempted': fetched,
            }

    try:
        result = _run_git(['rev-list', '--left-right', '--count', f'{ORIGIN_MAIN}...HEAD'])
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        parts = result.stdout.strip().split()
        if len(parts) != 2:
            raise RuntimeError('unexpected rev-list output')
        behind, ahead = int(parts[0]), int(parts[1])
        status = 'aligned' if behind == 0 else 'diverged' if ahead > 0 else 'behind'
        return {
            'branch': branch,
            'head': head,
            'origin_main': origin_main,
            'status': status,
            'aligned': behind == 0,
            'behind': behind,
            'ahead': ahead,
            'fetch_attempted': True,
        }
    except Exception:
        return {
            'branch': branch,
            'head': head,
            'origin_main': origin_main,
            'status': 'alignment_failed',
            'aligned': False,
            'behind': None,
            'ahead': None,
            'fetch_attempted': True,
        }


get_branch_alignment = check_branch_alignment


def _read_audit_entries() -> list[dict[str, Any]]:
    if not AUDIT_FILE.exists():
        return []
    try:
        payload = json.loads(AUDIT_FILE.read_text(encoding='utf-8'))
        if isinstance(payload, list):
            return payload
    except Exception:
        pass
    return []


def _write_audit_entries(entries: list[dict[str, Any]]) -> None:
    AUDIT_FILE.write_text(json.dumps(entries, indent=2), encoding='utf-8')


def get_last_audit_entry() -> dict[str, Any] | None:
    entries = _read_audit_entries()
    return entries[-1] if entries else None


def append_audit_entry(entry: dict[str, Any]) -> bool:
    last = get_last_audit_entry()
    if last and last.get('git', {}).get('head') == entry.get('git', {}).get('head'):
        return False
    entries = _read_audit_entries()
    entries.append(entry)
    _write_audit_entries(entries)
    try:
        _run_git(['add', str(AUDIT_FILE)])
    except Exception:
        pass
    return True


def audit_file_requires_commit() -> bool:
    try:
        dirty = _run_git(['diff', '--quiet', '--', str(AUDIT_FILE)])
        staged = _run_git(['diff', '--cached', '--quiet', '--', str(AUDIT_FILE)])
        return dirty.returncode != 0 or staged.returncode != 0
    except Exception:
        return False


def auto_amend_audit_file() -> bool:
    try:
        _run_git(['add', str(AUDIT_FILE)])
        result = _run_git(['commit', '--amend', '--no-edit', '--', str(AUDIT_FILE)])
        return result.returncode == 0
    except Exception:
        return False


def build_audit_entry(
    branch_alignment: dict[str, Any],
    changed_files: list[str],
    quality: dict[str, Any] | None = None,
    impact: dict[str, Any] | None = None,
    results: dict[str, Any] | None = None,
    final_status: str = 'unknown',
    blocked_reason: str | None = None,
    review_required: bool = False,
) -> dict[str, Any]:
    return {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'git': {
            'branch': branch_alignment.get('branch'),
            'head': branch_alignment.get('head'),
            'origin_main': branch_alignment.get('origin_main'),
            'alignment': {
                'status': branch_alignment.get('status'),
                'aligned': branch_alignment.get('aligned'),
                'behind': branch_alignment.get('behind'),
                'ahead': branch_alignment.get('ahead'),
            },
        },
        'changed_files': changed_files,
        'quality': {
            'blocking_errors': bool(quality and quality.get('has_blocking_errors')),
            'total_errors': quality.get('total_errors', 0) if quality else 0,
            'total_warnings': quality.get('total_warnings', 0) if quality else 0,
            'files_with_violations': sorted(quality.get('violations', {}).keys()) if quality else [],
        },
        'impact': {
            'risk_level': impact.get('risk_level') if impact else None,
            'total_impacted': impact.get('total_impacted') if impact else None,
            'impacted_ui_tests': impact.get('impacted_ui_tests', []) if impact else [],
            'impacted_api_tests': impact.get('impacted_api_tests', []) if impact else [],
            'suggested_command': impact.get('suggested_command') if impact else None,
        },
        'results': {
            'status': results.get('status') if results else None,
            'pass_rate': results.get('pass_rate') if results else None,
            'total': results.get('total') if results else None,
            'passed': results.get('passed') if results else None,
            'failed': results.get('failed') if results else None,
            'tags_found': sorted(results.get('tags_found', [])) if results else [],
            'not_covered': results.get('not_covered', []) if results else [],
            'override_used': bool(results and results.get('override')),
        },
        'review': {
            'required': review_required,
            'status': 'pending' if review_required else 'not_required',
            'note': 'Run the review agent for changed test files: AI/agents/review-test.md',
        },
        'final_status': final_status,
        'blocked_reason': blocked_reason,
    }
