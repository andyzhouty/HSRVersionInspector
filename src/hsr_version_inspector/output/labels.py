"""User-facing labels shared by all output formats."""

MODE_LABELS = {
    "character": "角色",
    "lightcone": "光锥",
    "maze": "混沌",
    "story": "虚构",
    "boss": "末日",
    "peak": "异相",
    "knight": "骑士",
    "king": "王棋",
    "hard-king": "绝境",
}

STATUS_LABELS = {
    "added": "新增",
    "removed": "删除",
    "changed": "已变更",
    "unchanged": "未变更",
    "missing": "缺失",
}

ELEMENT_LABELS = {
    "Physical": "物理",
    "Fire": "火",
    "Ice": "冰",
    "Lightning": "雷",
    "Thunder": "雷",
    "Wind": "风",
    "Quantum": "量子",
    "Imaginary": "虚数",
}

def mode_label(mode: str) -> str:
    """Return the Chinese label for a mode or a numbered node mode."""
    if mode.startswith("story "):
        return f"虚构节点 {mode.removeprefix('story ')}"
    return MODE_LABELS.get(mode, mode)


def element_label(element: str) -> str:
    return ELEMENT_LABELS.get(element, element)
