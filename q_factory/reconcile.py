"""Preview or apply an explicitly bounded GitHub PR/Jyra reconciliation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import UUID

import httpx

from . import settings as factory_settings
from .client import Client
from .git import FactoryError, factory_root, git, project

SYNC_ACTOR = 'factory-github-reconcile'
UUID4 = r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'
REPO = r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+'
PR_URL = re.compile(r'https://github\.com/(' + REPO + r')/pull/([1-9][0-9]*)\Z')
LINK = re.compile(r'Jyra-Ticket: (' + UUID4 + r')\Z')
SHA = re.compile(r'[0-9a-f]{40}\Z')
RECEIPT = re.compile(r'Factory-GitHub-Receipt: (' + UUID4 + r')\Z')


def canonical_uuid(value: str) -> str:
    if not re.fullmatch(UUID4, value):
        raise FactoryError('Ticket, board and preview identifiers must be canonical UUIDv4 values.')
    return value


def repository(url: str) -> str:
    match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:)(' + REPO + r')', url)
    if not match:
        raise FactoryError('The registered origin must be a GitHub HTTPS or SSH repository without embedded credentials.')
    value = match[1]
    return value[:-4] if value.endswith('.git') else value


def links(text: str, *, trailer: bool = False) -> set[str]:
    """Only exact declarations outside code fences; commits need a final trailer block."""
    if not isinstance(text, str):
        raise FactoryError('GitHub returned invalid linkage text.')
    original = text.rstrip().splitlines()
    visible, fence, comment = [], None, False
    for line in original:
        delimiter = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        if delimiter and not comment:
            marker, rest = delimiter.groups()
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1] and not rest.strip():
                fence = None
            visible.append(None)
            continue
        if fence is not None:
            visible.append(None)
            continue
        hidden = comment or '<!--' in line
        if '<!--' in line:
            comment = True
        if '-->' in line:
            comment = False
        visible.append(None if hidden else line)
    start = 0
    if trailer:
        start = len(original)
        while start and original[start - 1].strip():
            start -= 1
        if start == 0 or not any(line.strip() for line in original[:start]):
            return set()
        if any(line is None or not re.fullmatch(r'[A-Za-z][A-Za-z-]*: .+', line)
               for line in visible[start:]):
            return set()
    result = set()
    for line in visible[start:]:
        if line is not None and line.startswith('Jyra-Ticket:'):
            match = LINK.fullmatch(line)
            if not match:
                raise FactoryError('Malformed Jyra-Ticket linkage; use one canonical UUIDv4 per exact declaration line.')
            result.add(match[1])
    return result


class GitHub:
    """Outbound read-only gh API access, with full list pagination and no shell."""
    def get(self, endpoint: str, *, pages: bool = False):
        args = ['gh', 'api', '--hostname', 'github.com']
        if pages:
            args += ['--paginate']
        args.append(endpoint)
        env = {k: v for k, v in os.environ.items() if k != 'GH_DEBUG'}
        env['GH_PROMPT_DISABLED'] = '1'
        try:
            response = subprocess.run(args, capture_output=True, text=True, timeout=60, env=env)
        except (OSError, subprocess.TimeoutExpired):
            raise FactoryError('GitHub read failed; verify local gh authentication and connectivity.') from None
        if response.returncode:
            raise FactoryError('GitHub read failed; verify local gh authentication, repository access and PR identity.')
        try:
            if not pages:
                data = json.loads(response.stdout)
                if not isinstance(data, dict):
                    raise FactoryError('GitHub returned an invalid object.')
                return data
            # gh --paginate emits one complete JSON value per page. Decode the
            # stream directly: --slurp is absent from the installed gh 2.32 and
            # must not turn a supported read into a misleading auth failure.
            decoder, offset, data = json.JSONDecoder(), 0, []
            while offset < len(response.stdout):
                if response.stdout[offset].isspace():
                    offset += 1
                    continue
                page, offset = decoder.raw_decode(response.stdout, offset)
                if not isinstance(page, list):
                    raise FactoryError('GitHub returned invalid paginated data.')
                data.append(page)
            if not data:
                raise FactoryError('GitHub returned no pagination response.')
        except ValueError:
            raise FactoryError('GitHub returned invalid JSON or pagination data.') from None
        items = [item for page in data for item in page]
        if any(not isinstance(item, dict) for item in items):
            raise FactoryError('GitHub returned invalid list items.')
        return items


def stamp(body: str, **scope):
    # Shared exact-head protocol, deliberately not inferred from PR prose.
    from .review_state import parse_stamp
    return parse_stamp(body, **scope)


def review_verdict(reviews: list[dict], repo: str, number: int, head: str, base: str, authors: set[str]) -> str:
    protocols, blockers, seen = {}, {}, set()
    for review in sorted(reviews, key=lambda r: (r.get('submitted_at') or '', r.get('id', 0))):
        identity = review.get('id')
        if identity in seen or identity is None:
            raise FactoryError('GitHub review pagination repeated or omitted an identity.')
        seen.add(identity)
        state = review.get('state')
        if state == 'PENDING':
            continue
        body = review.get('body') or ''
        author = (review.get('user') or {}).get('login', '').lower()
        current = review.get('commit_id') == head
        if state == 'CHANGES_REQUESTED':
            blockers[author] = 'unknown'
        elif state in {'APPROVED', 'DISMISSED'}:
            blockers.pop(author, None)
        if state == 'DISMISSED':
            protocols.pop(author, None)
            continue
        if 'factory-review:v1' in body and author in authors and current:
            try:
                parsed = stamp(body, repository=repo, pr=number, head=head, base=base)
            except FactoryError:
                protocols[author] = {'verdict': 'unknown', 'round': 0}
            else:
                previous = protocols.get(author)
                if previous is not None and parsed['round'] < previous['round']:
                    raise FactoryError('Review rounds moved backwards; inspect the PR review history.')
                protocols[author] = parsed
                if author in blockers and parsed['verdict'] == 'changes-requested':
                    blockers[author] = 'changes-requested'
    verdicts = list(blockers.values()) + [value['verdict'] for value in protocols.values()]
    if any(value == 'unknown' for value in blockers.values()):
        return 'unknown'
    if 'changes-requested' in verdicts:
        return 'changes-requested'
    return 'approved' if verdicts and all(value == 'approved' for value in verdicts) else 'unknown'


def normalize_pr(url: str, repo: str) -> tuple[str, int]:
    match = PR_URL.fullmatch(url)
    if not match or match[1].lower() != repo.lower():
        raise FactoryError('Every selected PR must belong to the registered project repository.')
    number = int(match[2])
    return f'https://github.com/{repo}/pull/{number}', number


def pull_snapshot(github: GitHub, url: str, repo: str, ticket_id: str, authors: set[str]) -> dict:
    url, number = normalize_pr(url, repo)
    endpoint = f'repos/{repo}/pulls/{number}'
    pull = github.get(endpoint)
    if pull.get('number') != number or (pull.get('base', {}).get('repo') or {}).get('full_name', '').lower() != repo.lower():
        raise FactoryError('GitHub PR identity does not match the selected repository.')
    if links(pull.get('body') or '') != {ticket_id}:
        raise FactoryError('The PR body must explicitly link exactly the selected Jyra ticket.')
    head, base = pull.get('head', {}).get('sha'), pull.get('base', {}).get('sha')
    if not isinstance(head, str) or not SHA.fullmatch(head) or not isinstance(base, str) or not SHA.fullmatch(base):
        raise FactoryError('GitHub returned invalid PR revision identities.')
    commits = github.get(endpoint + '/commits?per_page=100', pages=True)
    commit_ids = [c.get('sha') for c in commits]
    if type(pull.get('commits')) is not int or len(commits) != pull['commits'] or len(set(commit_ids)) != len(commit_ids):
        raise FactoryError('PR commit pagination is incomplete or repeated; this PR cannot be reconciled automatically.')
    if not commits or commit_ids[-1] != head:
        raise FactoryError('PR head changed or commit listing is stale; retry the preview.')
    declared = set()
    for commit in commits:
        declared |= links(commit.get('commit', {}).get('message', ''), trailer=True)
    if declared != {ticket_id}:
        raise FactoryError('Current PR commits must have final Jyra-Ticket trailers linking only the selected ticket.')
    reviews = github.get(endpoint + '/reviews?per_page=100', pages=True)
    verdict = review_verdict(reviews, repo, number, head, base, authors)
    state = ('merged' if pull.get('merged') else 'closed-unmerged' if pull.get('state') == 'closed'
             else 'draft' if pull.get('draft') else 'open')
    if pull.get('state') not in {'open', 'closed'}:
        raise FactoryError('GitHub returned an unknown PR state.')
    # Recheck immutable scope and mutable head/base/state after paginated reads.
    latest = github.get(endpoint)
    for key in ('head', 'base', 'state', 'merged', 'draft', 'body', 'commits', 'updated_at'):
        if latest.get(key) != pull.get(key):
            raise FactoryError('PR changed during reconciliation; retry the preview.')
    return {'url': f'https://github.com/{repo}/pull/{number}', 'head': head, 'base': base,
            'state': state, 'verdict': verdict,
            'reviews': [{'id': r.get('id'), 'state': r.get('state'), 'commit_id': r.get('commit_id'),
                         'body_digest': hashlib.sha256((r.get('body') or '').encode()).hexdigest(),
                         'author': (r.get('user') or {}).get('login')} for r in reviews]}


def scope(root: Path, client: Client, selector: str | None, board_id: str, own: bool,
          identity: factory_settings.SelfIdentity | None = None):
    """Resolve the repository to reconcile.

    `own` (the --self flag) reconciles the factory repository itself against
    its documented Jyra identity from q-factory.toml; it replaced the
    hard-coded ids from before the factory split from an earlier repository.
    """
    canonical_uuid(board_id)
    if own:
        identity = identity or factory_settings.load(root).self_identity
        if board_id != identity.board_id:
            raise FactoryError('--self requires the board documented in q-factory.toml.')
        entity = client.get('/entities/' + identity.project_id)
        board = client.get('/boards/' + board_id)
        # The detail endpoint embeds entity metadata; only the board listing
        # returns the flat entity_id used by Client.resolve for managed projects.
        associated = board.get('entity')
        if (entity.get('type') != 'project' or entity.get('id') != identity.project_id
                or board.get('id') != board_id or not isinstance(associated, dict)
                or associated.get('id') != identity.project_id or associated.get('type') != 'project'):
            raise FactoryError('Factory project/board association does not match q-factory.toml.')
        repo_path = root
    else:
        entity, board = client.resolve(selector, board_id)
        repo_path = project(root, entity['attributes']['repository_path'])['path']
    result = repository(git(repo_path, 'remote', 'get-url', 'origin'))
    if own and result.lower() != identity.repository:
        raise FactoryError('--self requires the repository origin documented in q-factory.toml.')
    return result


def preview(client: Client, github: GitHub, *, repo: str, board_id: str, ticket_id: str,
            urls: list[str], actor: str, authors: set[str], advance_owned: bool = False) -> dict:
    canonical_uuid(ticket_id)
    canonical_uuid(board_id)
    ticket = client.ticket(ticket_id, board_id)
    history = client.all(f'/tickets/{ticket_id}/transitions')
    if not history or history[-1].get('to_status') != ticket.get('status'):
        raise FactoryError('Ticket/history snapshot changed or is incomplete; retry the preview.')
    token = canonical_uuid(history[-1]['id'])
    # Discover only explicit links already recorded by this tool. The command
    # intentionally does not claim to discover every PR on GitHub for a ticket.
    known = set()
    for row in history:
        if row.get('actor') == SYNC_ACTOR:
            for line in (row.get('note') or '').splitlines():
                if line.startswith('GitHub-PR: '):
                    known.add(line[11:])
    urls = sorted({normalize_pr(url, repo)[0] for url in urls})
    known = {normalize_pr(url, repo)[0] for url in known}
    if not urls or not known.issubset(urls):
        raise FactoryError('Supply every previously linked PR plus the explicitly selected PRs; omitted links cannot be reconciled.')
    snapshots = [pull_snapshot(github, url, repo, ticket_id, authors) for url in urls]
    receipt_data = {'repo': repo, 'ticket': ticket_id, 'prs': snapshots, 'actor': actor,
                    'authors': sorted(authors), 'advance_owned': advance_owned}
    receipt = str(UUID(bytes=hashlib.sha256(json.dumps(receipt_data, sort_keys=True).encode()).digest()[:16], version=4))
    duplicate = any(row.get('actor') == SYNC_ACTOR and (row.get('note') or '').splitlines()[:1] ==
                    ['Factory-GitHub-Receipt: ' + receipt] for row in history)
    owner = next((row.get('actor') for row in reversed(history) if row.get('actor') != SYNC_ACTOR), None)
    target = ticket['status']
    if (advance_owned and owner == actor and ticket.get('claimed_by') == actor
            and target in {'agent_coding', 'in_progress', 'review'}):
        if any(p['verdict'] == 'changes-requested' and p['state'] == 'open' for p in snapshots):
            target = 'in_progress'
        elif all(p['state'] in {'open', 'merged'} and p['verdict'] == 'approved' for p in snapshots):
            target = 'review'
    note = '\n'.join(['Factory-GitHub-Receipt: ' + receipt, 'Jyra-Ticket: ' + ticket_id] +
                     [f"GitHub-PR: {p['url']}\nGitHub-State: {p['state']}; review {p['verdict']}" for p in snapshots] +
                     ['Recorded selected PR evidence; completion and acceptance remain separate.'])
    return {'ticket_id': ticket_id, 'repository': repo, 'expected_transition_id': token,
            'receipt': receipt, 'from_status': ticket['status'], 'to_status': target,
            'owner': owner, 'already_applied': duplicate, 'prs': snapshots, 'note': note}


def apply(client: Client, plan: dict, expected_transition: str, expected_receipt: str) -> dict:
    canonical_uuid(expected_transition)
    canonical_uuid(expected_receipt)
    if plan['receipt'] != expected_receipt:
        raise FactoryError('GitHub evidence or reconciliation policy changed; inspect a new preview.')
    if plan['already_applied']:
        return {'applied': False, 'already_applied': True, 'receipt': plan['receipt']}
    if plan['expected_transition_id'] != expected_transition:
        raise FactoryError('Jyra history changed since preview; inspect it before applying.')
    try:
        response = client.http.post(f"/tickets/{plan['ticket_id']}/transition", json={
            'to_status': plan['to_status'], 'actor': SYNC_ACTOR, 'note': plan['note'],
            'expected_transition_id': expected_transition})
        response.raise_for_status()
        result = response.json()
    except httpx.HTTPStatusError as exc:
        raise FactoryError(f'Reconciliation write refused (HTTP {exc.response.status_code}); preview current state before retrying.') from None
    except (httpx.HTTPError, ValueError):
        raise FactoryError('Reconciliation result is unknown; preview history before retrying. The receipt detects a completed write.') from None
    if not isinstance(result, dict) or result.get('id') != plan['ticket_id'] or result.get('status') != plan['to_status']:
        raise FactoryError('Reconciliation response was incomplete; preview history before retrying.')
    return {'applied': True, 'receipt': plan['receipt'], 'ticket_id': result['id'], 'status': result['status']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--api-url', help='q-core API origin; defaults to q-factory.toml')
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--project')
    selection.add_argument('--self', dest='own', action='store_true',
                           help='reconcile the factory repository itself (identity from q-factory.toml)')
    parser.add_argument('--board', required=True)
    parser.add_argument('--ticket', required=True)
    parser.add_argument('--pr', action='append', required=True)
    parser.add_argument('--actor', default='factory-worker')
    parser.add_argument('--review-author', action='append', default=[])
    parser.add_argument('--advance-owned', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-transition')
    parser.add_argument('--expected-receipt')
    args = parser.parse_args(argv)
    client = None
    try:
        if args.apply and (not args.expected_transition or not args.expected_receipt):
            raise FactoryError('--apply requires both preview --expected-transition and --expected-receipt UUIDs.')
        if not args.actor.strip() or args.actor == SYNC_ACTOR:
            raise FactoryError('Supply the worker actor; the reconciliation actor is reserved for receipts.')
        root = factory_root(args.root)
        config = factory_settings.load(root)
        client = Client(args.api_url or config.api_url, factory_settings.api_token(root), tailnet=config.tailnet)
        repo = scope(root, client, args.project, args.board, args.own, config.self_identity)
        plan = preview(client, GitHub(), repo=repo, board_id=args.board, ticket_id=args.ticket,
                       urls=args.pr, actor=args.actor, authors={a.lower() for a in args.review_author},
                       advance_owned=args.advance_owned)
        result = apply(client, plan, args.expected_transition, args.expected_receipt) if args.apply else plan
        print(json.dumps(result, indent=2))
        return 0
    except (FactoryError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        message = str(exc) if isinstance(exc, FactoryError) else 'Reconciliation failed; inspect local configuration.'
        print(json.dumps({'error': message}), file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == '__main__':
    raise SystemExit(main())
