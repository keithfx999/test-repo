"""
state.py — 已审查 PR 状态持久化

用一个简单的 JSON 文件记录已经审查过的 PR（number + head_sha）。
当 PR 有新 commit push 时，head_sha 会变化，从而触发重新审查。
"""

import json
import os
from pathlib import Path

STATE_FILE = Path(__file__).parent / ".reviewed_prs.json"


def load_reviewed() -> dict[str, str]:
    """
    返回 {pr_number_str: head_sha} 的字典。
    已审查过当前 head_sha 的 PR 不会重复审查。
    """
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def mark_reviewed(pr_number: int, head_sha: str) -> None:
    """标记某个 PR 的当前 commit 已审查。"""
    state = load_reviewed()
    state[str(pr_number)] = head_sha
    STATE_FILE.write_text(json.dumps(state, indent=2))


def is_reviewed(pr_number: int, head_sha: str) -> bool:
    """检查该 PR 的当前 head_sha 是否已经审查过。"""
    state = load_reviewed()
    return state.get(str(pr_number)) == head_sha
