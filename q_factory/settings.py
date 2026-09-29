"""q-factory configuration, without importing q-core.

Before the split the factory read `api.config.Settings` from the earlier
checkout it lived in. q-factory is cloned on every machine and talks to
q-core only over HTTP, so it carries its own small settings:

- `q-factory.toml` at the factory root (committed, no secrets): the q-core
  API origin and this repository's own Jyra identity (for `--self`).
- The API token, never committed: `Q_CORE_API_TOKEN`, else the same key in
  the root `.env`.
"""
from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from .git import FactoryError

CONFIG_NAME = 'q-factory.toml'
REPOSITORY = re.compile(r'[A-Za-z0-9-]+/[A-Za-z0-9._-]+')
TAILNET = re.compile(r'(?:[a-z0-9-]+\.)+ts\.net')
TOKEN_KEYS = ('Q_CORE_API_TOKEN',)


@dataclass(frozen=True)
class SelfIdentity:
    project_id: str
    board_id: str
    repository: str


@dataclass(frozen=True)
class Settings:
    api_url: str
    self_identity: SelfIdentity
    #: The tailnet DNS suffix (e.g. `tail1234.ts.net`) that API origins may use
    #: besides loopback. None: loopback only.
    tailnet: str | None = None


def _uuid(value, name: str) -> str:
    try:
        return str(UUID(str(value)))
    except ValueError:
        raise FactoryError(f'{CONFIG_NAME}: {name} must be a UUID.') from None


def load(root: Path) -> Settings:
    path = Path(root) / CONFIG_NAME
    try:
        data = tomllib.loads(path.read_text())
    except FileNotFoundError:
        raise FactoryError(f'{CONFIG_NAME} is missing from the factory root.') from None
    except tomllib.TOMLDecodeError:
        raise FactoryError(f'{CONFIG_NAME} is not valid TOML.') from None
    core, own = data.get('q_core', {}), data.get('self', {})
    api_url = core.get('api_url')
    repository = own.get('repository')
    if not isinstance(api_url, str) or not api_url:
        raise FactoryError(f'{CONFIG_NAME}: [q_core] api_url is required.')
    if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
        raise FactoryError(f'{CONFIG_NAME}: [self] repository must be OWNER/NAME.')
    tailnet = core.get('tailnet')
    if tailnet is not None and (not isinstance(tailnet, str) or not TAILNET.fullmatch(tailnet.lower())):
        raise FactoryError(f'{CONFIG_NAME}: [q_core] tailnet must be a tailnet DNS name such as tail1234.ts.net.')
    return Settings(api_url, SelfIdentity(_uuid(own.get('project_id'), '[self] project_id'),
                                          _uuid(own.get('board_id'), '[self] board_id'),
                                          repository.lower()),
                    tailnet.lower() if tailnet else None)


def _dotenv(path: Path) -> dict[str, str]:
    """KEY=VALUE lines only; enough for the token, no interpolation."""
    values = {}
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip().removeprefix('export ').strip()] = value.strip().strip('"').strip("'")
    return values


def api_token(root: Path) -> str:
    for key in TOKEN_KEYS:
        if os.environ.get(key):
            return os.environ[key]
    file_values = _dotenv(Path(root) / '.env')
    for key in TOKEN_KEYS:
        if file_values.get(key):
            return file_values[key]
    raise FactoryError('Set Q_CORE_API_TOKEN in the environment or the factory root .env.')
