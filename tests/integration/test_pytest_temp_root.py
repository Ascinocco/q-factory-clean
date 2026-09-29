"""q-core's test-path guard must see this run's real pytest temp root.

If the conftest publishes a variable the pinned q-core no longer reads, the
guard falls back to tempfile.gettempdir(): the suite still passes by default,
with a warning per database, and errors under --basetemp outside /tmp.
"""
import logging


def test_q_core_guard_reads_the_published_temp_root(tmp_path_factory, caplog):
    from api import db

    with caplog.at_level(logging.WARNING, logger="api"):
        root = db._test_writable_root()

    assert root == tmp_path_factory.getbasetemp().resolve()
    assert not [r for r in caplog.records if "is not set" in r.getMessage()]
