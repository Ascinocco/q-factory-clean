"""Read-only public API client for on-demand factory coordination."""
from __future__ import annotations

import ipaddress
from urllib.parse import quote, urlsplit

import httpx

from .git import FactoryError


def _allowed_origin(url: str, tailnet: str | None = None) -> bool:
    """Loopback with an explicit port (local q-core), or HTTPS on OUR tailnet.

    q-core is published only through Tailscale Serve, so the one non-loopback
    shape allowed is `https://<machine>.<tailnet>` where <tailnet> is the one
    pinned in q-factory.toml. Any `*.ts.net` is not enough: another tailnet's
    machine, possibly public through Funnel, is also `*.ts.net`, and a typo
    must not send the token there. No pinned tailnet means loopback only.
    Plain HTTP stays loopback-only, and credentials, paths, queries and
    fragments are refused either way.
    """
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower()
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {'', '/'}:
            return False
        if host == 'localhost' or (host and _is_loopback_ip(host)):
            return parsed.scheme in {'http', 'https'} and parsed.port is not None
        if not tailnet:
            return False
        machine, _, rest = host.partition('.')
        return (parsed.scheme == 'https' and rest == tailnet.lower() and bool(machine)
                and parsed.port in {None, 443})
    except (ValueError, TypeError):
        return False


def _is_loopback_ip(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class Client:
    def __init__(self, url: str, token: str, *, tailnet: str | None = None, transport=None):
        if not _allowed_origin(url, tailnet):
            raise FactoryError('API URL must be a loopback HTTP(S) origin with an explicit port, '
                               'or https://<machine>.<tailnet> for the tailnet pinned in q-factory.toml.')
        if not token:
            raise FactoryError('Set Q_CORE_API_TOKEN or configure the factory root .env.')
        self.http = httpx.Client(base_url=url.rstrip('/'), headers={'Authorization': 'Bearer ' + token},
                                 timeout=15, follow_redirects=False, trust_env=False, transport=transport)

    def close(self):
        self.http.close()

    def get(self, path: str, **params):
        try:
            response = self.http.get(path, params=params)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            raise FactoryError(f'q-core API read failed (HTTP {exc.response.status_code}).') from None
        except (httpx.HTTPError, ValueError):
            raise FactoryError('q-core API is unavailable or returned invalid JSON.') from None
        if not isinstance(body, dict):
            raise FactoryError('q-core API returned an invalid object.')
        return body

    def all(self, path: str, **params) -> list[dict]:
        items, seen, offset = [], set(), 0
        while True:
            page = self.get(path, limit=200, offset=offset, **params)
            batch, total = page.get('items'), page.get('total')
            if not isinstance(batch, list) or type(total) is not int or total < 0:
                raise FactoryError('q-core API returned an invalid page.')
            if not batch:
                if len(items) < total:
                    raise FactoryError('q-core API pagination ended before the reported total; retry the read.')
                return items
            for item in batch:
                if not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] in seen:
                    raise FactoryError('q-core API pagination repeated or omitted an item identity; retry the read.')
                seen.add(item['id'])
            items.extend(batch)
            if len(items) >= total:
                return items
            offset += len(batch)

    def projects(self):
        return self.all('/entities', type='project')

    def resolve(self, selector: str, board_id: str | None = None):
        project = self.project(selector)
        boards = self.all('/boards', entity_id=project['id'])
        choices = [b for b in boards if b['id'] == board_id] if board_id else boards
        if len(choices) != 1:
            raise FactoryError('Select an explicit associated board ID; the project must have one chosen board.')
        if choices[0].get('entity_id') != project['id']:
            raise FactoryError('Board association does not match the selected project.')
        return project, choices[0]

    def project(self, selector: str):
        projects = self.projects()
        matches = [p for p in projects if p['id'] == selector]
        if not matches:
            matches = [p for p in projects if p.get('name') == selector]
        if len(matches) != 1:
            raise FactoryError('Project must resolve to one exact ID or unique exact name.')
        project = matches[0]
        path = project.get('attributes', {}).get('repository_path')
        if not path:
            raise FactoryError('The selected project has no managed repository_path.')
        if sum(p.get('attributes', {}).get('repository_path') == path for p in projects) != 1:
            raise FactoryError('Multiple projects assign this repository_path; repair the registry first.')
        return project

    def ticket_board(self, board_id: str, project: dict):
        """A board attached to another entity (an initiative) whose tickets use this project's repo."""
        board = self.get('/boards/' + quote(board_id, safe=''))
        # The detail endpoint embeds the entity; only the board listing has a flat entity_id.
        entity = board.get('entity')
        if board.get('id') != board_id or not isinstance(entity, dict) or not isinstance(entity.get('id'), str) or not entity['id']:
            raise FactoryError('Ticket board could not be read as the requested board.')
        if entity['id'] == project['id']:
            raise FactoryError("The ticket board is the project's own board; select it with --board instead.")
        # An initiative board's entity has no repository; another managed project's board belongs to that repo.
        if any(p['id'] == entity['id'] and p.get('attributes', {}).get('repository_path') for p in self.projects()):
            raise FactoryError("The ticket board belongs to another managed project with its own repository; "
                               "work its tickets in that project's checkout.")
        return {'id': board_id, 'entity_id': entity['id']}

    def ticket(self, ticket_id: str, board_id: str):
        ticket = self.get('/tickets/' + quote(ticket_id, safe=''))
        if ticket.get('id') != ticket_id or ticket.get('board_id') != board_id:
            raise FactoryError('Ticket does not belong to the selected board.')
        return ticket
