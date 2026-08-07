import json
import tempfile
import unittest
from pathlib import Path

from hsr_version_inspector.lightcone import load_lightcone


class LightConeTests(unittest.TestCase):
    def test_maps_all_light_cone_paths(self) -> None:
        expected = {
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

        for base_type, path_name in expected.items():
            with self.subTest(base_type=base_type):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    path = root / "4.4.54/zh/lightcone/23063.json"
                    path.parent.mkdir(parents=True)
                    path.write_text(
                        json.dumps(
                            {
                                "name": "Test light cone",
                                "rarity": "CombatPowerLightconeRarity5",
                                "base_type": base_type,
                                "refinements": {
                                    "name": "Test effect",
                                    "desc": "效果",
                                    "level": {"1": {"param_list": []}},
                                },
                                "stats": [
                                    {
                                        "max_level": 80,
                                        "base_hp": 1,
                                        "base_hp_add": 0,
                                        "base_attack": 2,
                                        "base_attack_add": 0,
                                        "base_defence": 3,
                                        "base_defence_add": 0,
                                    }
                                ],
                            }
                        ),
                        encoding="utf-8",
                    )

                    view = load_lightcone("4.4.54", "23063", root)

                self.assertEqual(view.path, path_name)

    def test_loads_level_80_and_all_refinements_without_repeating_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "4.4.54/zh/lightcone/23063.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "name": "Test light cone",
                        "rarity": "CombatPowerLightconeRarity5",
                        "base_type": "Memory",
                        "refinements": {
                            "name": "Test effect",
                            "desc": "提高#1[i]%，持续#2[i]回合。",
                            "level": {
                                str(index): {"param_list": [value, 2]}
                                for index, value in enumerate(
                                    (0.2, 0.25, 0.3, 0.35, 0.4),
                                    1,
                                )
                            },
                        },
                        "stats": [
                            {
                                "max_level": 70,
                                "base_hp": 1,
                                "base_hp_add": 1,
                                "base_attack": 2,
                                "base_attack_add": 2,
                                "base_defence": 3,
                                "base_defence_add": 3,
                            },
                            {
                                "max_level": 80,
                                "base_hp": 100,
                                "base_hp_add": 1.5,
                                "base_attack": 200,
                                "base_attack_add": 2.5,
                                "base_defence": 300,
                                "base_defence_add": 3.5,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            view = load_lightcone("4.4.54", "23063", root)

        self.assertEqual(view.level, 80)
        self.assertEqual(view.rarity, 5)
        self.assertEqual(view.path, "记忆")
        self.assertEqual((view.hp, view.attack, view.defence), ("218.50", "397.50", "576.50"))
        self.assertEqual(view.refinement, "1/2/3/4/5")
        self.assertEqual(
            view.description,
            "提高20%/25%/30%/35%/40%，持续2回合。",
        )
        self.assertEqual(view.description.count("提高"), 1)


if __name__ == "__main__":
    unittest.main()
