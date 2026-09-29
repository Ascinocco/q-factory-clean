"""Pin the factory skills against q-core's published surface.

These checks lived in an earlier repository as tests against the API itself.
The skills moved to q-factory in a later split; q-core now publishes the facts
in contracts/factory-contract.json and this repository keeps a copy.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTRACT = json.loads((REPO / "contracts/q-core-factory-contract.json").read_text())
WORK_BOARD_SKILL = REPO / ".claude/skills/work-the-board/SKILL.md"
STATUS_ANCHOR = "`to_status` is one of"
ATTACHMENT_TOOL = "read_attachment"


def _paragraph_after(path: Path, anchor: str) -> str:
    text = path.read_text()
    assert anchor in text, f"{path.name} no longer contains {anchor!r}; fix the anchor rather than deleting the test"
    start = text.index(anchor)
    return text[start: text.index("\n\n", start)]


def _listed_statuses() -> set[str]:
    return set(re.findall(r"`([a-z_]+)`", _paragraph_after(WORK_BOARD_SKILL, STATUS_ANCHOR))) - {"to_status"}


def test_work_the_board_lists_exactly_the_api_delivery_statuses():
    """Set equality both ways, as before the split: an omitted status is one
    the loop can never reach (omitting `blocked` turns hand-back into a stall),
    and an extra one is a 422 the model cannot reason its way out of."""
    assert _listed_statuses() == set(CONTRACT["ticket_statuses_by_type"]["task"])


def test_the_status_list_is_not_matching_by_accident():
    assert len(_listed_statuses()) >= 7
    assert {"blocked", "review", "agent_ready"} <= _listed_statuses()


def test_the_skill_reads_attachments_through_a_tool_that_exists():
    tools = CONTRACT["mcp_tools"]
    assert len(tools) > 50, "the contract lists almost no tools -- the copy is broken"
    assert ATTACHMENT_TOOL in tools, f"q-core no longer registers {ATTACHMENT_TOOL!r}; do not reword the skill to use file paths"
    assert "attachment_id" in tools[ATTACHMENT_TOOL]
    assert ATTACHMENT_TOOL in WORK_BOARD_SKILL.read_text()


def test_every_mcp_tool_the_factory_skills_call_exists():
    """New since the split: any `tool_name(` a factory skill writes that looks
    like a q-core MCP tool (matches a known tool prefix) must exist there."""
    skills = sorted((REPO / ".claude/skills").glob("*/SKILL.md"))
    assert skills
    known = set(CONTRACT["mcp_tools"])
    prefixes = {name.split("_")[0] for name in known}
    missing = {}
    for skill in skills:
        for name in set(re.findall(r"`([a-z]+_[a-z_]+)\(", skill.read_text())):
            if name.split("_")[0] in prefixes and name not in known and name != "fetch_all":
                missing.setdefault(skill.parent.name, []).append(name)
    assert not missing, f"factory skills call MCP tools q-core does not publish: {missing}"
