import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from hsr_version_inspector.boss import BossBuff, BossView
from hsr_version_inspector.data import VersionRecord
from hsr_version_inspector.diff import (
    CharacterChange,
    compare_all_boss_versions,
    compare_all_maze_versions,
    compare_boss_versions,
    compare_character_versions,
    compare_highmode_versions,
    compare_all_story_versions,
    compare_lightcone_versions,
    compare_versions,
    character_change_subject,
    tokenize_refinement_diff,
    tokenize_text_diff,
    validate_request,
)
from helpers import write_scaling_config


def _record(name: str = "4.4") -> VersionRecord:
    return VersionRecord(
        name=name,
        versions=("4.4.51", "4.4.54"),
        character=("1512",),
        lightcone=(),
        maze="0",
        story="2026",
        boss="3020",
        peak="9",
    )


class DiffTests(unittest.TestCase):
    def test_character_skill_diff_uses_type_without_level(self) -> None:
        changed = CharacterChange(
            "战技 10级 · 旧名称",
            "旧描述",
            "新描述",
            "changed",
        )
        added = CharacterChange(
            "终结技 10级 · 新名称",
            None,
            "新描述",
            "added",
        )

        self.assertEqual(character_change_subject("技能", changed), "战技")
        self.assertEqual(
            character_change_subject("技能", added),
            "终结技 · 新名称",
        )

    def test_maze_diff_uses_only_the_three_highest_layer_nodes(self) -> None:
        record = replace(_record(), maze="1034")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)

            def event(monster_id: int) -> dict[str, object]:
                return {
                    "hard_level_group": 3,
                    "level": 95,
                    "elite_group": 367,
                    "monster_list": [{"monster0": monster_id}],
                }

            for version, effect, node_one_hp in (
                ("4.4.51", 0.8, 100),
                ("4.4.54", 0.9, 120),
            ):
                maze_path = root / version / "zh/maze/1034.json"
                monster_dir = root / version / "zh/monster"
                maze_path.parent.mkdir(parents=True)
                monster_dir.mkdir(parents=True)
                maze_path.write_text(
                    json.dumps(
                        [
                            {
                                "id": 5301,
                                "name": "旧层",
                                "event_id_list1": [event(1000001)],
                                "event_id_list2": [event(1000001)],
                            },
                            {
                                "id": 5312,
                                "name": "最高层",
                                "group_name": "本期效果",
                                "desc": "提高#1[i]%伤害。",
                                "param": [effect],
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
                for monster_id, hp in (
                    (1000001, 999),
                    (1000002, node_one_hp),
                    (1000003, 100),
                    (1000004, 100),
                ):
                    (monster_dir / f"{monster_id}.json").write_text(
                        json.dumps({"name": str(monster_id), "hp_base": hp, "child": [{"id": monster_id}]}),
                        encoding="utf-8",
                    )

            reports = compare_all_maze_versions(
                "4.4.51", "4.4.54", record, record, root
            )

        self.assertEqual(
            [report.sections[0].name for report in reports],
            ["Maze 1", "Maze 2", "Maze 3"],
        )
        self.assertTrue(all(report.changed_sections for report in reports))
        self.assertEqual(
            sum(change.category == "hp" for change in reports[0].sections[0].changes),
            1,
        )
        self.assertEqual(
            sum(change.category == "hp" for report in reports[1:] for change in report.sections[0].changes),
            0,
        )

    def test_lightcone_refinement_values_are_one_diff_group(self) -> None:
        parts = tokenize_refinement_diff(
            "行动提前40%/45%/50%/55%/60%。",
            "行动提前30%/32%/35%/38%/40%。",
        )

        self.assertIsNotNone(parts)
        self.assertEqual(
            [(part.kind, part.text) for part in parts or ()],
            [
                ("equal", "行动提前"),
                ("removed", "40%/45%/50%/55%/60%"),
                ("added", "30%/32%/35%/38%/40%"),
                ("equal", "。"),
            ],
        )

    def test_text_diff_tokenization_is_shared_and_numeric_aware(self) -> None:
        parts = tokenize_text_diff("提高25%伤害，持续4回合。", "提高30%伤害，持续4回合。")
        self.assertEqual(
            [(part.kind, part.text) for part in parts],
            [
                ("equal", "提高"),
                ("removed", "25%"),
                ("added", "30%"),
                ("equal", "伤害，持续"),
                ("equal", "4"),
                ("equal", "回合。"),
            ],
        )

    def test_text_diff_keeps_grouped_numbers_whole(self) -> None:
        expected = [
            ("equal", "HP "),
            ("removed", "3,086,555"),
            ("added", "3,519,511"),
        ]
        for numeric_only in (False, True):
            parts = tokenize_text_diff(
                "HP 3,086,555",
                "HP 3,519,511",
                numeric_only=numeric_only,
            )
            self.assertEqual(
                [(part.kind, part.text) for part in parts],
                expected,
            )

    def test_boss_diff_uses_effect_and_hp_sections(self) -> None:
        before = BossView("4.4.51", 1, 90, "旧首领", 1000, 2, (
            BossBuff("删除效果", "旧描述"),
            BossBuff("变更效果", "旧数值25%"),
        ))
        after = BossView("4.4.54", 1, 90, "新首领", 1200, 2, (
            BossBuff("新增效果", "新描述"),
            BossBuff("变更效果", "新数值30%"),
        ))
        with patch("hsr_version_inspector.diff.load_boss", side_effect=(before, after)):
            report = compare_boss_versions(
                "4.4.51", "4.4.54", 1, _record(), _record()
            )

        changes = report.sections[0].changes
        self.assertEqual(changes[0].category, "metadata")
        self.assertEqual(
            {(change.category, change.kind) for change in changes},
            {
                ("metadata", "changed"),
                ("effects", "removed"),
                ("effects", "added"),
                ("effects", "changed"),
                ("hp", "changed"),
            },
        )
        hp_change = changes[-1]
        self.assertEqual(hp_change.subject, "新首领")
        self.assertEqual(hp_change.wave, 0)

    def test_boss_diff_without_node_compares_all_nodes(self) -> None:
        view = BossView("4.4.51", 1, 90, "首领", 1000, 1, ())
        with patch("hsr_version_inspector.diff.available_boss_nodes", return_value=(1, 2)), patch(
            "hsr_version_inspector.diff.load_boss", side_effect=(view, view, view, view)
        ):
            reports = compare_all_boss_versions(
                "4.4.51", "4.4.54", _record(), _record()
            )

        self.assertEqual([report.sections[0].name for report in reports], ["Boss 1", "Boss 2"])

    def test_character_diff_reports_semantic_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            for version, value in (("4.4.51", 0.5), ("4.4.54", 0.6)):
                path = root / version / "zh/character/1512.json"
                path.parent.mkdir(parents=True)
                path.write_text(
                    json.dumps(
                        {
                            "name": "Test character",
                            "skills": {
                                "1": {
                                    "type_name": "普攻",
                                    "name": "Basic",
                                    "desc": "<u>#1[i]%</u> damage",
                                    "level": {"6": {"param_list": [value]}},
                                    "extra": {
                                        "effect": {
                                            "name": "Effect",
                                            "desc": f"Effect {version}",
                                        }
                                    },
                                }
                            },
                            "skill_trees": {
                                "major": {
                                    "1": {
                                        "point_type": 3,
                                        "point_name": "Major trace",
                                        "point_desc": f"Trace {version}",
                                        "param_list": [],
                                    }
                                },
                                "stat": {
                                    "1": {
                                        "point_type": 1,
                                        "point_name": "速度强化",
                                        "status_add_list": [
                                            {
                                                "property_type": "SpeedDelta",
                                                "name": "速度",
                                                "value": 2 if version == "4.4.51" else 3,
                                            }
                                        ],
                                    }
                                },
                            },
                            "ranks": {
                                str(index): {
                                    "name": f"E{index}",
                                    "desc": f"Rank {index} {version}",
                                    "param_list": [],
                                }
                                for index in range(1, 7)
                            },
                        }
                    ),
                    encoding="utf-8",
                )

            report = compare_character_versions(
                "4.4.51", "4.4.54", 1, _record(), _record(), root
            )

        changed = {section.name: section for section in report.changed_sections}
        self.assertEqual(set(changed), {"技能", "行迹", "特殊效果", "星魂"})
        skill_change = changed["技能"].changes[0]
        self.assertEqual(skill_change.label, "普攻 6级 · Basic")
        self.assertEqual(skill_change.before, "50% damage")
        self.assertEqual(skill_change.after, "60% damage")
        self.assertEqual(changed["行迹"].changes[1].before, "+2")
        self.assertEqual(changed["行迹"].changes[1].after, "+3")

    def test_compare_versions_uses_structured_json_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            for version, payload in {
                "4.4.51": {"b": 2, "a": 1, "nested": {"value": 10}},
                "4.4.54": {"nested": {"value": 20}, "a": 1, "b": 2},
            }.items():
                path = root / version / "zh/story/2026.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(payload), encoding="utf-8")

            report = compare_versions(
                "4.4.51", "4.4.54", "story", _record(), _record(), root
            )

        self.assertEqual(len(report.resources), 1)
        resource = report.resources[0]
        self.assertEqual(resource.status, "changed")
        self.assertEqual(resource.change_count, 1)
        self.assertEqual(resource.changes[0].path, '$["nested"]["value"]')
        self.assertEqual(resource.changes[0].before, 10)
        self.assertEqual(resource.changes[0].after, 20)

    def test_rejects_other_version_line_and_unsupported_mode(self) -> None:
        record = _record()
        other_line = replace(record, name="4.5", versions=("4.5.51",))
        with self.assertRaisesRegex(ValueError, "主版本号和次版本号"):
            validate_request(record, other_line, "4.4.51", "4.5.51", "story")
        with self.assertRaisesRegex(ValueError, "不支持的比较模式"):
            validate_request(record, record, "4.4.51", "4.4.54", "boss-vs-story")

    def test_lightcone_diff_reports_stats_and_effect_changes(self) -> None:
        record = replace(_record(), lightcone=("23063",))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            for version, hp, effect in (
                ("4.4.51", 100, 0.2),
                ("4.4.54", 120, 0.3),
            ):
                path = root / version / "zh/lightcone/23063.json"
                path.parent.mkdir(parents=True)
                path.write_text(
                    json.dumps(
                        {
                            "name": "Test light cone",
                            "rarity": "CombatPowerLightconeRarity5",
                            "base_type": "Memory",
                            "refinements": {
                                "name": "Test effect",
                                "desc": "提高#1[i]%，持续2回合。",
                                "level": {
                                    str(index): {"param_list": [effect]}
                                    for index in range(1, 6)
                                },
                            },
                            "stats": [
                                {
                                    "max_level": 80,
                                    "base_hp": hp,
                                    "base_hp_add": 1,
                                    "base_attack": 200,
                                    "base_attack_add": 2,
                                    "base_defence": 300,
                                    "base_defence_add": 3,
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )

            report = compare_lightcone_versions(
                "4.4.51",
                "4.4.54",
                1,
                record,
                record,
                root,
            )

        changed = {section.name: section for section in report.changed_sections}
        self.assertEqual(set(changed), {"基础属性", "光锥效果"})
        stats_change = next(
            change for change in changed["基础属性"].changes if change.label == "生命值"
        )
        self.assertEqual((stats_change.before, stats_change.after), ("179.00", "199.00"))
        effect_change = changed["光锥效果"].changes[0]
        self.assertEqual(effect_change.before, "提高20%，持续2回合。")
        self.assertEqual(effect_change.after, "提高30%，持续2回合。")

    def test_story_diff_reports_effect_and_hp_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            for version, hp, buff in (
                ("4.4.51", 100, []),
                ("4.4.54", 120, [{"name": "New effect", "desc": "Damage up", "param": []}]),
            ):
                path = root / version / "zh/story/2026.json"
                path.parent.mkdir(parents=True)
                path.write_text(
                    json.dumps(
                        {
                            "buff": buff,
                            "level": [
                                {
                                    "name": "Story node 1",
                                    "damage_type1": ["Fire"],
                                    "event_id_list1": [
                                        {
                                            "hard_level_group": 1,
                                            "level": 85,
                                            "monster_list": [{"monster0": 1000000}],
                                        }
                                    ],
                                    "infinite_list1": {
                                        "wave1": {
                                            "monster_group_id_list": [1000000],
                                            "elite_group": 1,
                                            "param_list": [0, 0],
                                        }
                                    },
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                monster_path = root / version / "zh/monster/1000000.json"
                monster_path.parent.mkdir(parents=True, exist_ok=True)
                monster_path.write_text(
                    json.dumps(
                        {
                            "name": "Test enemy",
                            "hp_base": hp,
                            "child": [{"id": 1000000, "hp_modify_ratio": 1}],
                        }
                    ),
                    encoding="utf-8",
                )

            report = compare_highmode_versions(
                "4.4.51", "4.4.54", "story", 1, _record(), _record(), root
            )

        changes = report.sections[0].changes
        self.assertIn("effects", {change.category for change in changes})
        hp_change = next(change for change in changes if change.category == "hp")
        self.assertEqual(hp_change.label, "Wave 1: Test enemy")
        self.assertIn("18,826", hp_change.before)
        self.assertIn("22,592", hp_change.after)

    def test_story_diff_without_node_compares_all_story_nodes(self) -> None:
        record = _record()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            for version, hp in (("4.4.51", 100), ("4.4.54", 120)):
                story_path = root / version / "zh/story/2026.json"
                story_path.parent.mkdir(parents=True)
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
                                    "name": "Story stage",
                                    "event_id_list1": [event],
                                    "event_id_list2": [event],
                                    "infinite_list1": {
                                        "wave1": {
                                            "monster_group_id_list": [1000000],
                                            "elite_group": 1,
                                        }
                                    },
                                    "infinite_list2": {
                                        "wave1": {
                                            "monster_group_id_list": [1000000],
                                            "elite_group": 1,
                                        }
                                    },
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                monster_path = root / version / "zh/monster/1000000.json"
                monster_path.parent.mkdir(parents=True, exist_ok=True)
                monster_path.write_text(
                    json.dumps(
                        {
                            "name": "Test enemy",
                            "hp_base": hp,
                            "child": [{"id": 1000000, "hp_modify_ratio": 1}],
                        }
                    ),
                    encoding="utf-8",
                )

            reports = compare_all_story_versions(
                "4.4.51", "4.4.54", record, record, root
            )

        self.assertEqual([report.mode for report in reports], ["story 1", "story 2"])
        self.assertTrue(all(report.changed_sections for report in reports))

    def test_knight_diff_without_node_compares_all_three_knights(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_scaling_config(root)
            for version, hp in (("4.4.51", 100), ("4.4.54", 120)):
                path = root / version / "zh/peak/9.json"
                path.parent.mkdir(parents=True)
                path.write_text(
                    json.dumps(
                        {
                            "pre_level": [
                                {
                                    "name": f"Knight {index}",
                                    "damage_type": ["Fire"],
                                    "event_id_list": [
                                        {
                                            "hard_level_group": 3,
                                            "level": 95,
                                            "monster_list": [{"monster0": 1000000}],
                                        }
                                    ],
                                    "infinite_list": {
                                        "wave1": {
                                            "monster_group_id_list": [1000000],
                                            "elite_group": 1,
                                        }
                                    },
                                }
                                for index in range(1, 4)
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                monster_path = root / version / "zh/monster/1000000.json"
                monster_path.parent.mkdir(parents=True, exist_ok=True)
                monster_path.write_text(
                    json.dumps(
                        {
                            "name": "Test enemy",
                            "hp_base": hp,
                            "child": [{"id": 1000000, "hp_modify_ratio": 1}],
                        }
                    ),
                    encoding="utf-8",
                )

            report = compare_highmode_versions(
                "4.4.51", "4.4.54", "knight", None, _record(), _record(), root
            )

        self.assertEqual([section.name for section in report.sections], [
            "Knight 1",
            "Knight 2",
            "Knight 3",
        ])
        self.assertTrue(all(section.status == "changed" for section in report.sections))


if __name__ == "__main__":
    unittest.main()
