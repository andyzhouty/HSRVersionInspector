import unittest

from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import HRFlowable, PageBreak, Spacer, Table

from hsr_version_inspector.character import CharacterSkill, CharacterView
from hsr_version_inspector.diff import (
    CharacterChange,
    CharacterDiffReport,
    CharacterSectionDiff,
    HighModeChange,
    HighModeDiffReport,
    HighModeSectionDiff,
)
from hsr_version_inspector.highmode import HighModeEnemy, HighModeView, HighModeWave
from hsr_version_inspector.lightcone import LightConeView
from hsr_version_inspector.pdf import PdfRenderer, SYMBOL_FONT, _enemy_count_text, _symbol_font_text


class PdfTests(unittest.TestCase):
    def test_pdf_styles_have_distinct_text_hierarchy(self) -> None:
        renderer = PdfRenderer()

        self.assertGreater(renderer.title.fontSize, renderer.resource_title.fontSize)
        self.assertGreater(renderer.resource_title.fontSize, renderer.subtitle.fontSize)
        self.assertGreater(renderer.subtitle.fontSize, renderer.subheading.fontSize)
        self.assertGreater(renderer.subheading.fontSize, renderer.box_title.fontSize)
        self.assertGreater(renderer.box_title.fontSize, renderer.body.fontSize)
        self.assertGreater(renderer.body.fontSize, renderer.table_body.fontSize)

    def test_music_note_uses_a_registered_symbol_font(self) -> None:
        PdfRenderer()

        self.assertIn(SYMBOL_FONT, pdfmetrics.getRegisteredFontNames())
        self.assertIn(f'<font name="{SYMBOL_FONT}">♪</font>', _symbol_font_text("♪"))

    def test_renderer_builds_a_pdf_without_markdown_conversion(self) -> None:
        renderer = PdfRenderer()
        renderer._box("新增", '<font color="#198754">新增：测试内容</font>', markup=True)

        output = renderer.build()

        self.assertTrue(output.startswith(b"%PDF-"))
        self.assertIn(b"ReportLab", output)

    def test_skill_group_has_a_splittable_separator_row(self) -> None:
        renderer = PdfRenderer()
        renderer._skills(
            "技能",
            (
                CharacterSkill("助战技", "技能一", 10, "描述一"),
                CharacterSkill("助战技", "技能二", 10, "描述二"),
            ),
        )

        table = next(item for item in renderer.story if isinstance(item, Table))
        self.assertEqual(table.splitByRow, 1)
        self.assertIsInstance(table._cellvalues[2][0], HRFlowable)

    def test_highmode_nodes_have_extra_pdf_spacing(self) -> None:
        renderer = PdfRenderer()
        view = HighModeView(
            version="4.4.54",
            title="敌人",
            level=85,
            recommended_elements=(),
            buffs=(),
            waves=(HighModeWave(1, 85, (HighModeEnemy("敌人", 100),)),),
        )
        renderer.begin_mode("混沌")
        renderer.add_highmode(view)
        renderer.add_highmode(view)

        self.assertTrue(
            any(
                isinstance(item, Spacer) and item.height == 30
                for item in renderer.story
            )
        )

    def test_diff_modes_use_spacing_instead_of_page_breaks(self) -> None:
        renderer = PdfRenderer()
        renderer.begin_diff_mode("角色差异")
        renderer.begin_diff_mode("光锥差异")

        self.assertFalse(any(isinstance(item, PageBreak) for item in renderer.story))
        self.assertTrue(
            any(
                isinstance(item, Spacer) and item.height == 45
                for item in renderer.story
            )
        )

    def test_lightcones_have_twenty_point_pdf_spacing(self) -> None:
        renderer = PdfRenderer()
        view = LightConeView(
            version="4.4.54",
            lightcone_id="23063",
            name="光锥",
            level=80,
            rarity=5,
            path="记忆",
            hp="100.00",
            attack="200.00",
            defence="300.00",
            refinement="1/2/3/4/5",
            refinement_name="效果",
            description="描述",
        )
        renderer.begin_mode("光锥")
        renderer.add_lightcone(view)
        renderer.add_lightcone(view)

        self.assertTrue(
            any(
                isinstance(item, Spacer) and item.height == 20
                for item in renderer.story
            )
        )

    def test_summary_table_uses_name_row_and_value_row(self) -> None:
        renderer = PdfRenderer()

        table = renderer._summary_table(
            [("等级", "85级"), ("推荐属性", "物理、虚数")],
        )

        self.assertEqual(len(table._cellvalues), 2)
        self.assertEqual(len(table._cellvalues[0]), 2)
        self.assertEqual(len(table._cellvalues[1]), 2)

    def test_enemy_table_can_omit_column_headers(self) -> None:
        renderer = PdfRenderer()

        table = renderer._table_flowable(
            None,
            [("敌人", "×1", "100,000")],
            [100, 50, 100],
        )

        self.assertEqual(len(table._cellvalues), 1)
        self.assertEqual(table.repeatRows, 0)

    def test_diff_tables_omit_column_headers(self) -> None:
        renderer = PdfRenderer()

        change_table = renderer._change_table([("战技", "变更")])
        status_table = renderer._status_table([
            ("刚毅", "新增", "描述"),
        ])

        self.assertEqual(len(change_table._cellvalues), 1)
        self.assertEqual(change_table.repeatRows, 0)
        self.assertEqual(len(status_table._cellvalues), 1)
        self.assertEqual(status_table.repeatRows, 0)

    def test_diff_overview_records_names_and_node_numbers(self) -> None:
        character_renderer = PdfRenderer()
        character_renderer.add_character_diff(
            CharacterDiffReport(
                "4.4.51",
                "4.4.54",
                1,
                "1512",
                "1512",
                "角色一",
                "角色一",
                (
                    CharacterSectionDiff(
                        "技能",
                        "changed",
                        (CharacterChange("战技", "旧", "新", "changed"),),
                    ),
                ),
            )
        )
        self.assertEqual(
            character_renderer.diff_overview,
            [("角色 · 角色一", 1)],
        )

        highmode_renderer = PdfRenderer()
        highmode_renderer.add_highmode_diff(
            HighModeDiffReport(
                "4.4.51",
                "4.4.54",
                "boss",
                (
                    HighModeSectionDiff(
                        "Boss 3",
                        "changed",
                        (HighModeChange("hp", "Wave 0: 首领", "旧", "新", "changed"),),
                    ),
                ),
            )
        )
        self.assertEqual(
            highmode_renderer.diff_overview,
            [("末日 · 节点 3", 1)],
        )

        unchanged_renderer = PdfRenderer()
        unchanged_renderer.add_highmode_diff(
            HighModeDiffReport(
                "4.4.51",
                "4.4.54",
                "maze",
                (HighModeSectionDiff("Maze 1", "unchanged", ()),),
            )
        )
        self.assertEqual(unchanged_renderer.diff_overview, [("混沌 · 节点 1", 0)])
        self.assertEqual(unchanged_renderer.story, [])

    def test_pdf_enemy_count_uses_multiplication_sign(self) -> None:
        self.assertEqual(_enemy_count_text(1), "×1")
        self.assertEqual(_enemy_count_text(12), "×12")

    def test_characters_have_thirty_point_pdf_spacing(self) -> None:
        renderer = PdfRenderer()
        view = CharacterView(
            version="4.4.54",
            character_id="1512",
            name="角色",
            path="同谐",
            level=80,
            base_stats=None,
            skills=(),
            memosprite_name=None,
            memosprite_skills=(),
            traces=(),
            trace_stats=(),
            special_effects=(),
            eidolons=(),
        )
        renderer.begin_mode("角色")
        renderer.add_character(view)
        renderer.add_character(view)

        self.assertTrue(
            any(
                isinstance(item, Spacer) and item.height == 30
                for item in renderer.story
            )
        )


if __name__ == "__main__":
    unittest.main()
