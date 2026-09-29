"""One process-safety rule, worded the same in the worker prompt and every skill/runbook that governs agents."""
from pathlib import Path

import pytest

from q_factory import review_runner

ROOT = Path(__file__).resolve().parents[1]
RULE = ("Never use pkill, killall or any other pattern-matched kill. Stop only processes you started, "
        "by their recorded PID or your own process group, and never touch system services or other users' processes. "
        "Hosts such as the server are shared with production and other agents.")


def normalized(text):
    return ' '.join(text.split())


@pytest.mark.parametrize('path', ['.claude/skills/work-the-board/SKILL.md', '.claude/skills/review-lead/SKILL.md',
                                  '.claude/skills/code-review/SKILL.md', '.claude/skills/strategize-teammates/SKILL.md',
                                  '.claude/skills/review-response/SKILL.md', '.claude/skills/factory-reconcile/SKILL.md',
                                  '.claude/skills/coordinate-leads/SKILL.md', '.claude/skills/project-onboarding/SKILL.md',
                                  'runbooks/team-workflow.md'])
def test_documents_state_the_rule_verbatim(path):
    assert RULE in normalized((ROOT / path).read_text())


def test_worker_prompt_rule_matches_the_documents():
    assert normalized(review_runner.PROCESS_SAFETY) == 'Process safety: n' + RULE[1:]
