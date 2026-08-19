"""User-facing labels shared by all output formats."""

from ..mappings import ELEMENT_LABELS, MODE_LABELS, STATUS_LABELS

__all__ = [
    "ELEMENT_LABELS",
    "MODE_LABELS",
    "STATUS_LABELS",
    "element_label",
    "mode_label",
]

def mode_label(mode: str) -> str:
    """Return the Chinese label for a mode or a numbered node mode."""
    if mode.startswith("story "):
        return f"虚构节点 {mode.removeprefix('story ')}"
    return MODE_LABELS.get(mode, mode)


def element_label(element: str) -> str:
    return ELEMENT_LABELS.get(element, element)
