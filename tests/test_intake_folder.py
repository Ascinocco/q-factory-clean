"""The tracked intake/ drop folder: the folder ships, its contents never do."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def ignored(path):
    result = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index", path])
    assert result.returncode in (0, 1), result
    return result.returncode == 0


def test_intake_keep_file_is_tracked():
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "intake"],
                             check=True, capture_output=True, text=True).stdout.split()
    assert tracked == ["intake/.gitkeep"]
    assert not ignored("intake/.gitkeep")


def test_intake_contents_are_ignored():
    for path in ("intake/statement.pdf", "intake/sept_24_2026/activity.csv",
                 "intake/sept_24_2026/nested/export.xlsx", "intake/.hidden"):
        assert ignored(path), path
