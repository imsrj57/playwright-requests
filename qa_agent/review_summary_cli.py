"""
CLI to manage `qa_agent/review_summary.json` and optionally post it to a GitHub PR.

Usage:
  python qa_agent/review_summary_cli.py ack        # set user_acknowledged = true
  python qa_agent/review_summary_cli.py apply      # set user_changes_applied = true
  python qa_agent/review_summary_cli.py show       # print the summary
  python qa_agent/review_summary_cli.py post-pr --pr 123 [--token ENV_VAR]

`post-pr` requires GITHUB_TOKEN env var by default; you can pass a different env var name with --token.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REVIEW_FILE = Path(__file__).parent / 'review_summary.json'


def load_summary():
    if not REVIEW_FILE.exists():
        print('No review summary found at', REVIEW_FILE)
        sys.exit(1)
    with REVIEW_FILE.open('r', encoding='utf-8') as f:
        return json.load(f)


def write_summary(data):
    with REVIEW_FILE.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print('Wrote', REVIEW_FILE)


def cmd_ack(args):
    data = load_summary()
    data['user_acknowledged'] = True
    write_summary(data)


def cmd_apply(args):
    data = load_summary()
    data['user_changes_applied'] = True
    write_summary(data)


def cmd_show(args):
    data = load_summary()
    print(json.dumps(data, indent=2))


def _get_repo_info():
    try:
        url = subprocess.check_output(['git', 'config', '--get', 'remote.origin.url'], text=True).strip()
    except Exception as e:
        raise RuntimeError('Failed to read git remote: ' + str(e))
    # common formats: git@github.com:owner/repo.git or https://github.com/owner/repo.git
    if url.startswith('git@'):
        # git@github.com:owner/repo.git
        _, path = url.split(':', 1)
        owner_repo = path.rstrip('.git')
    else:
        # https://github.com/owner/repo.git
        owner_repo = url.split('github.com/')[-1].rstrip('.git')
    if '/' not in owner_repo:
        raise RuntimeError('Unrecognized remote.origin.url format: ' + url)
    owner, repo = owner_repo.split('/', 1)
    return owner, repo


def cmd_post_pr(args):
    try:
        owner, repo = _get_repo_info()
    except Exception as e:
        print('Error discovering repo info:', e)
        sys.exit(1)

    pr_number = args.pr
    token_env = args.token or 'GITHUB_TOKEN'
    token = os.environ.get(token_env)
    if not token:
        print(f'Environment variable {token_env} not found. Set it to a GitHub token with repo scope.')
        sys.exit(1)

    try:
        import requests
    except Exception:
        print('requests library is required to post to GitHub. Please install it (requirements.txt updated).')
        sys.exit(1)

    data = load_summary()
    body = 'Review Agent Summary:\n\n```json\n' + json.dumps(data, indent=2) + '\n```\n'
    api = f'https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments'
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    resp = requests.post(api, headers=headers, json={'body': body})
    if resp.status_code in (200, 201):
        print('Posted review summary as comment to PR', pr_number)
    else:
        print('Failed to post comment:', resp.status_code, resp.text)
        sys.exit(1)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd')

    sub.add_parser('ack')
    sub.add_parser('apply')
    sub.add_parser('show')

    post = sub.add_parser('post-pr')
    post.add_argument('--pr', required=True, type=int, help='Pull request number')
    post.add_argument('--token', help='Environment variable name that holds GitHub token (default GITHUB_TOKEN)')

    args = p.parse_args()
    if args.cmd == 'ack':
        cmd_ack(args)
    elif args.cmd == 'apply':
        cmd_apply(args)
    elif args.cmd == 'show':
        cmd_show(args)
    elif args.cmd == 'post-pr':
        cmd_post_pr(args)
    else:
        p.print_help()


if __name__ == '__main__':
    main()
