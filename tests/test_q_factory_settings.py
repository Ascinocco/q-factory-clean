"""q-factory's own configuration: q-factory.toml, the token, and API origins."""
import pytest

from q_factory import settings
from q_factory.client import Client, _allowed_origin
from q_factory.git import FactoryError

GOOD = """[q_core]
api_url = "https://q-core.tail1234.ts.net"
tailnet = "tail1234.ts.net"
[self]
project_id = "00000000-0000-4000-8000-000000000001"
board_id = "00000000-0000-4000-8000-000000000002"
repository = "Ascinocco/q-factory-clean"
"""


def test_loads_origin_and_self_identity(tmp_path):
    (tmp_path / "q-factory.toml").write_text(GOOD)
    config = settings.load(tmp_path)
    assert config.api_url == "https://q-core.tail1234.ts.net"
    assert config.self_identity.repository == "ascinocco/q-factory-clean"
    assert config.self_identity.board_id == "00000000-0000-4000-8000-000000000002"
    assert config.tailnet == "tail1234.ts.net"


@pytest.mark.parametrize("text, message", [
    (None, "missing"),
    ("not = [toml", "not valid TOML"),
    (GOOD.replace('api_url = "https://q-core.tail1234.ts.net"\n', ""), "api_url is required"),
    (GOOD.replace('"00000000-0000-4000-8000-000000000001"', '"not-a-uuid"'), "project_id must be a UUID"),
    (GOOD.replace('"Ascinocco/q-factory-clean"', '"q-factory"'), "OWNER/NAME"),
    (GOOD.replace('"Ascinocco/q-factory-clean"', '"/q-factory"'), "OWNER/NAME"),
    (GOOD.replace('"Ascinocco/q-factory-clean"', '"Ascinocco/"'), "OWNER/NAME"),
    (GOOD.replace('"Ascinocco/q-factory-clean"', '"a/b/c"'), "OWNER/NAME"),
    (GOOD.replace('"tail1234.ts.net"', '"example.com"'), "tailnet must be"),
    (GOOD.replace('"tail1234.ts.net"', '"ts.net"'), "tailnet must be"),
])
def test_bad_configuration_is_refused_by_name(tmp_path, text, message):
    if text is not None:
        (tmp_path / "q-factory.toml").write_text(text)
    with pytest.raises(FactoryError, match=message):
        settings.load(tmp_path)


def test_the_repository_config_file_is_valid():
    from pathlib import Path
    config = settings.load(Path(__file__).resolve().parent.parent)
    assert _allowed_origin(config.api_url, config.tailnet)


@pytest.mark.parametrize("env, dotenv, expected", [
    ({"Q_CORE_API_TOKEN": "a"}, "Q_CORE_API_TOKEN=c\n", "a"),
    ({}, "# comment\nexport Q_CORE_API_TOKEN='c'\n", "c"),
    ({}, "Q_CORE_API_TOKEN=\"d\"\n", "d"),
])
def test_token_precedence(tmp_path, monkeypatch, env, dotenv, expected):
    for key in settings.TOKEN_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    (tmp_path / ".env").write_text(dotenv)
    assert settings.api_token(tmp_path) == expected


def test_missing_token_is_refused_without_echoing_anything(tmp_path, monkeypatch):
    for key in settings.TOKEN_KEYS:
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text("OTHER_SECRET=private-value\n")
    with pytest.raises(FactoryError) as failure:
        settings.api_token(tmp_path)
    assert "private-value" not in str(failure.value)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8420", "https://127.0.0.1:8420", "http://localhost:8420", "http://[::1]:8420",
    "https://q-core.tail1234.ts.net", "https://q-core.tail1234.ts.net:443", "https://q-core.tail1234.ts.net/",
])
def test_allowed_origins(url):
    assert _allowed_origin(url, "tail1234.ts.net")
    assert _allowed_origin(url, "TAIL1234.ts.net")


@pytest.mark.parametrize("url", [
    "http://127.0.0.1",                          # loopback needs an explicit port
    "http://q-core.tail1234.ts.net",             # tailnet must be HTTPS
    "https://q-core.tail1234.ts.net:8420",       # Serve is 443
    "https://example.com",                       # not the tailnet
    "https://q-core.tail1234.ts.net.evil.com",   # lookalike suffix
    "https://ts.net", "https://tail1234.ts.net",  # no machine label
    "https://q-core..ts.net",                    # empty label
    "https://user:pw@q-core.tail1234.ts.net",    # credentials
    "https://q-core.tail1234.ts.net/api",        # path
    "https://q-core.tail1234.ts.net?x=1",        # query
    "http://10.0.0.5:8420",                      # LAN IP
    "ftp://127.0.0.1:8420", "not a url", "",
])
def test_refused_origins(url):
    assert not _allowed_origin(url, "tail1234.ts.net")
    with pytest.raises(FactoryError, match="tailnet pinned in q-factory.toml"):
        Client(url, "token", tailnet="tail1234.ts.net")


@pytest.mark.parametrize("url", [
    "https://attacker.other-tailnet.ts.net",     # another tailnet (Funnel may make it public)
    "https://q-core.tail9999.ts.net",
    "https://a.q-core.tail1234.ts.net",          # machine label must be exactly one
])
def test_only_the_pinned_tailnet_is_accepted(url):
    assert not _allowed_origin(url, "tail1234.ts.net")


def test_without_a_pinned_tailnet_only_loopback_is_accepted():
    assert _allowed_origin("http://127.0.0.1:8420", None)
    assert not _allowed_origin("https://q-core.tail1234.ts.net", None)
    with pytest.raises(FactoryError):
        Client("https://q-core.tail1234.ts.net", "token")
