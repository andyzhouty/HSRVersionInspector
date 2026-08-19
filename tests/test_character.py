import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from hsr_version_inspector.app import (
    _lightcone_text_markup,
    _markdown_shared_text_markup,
    _shared_text_markup,
    render_character,
)
from hsr_version_inspector.character import (
    _load_traces,
    group_skill_entries,
    load_character,
)


class CharacterTests(unittest.TestCase):
    def test_trace_values_between_zero_and_one_use_percent_format(self) -> None:
        _, stats = _load_traces(
            {
                "ratio": {
                    "1": {
                        "point_type": 1,
                        "status_add_list": [
                            {"name": "小数", "property_type": "Unknown", "value": 0.25},
                            {"name": "边界", "property_type": "Unknown", "value": 0.999},
                            {"name": "零", "property_type": "Unknown", "value": 0},
                            {"name": "整数", "property_type": "Unknown", "value": 1},
                        ],
                    }
                }
            }
        )

        self.assertEqual(
            [(stat.name, stat.description) for stat in stats],
            [("小数", "+25%"), ("边界", "+99.9%"), ("零", "+0"), ("整数", "+1")],
        )

    def test_shared_text_markup_keeps_common_text_once(self) -> None:
        markup = _shared_text_markup(
            "造成伤害提高1%，持续2回合。",
            "造成伤害提高1.5%，持续2回合。",
        )

        self.assertEqual(markup.count("造成伤害提高"), 1)
        self.assertEqual(markup.count("持续2回合。"), 1)
        self.assertIn("[red strike]1%[/red strike][green]1.5%[/green]", markup)

        wrapped = _shared_text_markup("晴空乐手", "「晴空乐手」")
        self.assertEqual(wrapped.count("晴空乐手"), 1)
        self.assertEqual(wrapped, "[green]「[/green]晴空乐手[green]」[/green]")

    def test_multiplication_sign_is_not_changed_in_markdown_diff(self) -> None:
        terminal = _shared_text_markup("气氛值*0.4%", "气氛值*0.5%")
        markdown = _markdown_shared_text_markup("气氛值*0.4%", "气氛值*0.5%")

        self.assertIn("×", terminal)
        self.assertNotIn("*", terminal)
        self.assertIn("*", markdown)

    def test_lightcone_markup_strikes_old_refinement_values(self) -> None:
        markup = _lightcone_text_markup(
            "行动提前40%/45%/50%/55%/60%。",
            "行动提前30%/32%/35%/38%/40%。",
        )

        self.assertNotIn("->", markup)
        self.assertIn(
            "[red strike]40%/45%/50%/55%/60%[/red strike]"
            "[green]30%/32%/35%/38%/40%[/green]",
            markup,
        )

    def test_load_character_expands_levels_and_removes_tags(self) -> None:
        payload = {
            "name": "Test character",
            "base_type": "Shaman",
            "stats": {
                "0": {
                    "hp_base": 100,
                    "attack_base": 50,
                    "defence_base": 40,
                    "speed_base": 95,
                },
                "6": {
                    "hp_base": 556.512,
                    "hp_add": 8.184,
                    "attack_base": 278.256,
                    "attack_add": 4.092,
                    "defence_base": 224.4,
                    "defence_add": 3.3,
                    "speed_base": 98,
                },
            },
            "skills": {
                "1": {
                    "type_name": "普攻",
                    "name": "Basic",
                    "desc": "<u>#1[i]%</u> damage\\nnext line",
                    "level": {"6": {"param_list": [0.5]}},
                    "extra": {
                        "effect": {"name": "Effect", "desc": "<u>Special</u>"}
                    },
                },
                "2": {
                    "type_name": "",
                    "name": "Internal",
                    "desc": "hidden",
                    "level": {"1": {"param_list": []}},
                },
            },
            "memosprite": {
                "name": "Memory",
                "skills": {
                    "3": {
                        "type_name": "忆灵技",
                        "name": "Memory skill",
                        "desc": "<color=x>#1[f1]%</color>",
                        "level": {"6": {"param_list": [0.125]}},
                    }
                },
            },
            "skill_trees": {
                "point": {
                    "1": {
                        "point_type": 3,
                        "point_name": "Major trace",
                        "point_desc": "<unbreak>#1[i]%</unbreak>",
                        "param_list": [0.2],
                    }
                },
                "stat_1": {
                    "1": {
                        "point_type": 1,
                        "point_name": "速度强化",
                        "status_add_list": [
                            {
                                "property_type": "SpeedDelta",
                                "name": "速度",
                                "value": 2,
                            }
                        ],
                    }
                },
                "stat_2": {
                    "1": {
                        "point_type": 1,
                        "point_name": "生命强化",
                        "status_add_list": [
                            {
                                "property_type": "HPAddedRatio",
                                "name": "生命值",
                                "value": 0.04,
                            }
                        ],
                    }
                },
                "stat_3": {
                    "1": {
                        "point_type": 1,
                        "point_name": "欢愉度强化",
                        "status_add_list": [
                            {
                                "property_type": "ElationDamageAddedRatioBase",
                                "name": "欢愉度",
                                "value": 0.04,
                            }
                        ],
                    }
                },
                "stat_4": {
                    "1": {
                        "point_type": 1,
                        "point_name": "欢愉度强化",
                        "status_add_list": [
                            {
                                "property_type": "ElationDamageAddedRatioBase",
                                "name": "欢愉度",
                                "value": 0.06,
                            }
                        ],
                    }
                },
            },
            "ranks": {
                str(index): {
                    "name": f"Eidolon {index}",
                    "desc": f"<u>{index}</u>",
                    "param_list": [],
                }
                for index in range(1, 7)
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "4.4.51/zh/character/1512.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
            view = load_character("4.4.51", "1512", Path(directory))

        self.assertEqual(view.level, 80)
        self.assertEqual(view.path, "同谐")
        assert view.base_stats is not None
        self.assertEqual(
            (view.base_stats.hp, view.base_stats.attack, view.base_stats.defence, view.base_stats.speed),
            ("1203.05", "601.52", "485.10", "98"),
        )
        self.assertEqual(len(view.skills), 1)
        self.assertEqual(view.skills[0].level, 6)
        self.assertEqual(view.skills[0].description, "50% damage\nnext line")
        self.assertEqual(view.memosprite_skills[0].description, "12.5%")
        self.assertEqual(view.traces[0].description, "20%")
        self.assertEqual(
            [(stat.name, stat.description) for stat in view.trace_stats],
            [("速度", "+2"), ("生命值", "+4%"), ("欢愉度", "+10%")],
        )
        self.assertEqual(view.special_effects[0].description, "Special")
        self.assertEqual(len(view.eidolons), 6)

        default_output = StringIO()
        with patch(
            "hsr_version_inspector.app.console",
            Console(file=default_output, color_system=None, width=120),
        ):
            render_character(view)
        self.assertNotIn("特殊效果", default_output.getvalue())

        verbose_output = StringIO()
        with patch(
            "hsr_version_inspector.app.console",
            Console(file=verbose_output, color_system=None, width=120),
        ):
            render_character(view, verbose=True)
        self.assertIn("特殊效果", verbose_output.getvalue())

    def test_assist_skill_uses_level_ten_and_ultimates_share_one_group(self) -> None:
        payload = {
            "name": "Test 1510",
            "stats": {"0": {"hp_base": 1, "attack_base": 1, "defence_base": 1, "speed_base": 1}},
            "skills": {
                "assist": {
                    "type_name": "助战技",
                    "name": "助战",
                    "desc": "助战描述",
                    "level": {"1": {}, "10": {}},
                },
                "ultimate_1": {
                    "type_name": "终结技",
                    "name": "终结技一",
                    "desc": "第一段",
                    "level": {"1": {}, "10": {}},
                },
                "invalid_ultimate": {
                    "type_name": "终结技",
                    "name": "不应显示",
                    "desc": None,
                    "simple_desc": "修复后的描述",
                    "level": {"1": {}},
                },
                "ultimate_2": {
                    "type_name": "终结技",
                    "name": "终结技二",
                    "desc": "第二段",
                    "level": {"1": {}, "10": {}},
                },
                "invalid_type": {
                    "type_name": None,
                    "name": "不应显示",
                    "desc": "不应显示",
                    "level": {"1": {}},
                },
                "unrecoverable": {
                    "type_name": "天赋",
                    "name": "无法恢复",
                    "desc": None,
                    "simple_desc": None,
                    "level": {"1": {}},
                },
                "assist_2": {
                    "type_name": "助战技",
                    "name": "助战二",
                    "desc": "助战描述二",
                    "level": {"1": {}, "10": {}},
                },
            },
            "ranks": {
                "1": {"name": None, "desc": "不应显示"},
                "2": {"name": "星魂二", "desc": "应显示"},
            },
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "4.4.54/zh/character/1510.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
            view = load_character("4.4.54", "1510", Path(directory))

        self.assertEqual(
            [(skill.type_name, skill.name, skill.level) for skill in view.skills],
            [
                ("助战技", "助战", 10),
                ("终结技", "终结技一", 10),
                ("终结技", "终结技二", 10),
                ("助战技", "助战二", 10),
            ],
        )
        groups = group_skill_entries(view.skills)
        ultimate_groups = [group for group in groups if group and group[0].type_name == "终结技"]
        self.assertEqual(len(ultimate_groups), 1)
        self.assertEqual(
            [entry.name for entry in ultimate_groups[0]],
            ["终结技一", "终结技二"],
        )
        assist_groups = [group for group in groups if group and group[0].type_name == "助战技"]
        self.assertEqual(len(assist_groups), 1)
        self.assertEqual([entry.name for entry in assist_groups[0]], ["助战", "助战二"])
        self.assertEqual([entry.name for entry in view.eidolons], ["星魂二"])

        output = StringIO()
        with patch(
            "hsr_version_inspector.app.console",
            Console(file=output, color_system=None, width=120),
        ):
            render_character(view)
        rendered = output.getvalue()
        self.assertIn("助战技 10级", rendered)
        self.assertEqual(rendered.count("助战技 10级"), 1)
        self.assertEqual(rendered.count("终结技 10级"), 1)
        self.assertIn("终结技一", rendered)
        self.assertIn("终结技二", rendered)
        self.assertIn("─", rendered)
        self.assertNotIn("修复后的描述", rendered)
        self.assertNotIn("不应显示", rendered)
        self.assertNotIn("无法恢复", rendered)


if __name__ == "__main__":
    unittest.main()
