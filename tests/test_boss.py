import json
import tempfile
import unittest
from pathlib import Path

from hsr_version_inspector.boss import available_boss_nodes, load_boss
from helpers import write_scaling_config


class BossTests(unittest.TestCase):
    def test_unsuffixed_boss_data_is_node_three_when_numbered_nodes_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            boss_path = root / "4.4.54/zh/boss/3020.json"
            monster_path = root / "4.4.54/zh/monster/1234.json"
            boss_path.parent.mkdir(parents=True)
            monster_path.parent.mkdir(parents=True)
            boss_path.write_text(
                json.dumps(
                    {
                        "buff_list3": [{"name": "Node 3 buff", "desc": "Damage", "param": []}],
                        "level": [
                            {"id": 1, "boss_monster_id1": 111},
                            {"id": 2, "boss_monster_id2": 222},
                            {
                                "id": 3,
                                "boss_monster_id": 1234,
                                "event_id_list": [{"level": 90}],
                                "boss_monster_config": {"phase_list": [{}]},
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            monster_path.write_text(
                json.dumps({"name": "Node 3 boss", "hp_base": 100, "child": [{"id": 1234}]}),
                encoding="utf-8",
            )

            self.assertEqual(available_boss_nodes("4.4.54", "3020", root), (1, 2, 3))
            view = load_boss("4.4.54", "3020", 3, root)

        self.assertEqual(view.name, "Node 3 boss")
        self.assertEqual(view.level, 90)
        self.assertEqual(view.phases, 1)
        self.assertEqual(view.buffs[0].name, "Node 3 buff")

    def test_load_boss_uses_highest_difficulty_and_node_buffs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            boss_path = root / "4.4.51/zh/boss/3020.json"
            monster_path = root / "4.4.51/zh/monster/2024016.json"
            elite_monster_path = root / "4.4.51/zh/monster/2033022.json"
            boss_path.parent.mkdir(parents=True)
            monster_path.parent.mkdir(parents=True)
            boss_path.write_text(
                json.dumps(
                    {
                        "buff_list1": [
                            {
                                "name": "Test buff",
                                "desc": "Damage up #1[i]% and stacks #2[i] times.",
                                "param": [0.3, 4],
                            }
                        ],
                        "level": [
                            {
                                "id": 30201,
                                "boss_monster_id1": 202401601,
                                "event_id_list1": [{"level": 60, "elite_group": 90}],
                            },
                            {
                                "id": 30204,
                                "boss_monster_id1": 202401604,
                                "boss_monster_id2": 203302204,
                                "event_id_list1": [{"level": 90, "elite_group": 90}],
                                "event_id_list2": [{"level": 90, "elite_group": 89}],
                                "boss_monster_config1": {
                                    "phase_list": [
                                        {"name": "Phase 1"},
                                        {"name": "Phase 2"},
                                    ]
                                },
                                "boss_monster_config2": {
                                    "phase_list": [
                                        {"name": "Phase 1"},
                                        {"name": "Phase 2"},
                                    ]
                                },
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            monster_path.write_text(
                json.dumps(
                    {
                        "name": "Test boss",
                        "rank": "LittleBoss",
                        "hp_base": 24412.5,
                        "child": [{"id": 202401604, "hp_modify_ratio": 1}],
                    }
                ),
                encoding="utf-8",
            )
            elite_monster_path.write_text(
                json.dumps(
                    {
                        "name": "Test elite",
                        "rank": "Elite",
                        "hp_base": 35805,
                        "child": [{"id": 203302204, "hp_modify_ratio": 1}],
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(available_boss_nodes("4.4.51", "3020", root), (1, 2))
            view = load_boss("4.4.51", "3020", 1, root)
            elite_view = load_boss("4.4.51", "3020", 2, root)

        self.assertEqual(view.level, 90)
        self.assertEqual(view.hp, 11548808)
        self.assertEqual(view.phases, 2)
        self.assertEqual(view.name, "Test boss")
        self.assertEqual(view.buffs[0].description, "Damage up 30% and stacks 4 times.")
        self.assertEqual(elite_view.hp, 16091338)
        self.assertEqual(elite_view.phases, 2)


if __name__ == "__main__":
    unittest.main()
