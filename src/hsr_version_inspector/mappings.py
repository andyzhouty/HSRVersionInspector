"""Static mappings shared by the data and rendering layers."""

BASE_STAT_ORDER = {
    "命途": -1,
    "生命值": 0,
    "攻击力": 1,
    "防御力": 2,
    "速度": 3,
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

PATH_NAMES = {
    "Memory": "记忆",
    "Elation": "欢愉",
    "Rogue": "巡猎",
    "Mage": "智识",
    "Warrior": "毁灭",
    "Knight": "存护",
    "Warlock": "虚无",
    "Priest": "丰饶",
    "Shaman": "同谐",
}

SECTION_LABELS = {
    "Knight 1": "骑士 1",
    "Knight 2": "骑士 2",
    "Knight 3": "骑士 3",
    "King": "王棋",
    "Hard-king": "绝境",
}

STATUS_LABELS = {
    "added": "新增",
    "removed": "删除",
    "changed": "已变更",
    "unchanged": "未变更",
    "missing": "缺失",
}
