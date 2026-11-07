import argparse
import json
import sys
import subprocess
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OVERRIDE_FILE = Path(__file__).parent / '.qa_override'


def _git_author():
    try:
        result = subprocess.run(
            ['git', 'config', 'user.name'],
            capture_output=True, text=True
        )
        return result.stdout.strip() or 'unknown'
    except Exception:
        return 'unknown'


def main():
    parser = argparse.ArgumentParser(description='Record QA push override reason')
    parser.add_argument('--reason', required=True, help='Reason for override')
    args = parser.parse_args()
    override = {
        'reason': args.reason,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'author': _git_author()
    }
    OVERRIDE_FILE.write_text(json.dumps(override, indent=2), encoding='utf-8')
    try:
        subprocess.run(['git', 'add', str(OVERRIDE_FILE)], check=False)
    except Exception:
        pass
    print('✅ Override recorded')
    print(f'Author:    {override["author"]}')
    print(f'Reason:    {override["reason"]}')
    print(f'Timestamp: {override["timestamp"]}')
    print('Now run: git push')
    print('This override is single-use and commits with your push.')


if __name__ == '__main__':
    main()
