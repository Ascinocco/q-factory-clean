"""On-demand factory commands; API access is read-only."""
import argparse
import json
from pathlib import Path
import sys
from uuid import UUID

from . import git
from .client import Client
from .status import report
from .integration import pin
from . import settings as factory_settings


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    cli.add_argument('--api-url', help='q-core API origin; defaults to [q_core] api_url in q-factory.toml')
    commands = cli.add_subparsers(dest='command', required=True)
    commands.add_parser('status')
    pin_command = commands.add_parser('pin')
    pin_command.add_argument('--project', required=True)
    pin_command.add_argument('--board')
    pin_command.add_argument('--commit', required=True)
    pin_command.add_argument('--expected-old', required=True)
    worktree = commands.add_parser('worktree').add_subparsers(dest='action', required=True)
    for action in ('start', 'finish', 'list'):
        cmd = worktree.add_parser(action)
        cmd.add_argument('--project', required=True)
        cmd.add_argument('--board', help='Associated board ID (required when more than one exists)')
        if action != 'list':
            cmd.add_argument('--task', required=True)
            cmd.add_argument('--owner', required=True)
        if action == 'start':
            cmd.add_argument('--base', required=True)
            cmd.add_argument('--ticket', required=True)
            cmd.add_argument('--ticket-board', help="Board holding the ticket when it belongs to another entity, "
                             "such as an initiative board (an initiative) whose work lives in this project's repository")
        if action == 'finish':
            cmd.add_argument('--merged-into', required=True)
            cmd.add_argument('--inactive', action='store_true')
    return cli


def execute(args, client):
    root = git.factory_root(args.root)
    if args.command == 'status':
        return report(root, client)
    if getattr(args, 'ticket_board', None):
        if args.board:
            raise git.FactoryError("Use --board for the project's own board or --ticket-board for another entity's board, not both.")
        project = client.project(args.project)
        board = client.ticket_board(args.ticket_board, project)
    else:
        project, board = client.resolve(args.project, args.board)
    path = project['attributes']['repository_path']
    if args.command == 'pin':
        return pin(root, path, args.commit, args.expected_old)
    if args.action == 'start':
        try:
            UUID(args.ticket)
        except ValueError:
            raise git.FactoryError('--ticket must be a ticket UUID.') from None
        client.ticket(args.ticket, board['id'])
        if args.ticket_board:
            link = {'project_id': project['id'], 'ticket_board_id': board['id'], 'ticket_board_entity_id': board['entity_id']}
            return git.start(root, path, args.task, args.base, args.owner, args.ticket, ticket_board=link)
        return git.start(root, path, args.task, args.base, args.owner, args.ticket)
    if args.action == 'finish':
        return git.finish(root, path, args.task, args.owner, args.merged_into, args.inactive)
    return {'project_id': project['id'], 'board_id': board['id'],
            'worktrees': git.worktrees(git.project(root, path)['path'])}


def main(argv=None):
    args = parser().parse_args(argv)
    client = None
    try:
        root = git.factory_root(args.root)
        config = factory_settings.load(root)
        client = Client(args.api_url or config.api_url, factory_settings.api_token(root), tailnet=config.tailnet)
        print(json.dumps(execute(args, client), default=str, indent=2))
        return 0
    except (git.FactoryError, OSError, ValueError) as exc:
        # Suppress arbitrary OS/Pydantic/transport diagnostics, which can carry
        # credentials. FactoryError messages are deliberately sanitized.
        print(json.dumps({'error': str(exc) if isinstance(exc, git.FactoryError) else 'Factory operation failed; inspect local configuration.'}), file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == '__main__':
    raise SystemExit(main())
