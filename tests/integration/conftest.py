"""Opt-in integration against a real q-core checkout.

These tests drive the factory client through q-core's actual API routes,
serializers and validation, so they need q-core's code. Point Q_CORE_ROOT at a
q-core checkout whose virtualenv packages are importable (run pytest with that
checkout's interpreter, or install its requirements here), e.g.:

    Q_CORE_ROOT=../q-core ../q-core/.venv/bin/python -m pytest tests/integration

Without it they are SKIPPED, and reported as skipped, never as passed: q-factory's
own suite must pass on a machine where q-core is not installed.
"""
import os
import sys
from pathlib import Path

import pytest

_ROOT = os.environ.get("Q_CORE_ROOT")

if _ROOT:
    core = Path(_ROOT).resolve()
    if not (core / "api" / "main.py").is_file():
        raise pytest.UsageError(f"Q_CORE_ROOT={_ROOT!r} is not a q-core checkout (no api/main.py).")
    sys.path.insert(0, str(core))
    # q-core's API fixtures, registered here by import. Its session guard that
    # publishes the pytest temp root (so api.db refuses real paths) comes too.
    from api.tests.conftest import client, test_settings, _never_the_real_settings  # noqa: E402,F401

    # q-core's api.db guard reads Q_CORE_TEST_TMP_ROOT. Missing it degrades to
    # tempfile.gettempdir(): a logged warning by default, errors under --basetemp.
    _TEMP_ROOT_VARIABLES = ("Q_CORE_TEST_TMP_ROOT",)

    @pytest.fixture(autouse=True, scope="session")
    def _publish_pytest_temp_root(tmp_path_factory):
        for name in _TEMP_ROOT_VARIABLES:
            os.environ[name] = str(tmp_path_factory.getbasetemp())
        yield
        for name in _TEMP_ROOT_VARIABLES:
            os.environ.pop(name, None)
else:
    def pytest_collection_modifyitems(config, items):
        skip = pytest.mark.skip(reason="set Q_CORE_ROOT to a q-core checkout to run integration tests")
        for item in items:
            if "tests/integration" in str(item.fspath):
                item.add_marker(skip)

    @pytest.fixture()
    def client():
        pytest.skip("Q_CORE_ROOT not set")

    @pytest.fixture()
    def test_settings():
        pytest.skip("Q_CORE_ROOT not set")
