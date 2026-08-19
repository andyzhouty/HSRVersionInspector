import json
import tempfile
import unittest
from pathlib import Path

from helpers import write_scaling_config

from hsr_version_inspector.highmode import (
    available_maze_nodes,
    available_story_nodes,
    load_maze,
    load_peak,
    load_story,
)


class HighModeTests(unittest.TestCase):
    def test_maze_uses_highest_layer_and_three_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            maze_path = root / "4.4.54/zh/maze/1034.json"
            monster_dir = root / "4.4.54/zh/monster"
            maze_path.parent.mkdir(parents=True)
            monster_dir.mkdir(parents=True)

            def event(monster_id: int) -> dict[str, object]:
                return {
                    "hard_level_group": 3,
                    "level": 95,
                    "elite_group": 367,
                    "monster_list": [{"monster0": monster_id}],
                }

            maze_path.write_text(
                json.dumps(
                    [
                        {
                            "id": 5301,
                            "name": "较低层",
                            "event_id_list1": [event(1000001)],
                            "event_id_list2": [event(1000001)],
                        },
                        {
                            "id": 5312,
                            "name": "最高层",
                            "group_name": "本期效果",
                            "desc": "提高#1[i]%伤害。",
                            "param": [0.8],
                            "damage_type1": ["Ice"],
                            "damage_type2": ["Quantum"],
                            "event_id_list1": [event(1000002)],
                            "event_id_list2": [event(1000003)],
                        },
                        {
                            "id": 5313,
                            "pre_id": 5312,
                            "damage_type": ["Fire"],
                            "event_id_list": [event(1000004)],
                        },
                    ]
                ),
                encoding="utf-8",
            )
            for monster_id, name in (
                (1000001, "低层敌人"),
                (1000002, "节点一敌人"),
                (1000003, "节点二敌人"),
                (1000004, "节点三敌人"),
            ):
                (monster_dir / f"{monster_id}.json").write_text(
                    json.dumps({"name": name, "hp_base": 100, "child": [{"id": monster_id}]}),
                    encoding="utf-8",
                )

            nodes = available_maze_nodes("4.4.54", "1034", root)
            views = tuple(load_maze("4.4.54", "1034", node, root) for node in nodes)

        self.assertEqual(nodes, (1, 2, 3))
        self.assertEqual(
            [view.parts[0].title for view in views],
            ["节点一敌人", "节点二敌人", "节点三敌人"],
        )
        self.assertEqual(
            [view.parts[0].waves[0].enemies[0].name for view in views],
            ["节点一敌人", "节点二敌人", "节点三敌人"],
        )
        self.assertEqual(views[0].parts[0].waves[0].enemies[0].hp, 37544)
        self.assertEqual(views[0].parts[0].buffs[0].description, "提高80%伤害。")

    def test_unsuffixed_story_data_is_node_three_when_numbered_nodes_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            story_path = root / "4.4.54/zh/story/2026.json"
            monster_path = root / "4.4.54/zh/monster/1000000.json"
            story_path.parent.mkdir(parents=True)
            monster_path.parent.mkdir(parents=True)
            event = {
                "hard_level_group": 1,
                "level": 85,
                "monster_list": [{"monster0": 1000000}],
            }
            story_path.write_text(
                json.dumps(
                    {
                        "level": [
                            {
                                "event_id_list1": [event],
                                "infinite_list1": {"wave1": {"monster_group_id_list": [1000000]}},
                            },
                            {
                                "event_id_list": [event],
                                "infinite_list": {"wave1": {"monster_group_id_list": [1000000]}},
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            monster_path.write_text(
                json.dumps({"name": "Node 3 enemy", "hp_base": 100, "child": [{"id": 1000000}]}),
                encoding="utf-8",
            )

            self.assertEqual(available_story_nodes("4.4.54", "2026", root), (1, 3))
            view = load_story("4.4.54", "2026", 3, root)

        self.assertEqual(view.title, "Node 3 enemy")
        self.assertEqual(view.waves[0].enemies[0].name, "Node 3 enemy")

    def test_knight_one_matches_peak_hp_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            peak_path = root / "4.4.54/zh/peak/9.json"
            monster_dir = root / "4.4.54/zh/monster"
            peak_path.parent.mkdir(parents=True)
            monster_dir.mkdir(parents=True)
            peak_path.write_text(
                json.dumps(
                    {
                        "pre_level": [
                            {
                                "id": 901,
                                "name": "骑士（一）",
                                "damage_type": ["Fire", "Quantum"],
                                "tag_list": [],
                                "event_id_list": [
                                    {
                                        "hard_level_group": 3,
                                        "level": 95,
                                        "monster_list": [
                                            {"monster0": 8033020, "monster1": 800304016},
                                            {"monster0": 8033020, "monster1": 100401014},
                                        ],
                                    }
                                ],
                                "infinite_list": {
                                    "wave1": {
                                        "monster_group_id_list": [8033020, 800304016],
                                        "elite_group": 367,
                                    },
                                    "wave2": {
                                        "monster_group_id_list": [8033020, 100401014],
                                        "elite_group": 370,
                                    },
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            for resource_id, payload in {
                "8033020": {
                    "name": "「灯塔」",
                    "hp_base": 1302,
                    "child": [{"id": 8033020, "hp_modify_ratio": 1}],
                },
                "8003040": {
                    "name": "蚕食者之影",
                    "hp_base": 930,
                    "child": [{"id": 800304016, "hp_modify_ratio": 1.5}],
                },
                "1004010": {
                    "name": "可可利亚",
                    "hp_base": 1627.5,
                    "child": [{"id": 100401014, "hp_modify_ratio": 1.942857}],
                },
            }.items():
                (monster_dir / f"{resource_id}.json").write_text(
                    json.dumps(payload), encoding="utf-8"
                )

            view = load_peak("4.4.54", "9", "knight", 1, root)

        self.assertEqual(view.title, "骑士（一）")
        self.assertEqual(view.level, 95)
        self.assertEqual(
            [[enemy.hp for enemy in wave.enemies] for wave in view.waves],
            [[3519511, 3770904], [4203860, 10209373]],
        )

    def test_knight_three_uses_its_wave_hp_multipliers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            peak_path = root / "4.4.54/zh/peak/9.json"
            monster_dir = root / "4.4.54/zh/monster"
            peak_path.parent.mkdir(parents=True)
            monster_dir.mkdir(parents=True)
            peak_path.write_text(
                json.dumps(
                    {
                        "pre_level": [
                            {},
                            {},
                            {
                                "name": "骑士（三）",
                                "damage_type": ["Ice", "Quantum"],
                                "event_id_list": [
                                    {
                                        "hard_level_group": 3,
                                        "level": 95,
                                        "monster_list": [
                                            {"monster0": 4013010, "monster1": 8003020},
                                            {"monster0": 4034010},
                                        ],
                                    }
                                ],
                                "infinite_list": {
                                    "wave1": {
                                        "monster_group_id_list": [4013010, 8003020, 4013010, 8003020],
                                        "elite_group": 369,
                                    },
                                    "wave2": {
                                        "monster_group_id_list": [4034010],
                                        "elite_group": 361,
                                    },
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            for resource_id, payload in {
                "4013010": {"name": "天谴先锋", "hp_base": 1674, "child": [{"id": 4013010}]},
                "8003020": {"name": "外宇宙之炎", "hp_base": 930, "child": [{"id": 8003020}]},
                "4034010": {
                    "name": "至黑之剑，盗火行者",
                    "hp_base": 3022.5,
                    "child": [{"id": 4034010}],
                    "phase_list": [
                        {"phase_max_hp_ratio": 1.0},
                        {"phase_max_hp_ratio": 1.0},
                    ],
                },
            }.items():
                (monster_dir / f"{resource_id}.json").write_text(
                    json.dumps(payload), encoding="utf-8"
                )

            view = load_peak("4.4.54", "9", "knight", 3, root)

        self.assertEqual(
            [(enemy.name, enemy.count, enemy.hp) for enemy in view.waves[0].enemies],
            [("天谴先锋", 2, 3896601), ("外宇宙之炎", 2, 2164778)],
        )
        self.assertEqual(view.waves[1].enemies[0].phase_hps, (6808577, 6808577))

    def test_king_includes_all_buffs_and_phases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            peak_path = root / "4.4.54/zh/peak/9.json"
            monster_dir = root / "4.4.54/zh/monster"
            peak_path.parent.mkdir(parents=True)
            monster_dir.mkdir(parents=True)
            stage = {
                "hard_level_group": 3,
                "level": 100,
                "monster_list": [{"monster0": 403501001}],
            }
            peak_path.write_text(
                json.dumps(
                    {
                        "boss_level": {
                            "name": "将杀王棋",
                            "damage_type": ["Ice"],
                            "tag_list": [{"name": "Stage buff", "desc": "stage", "param": []}],
                            "event_id_list": [stage],
                            "infinite_list": {
                                "wave1": {
                                    "monster_group_id_list": [403501001],
                                    "elite_group": 1,
                                }
                            },
                        },
                        "boss_config": {
                            "buff_list": [
                                {"name": "Season buff 1", "desc": "season 1", "param": []},
                                {"name": "Season buff 2", "desc": "season 2", "param": []},
                            ],
                            "tag_list": [{"name": "Hard stage buff", "desc": "hard", "param": []}],
                            "event_id_list": [stage],
                        },
                    }
                ),
                encoding="utf-8",
            )
            (monster_dir / "4035010.json").write_text(
                json.dumps(
                    {
                        "name": "Test king",
                        "hp_base": 6975,
                        "child": [{"id": 403501001, "hp_modify_ratio": 3.666667}],
                        "phase_list": [
                            {"phase_max_hp_ratio": 1.0},
                            {"phase_max_hp_ratio": 1.25},
                            {"phase_max_hp_ratio": 1.0},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            view = load_peak("4.4.54", "9", "king", data_root=root)

        self.assertEqual(view.phases, 3)
        self.assertEqual([buff.name for buff in view.season_buffs], ["Season buff 1", "Season buff 2"])
        self.assertEqual([buff.name for buff in view.buffs], ["Stage buff"])
        self.assertEqual(view.waves[0].enemies[0].phase_hps, (12395970, 15494963, 12395970))

    def test_story_two_uses_infinite_wave_groups(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            story_path = root / "4.4.54/zh/story/2026.json"
            monster_dir = root / "4.4.54/zh/monster"
            story_path.parent.mkdir(parents=True)
            monster_dir.mkdir(parents=True)
            groups = {
                "wave1": {
                    "monster_group_id_list": [
                        8003060,
                        *([5012100] * 12),
                        *([4062020] * 11),
                        *([501211002] * 2),
                    ],
                    "param_list": [0, 4],
                    "elite_group": 57,
                },
                "wave2": {
                    "monster_group_id_list": [
                        *([2012010] * 20),
                        *([1002030] * 20),
                        201302012,
                    ],
                    "param_list": [0.05, 9],
                    "elite_group": 57,
                },
                "wave3": {
                    "monster_group_id_list": [
                        *([5022010] * 20),
                        *([5012100] * 20),
                        5024014,
                    ],
                    "param_list": [0.12, 43],
                    "elite_group": 57,
                },
            }
            story_path.write_text(
                json.dumps(
                    {
                        "level": [
                            {
                                "id": 20265,
                                "name": "立界开篇其四",
                                "event_id_list2": [
                                    {
                                        "hard_level_group": 1,
                                        "level": 85,
                                        "monster_list": [
                                            {"monster0": 5012100},
                                            {"monster0": 2012010},
                                            {"monster0": 5022010},
                                        ],
                                    }
                                ],
                                "infinite_list2": groups,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            for resource_id, payload in {
                "5012100": {"name": "魔法少女急袭剧团", "hp_base": 279, "child": [{"id": 5012100}]},
                "4062020": {"name": "金血忆灵•犬形", "hp_base": 279, "child": [{"id": 4062020}]},
                "5012110": {
                    "name": "狸猫记者",
                    "hp_base": 372,
                    "child": [{"id": 501211002, "hp_modify_ratio": 1.5}],
                },
                "2012010": {"name": "入魔机巧 • 灯昼龙鱼", "hp_base": 139.5, "child": [{"id": 2012010}]},
                "1002030": {"name": "银鬃炮手", "hp_base": 195.3, "child": [{"id": 1002030}]},
                "2013020": {
                    "name": "金人勾魂使",
                    "hp_base": 1116,
                    "child": [{"id": 201302012, "hp_modify_ratio": 6.875}],
                },
                "5022010": {"name": "邪愿莲华", "hp_base": 334.8, "child": [{"id": 5022010}]},
                "5024014": {
                    "name": "极乐颠倒•邪愿莲华主",
                    "hp_base": 7672.5,
                    "child": [{"id": 5024014}],
                },
            }.items():
                (monster_dir / f"{resource_id}.json").write_text(
                    json.dumps(payload), encoding="utf-8"
                )

            self.assertEqual(available_story_nodes("4.4.54", "2026", root), (2,))
            view = load_story("4.4.54", "2026", 2, root)

        self.assertEqual(
            [[(enemy.name, enemy.count, enemy.hp) for enemy in wave.enemies] for wave in view.waves],
            [
                [
                    ("魔法少女急袭剧团", 12, 262628),
                    ("金血忆灵•犬形", 11, 262628),
                    ("狸猫记者", 2, 525255),
                ],
                [
                    ("入魔机巧 • 灯昼龙鱼", 20, 262628),
                    ("银鬃炮手", 20, 367679),
                    ("金人勾魂使", 1, 14444525),
                ],
                [
                    ("邪愿莲华", 20, 2773349),
                    ("魔法少女急袭剧团", 20, 2311124),
                    ("极乐颠倒•邪愿莲华主", 1, 63555909),
                ],
            ],
        )


if __name__ == "__main__":
    unittest.main()
