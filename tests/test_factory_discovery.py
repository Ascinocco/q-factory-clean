"""Independent project tests must not join q-factory's testpath census."""
import importlib.util
from pathlib import Path


def test_census_prunes_projects_but_keeps_nested_app_tests(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "conftest.py"
    spec = importlib.util.spec_from_file_location("factory_discovery_config", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for relative in ("tests/test_own.py", "api/tests/projects/test_owned.py",
                     "projects/example/tests/test_other.py",
                     ".worktrees/example/task/tests/test_worker.py"):
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("raise RuntimeError('must not import during census')\n")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    assert module._directories_holding_tests() == ["api/tests/projects", "tests"]
