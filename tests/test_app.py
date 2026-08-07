import unittest
import importlib
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from hsr_version_inspector.boss import BossBuff
from hsr_version_inspector.data import VersionRecord
from hsr_version_inspector.diff import HighModeChange, HighModeDiffReport, HighModeSectionDiff
from hsr_version_inspector.highmode import HighModeEnemy, HighModeView, HighModeWave


app_module = importlib.import_module("hsr_version_inspector.app")


class AppTests(unittest.TestCase):
    def test_interactive_navigation_forces_terminal_output(self) -> None:
        catalog = (
            VersionRecord(
                name="4.4",
                versions=("4.4.54",),
                character=("1512",),
                lightcone=(),
                maze="",
                story="",
                boss="",
                peak="",
            ),
        )
        output = StringIO()
        terminal = Console(file=output, color_system=None, width=120)

        with patch.object(app_module, "MARKDOWN_OUTPUT", True), patch.object(
            app_module, "console", terminal
        ), patch.object(app_module.sys.stdin, "isatty", return_value=False):
            app_module.run_tui(catalog)

        self.assertNotIn("# 星穹铁道版本检查器", output.getvalue())
        self.assertIn("版本组", output.getvalue())

    def test_batch_show_uses_mode_order(self) -> None:
        record = VersionRecord(
            name="4.4",
            versions=("4.4.54",),
            character=("c1", "c2"),
            lightcone=("l1",),
            maze="m1",
            story="s1",
            boss="b1",
            peak="p1",
        )
        calls: list[str] = []

        with patch.object(app_module, "available_story_nodes", return_value=(1, 2)), patch.object(
            app_module, "available_boss_nodes", return_value=(1, 2)
        ), patch.object(app_module, "load_character", side_effect=lambda version, resource: resource), patch.object(
            app_module, "load_lightcone", side_effect=lambda version, resource: resource
        ), patch.object(
            app_module,
            "load_story",
            side_effect=lambda version, resource, node: HighModeView(
                "4.4.54",
                f"故事敌人{node}",
                85,
                (),
                (),
                (HighModeWave(1, 85, (HighModeEnemy(f"故事敌人{node}", 1),)),),
            ),
        ), patch.object(
            app_module, "load_boss", side_effect=lambda version, resource, node: node
        ), patch.object(app_module, "load_peak", side_effect=lambda version, resource, mode, node: (mode, node)), patch.object(
            app_module, "available_maze_nodes", return_value=(1,)
        ), patch.object(app_module, "load_maze", return_value="m1"), patch.object(
            app_module, "render_character", side_effect=lambda view, verbose: calls.append(f"角色:{view}")), patch.object(
            app_module, "render_lightcone", side_effect=lambda view: calls.append(f"光锥:{view}")
        ), patch.object(app_module, "render_maze", side_effect=lambda view, seen: calls.append("混沌")), patch.object(
            app_module, "render_boss", side_effect=lambda view: calls.append(f"末日:{view}")
        ), patch.object(
            app_module,
            "render_highmode",
            side_effect=lambda view, **kwargs: calls.append(
                f"高难:{view.title}" if isinstance(view, HighModeView) else f"高难:{view}"
            ),
        ), patch.object(app_module, "_batch_separator"):
            app_module._render_show_all("4.4.54", record, False)

        self.assertEqual(
            calls,
            [
                "角色:c1",
                "角色:c2",
                "光锥:l1",
                "混沌",
                "高难:故事敌人1",
                "高难:故事敌人2",
                "末日:1",
                "末日:2",
                "高难:('knight', 1)",
                "高难:('knight', 2)",
                "高难:('knight', 3)",
                "高难:('king', None)",
                "高难:('hard-king', None)",
            ],
        )

    def test_highmode_markdown_fills_single_enemy_count(self) -> None:
        view = HighModeView(
            version="4.4.54",
            title="节点 1",
            level=85,
            recommended_elements=(),
            buffs=(),
            waves=(HighModeWave(1, 85, (HighModeEnemy("敌人", 123, 1),)),),
        )

        output = "\n".join(app_module._markdown_highmode(view))

        self.assertIn(r"| 敌人 | \*1 | 123 |", output)

    def test_enemy_count_text_uses_multiplication_sign_in_terminal(self) -> None:
        self.assertEqual(app_module._enemy_count_text(1), "×1")

    def test_highmode_phase_headers_use_p_labels(self) -> None:
        view = HighModeView(
            version="4.4.54",
            title="首领",
            level=100,
            recommended_elements=(),
            buffs=(),
            waves=(
                HighModeWave(
                    1,
                    100,
                    (HighModeEnemy("首领", 100, phase_hps=(100, 200, 300)),),
                ),
            ),
        )

        output = "\n".join(app_module._markdown_highmode(view))

        self.assertIn("| 敌人 | 数量 | P1 | P2 | P3 |", output)
        self.assertNotIn("阶段生命值", output)

    def test_highmode_diff_uses_show_style_summary(self) -> None:
        report = HighModeDiffReport(
            version_one="4.4.51",
            version_two="4.4.54",
            mode="knight",
            sections=(
                HighModeSectionDiff(
                    "Knight 1",
                    "changed",
                    (HighModeChange("effects", "Stage: 刚毅", None, "描述", "added"),),
                ),
            ),
        )
        output = StringIO()
        terminal = Console(file=output, color_system=None, width=120)

        with patch.object(app_module, "console", terminal):
            app_module.render_highmode_diff(report)

        rendered = output.getvalue()
        self.assertIn("骑士差异", rendered)
        self.assertIn("版本", rendered)
        self.assertIn("模式", rendered)
        self.assertIn("关卡效果", rendered)
        self.assertIn("效果", rendered)
        self.assertIn("新增", rendered)

    def test_batch_story_export_puts_shared_buffs_before_nodes(self) -> None:
        record = VersionRecord(
            name="4.4",
            versions=("4.4.54",),
            character=(),
            lightcone=(),
            maze="",
            story="s1",
            boss="",
            peak="",
        )
        common = BossBuff("共通效果", "重复描述")
        views = {
            1: HighModeView(
                version="4.4.54",
                title="原始标题 1",
                level=85,
                recommended_elements=(),
                buffs=(),
                season_buffs=(common,),
                waves=(HighModeWave(1, 85, (HighModeEnemy("敌人", 1),)),),
            ),
            2: HighModeView(
                version="4.4.54",
                title="原始标题 2",
                level=85,
                recommended_elements=(),
                buffs=(),
                season_buffs=(common,),
                waves=(HighModeWave(1, 85, (HighModeEnemy("敌人", 1),)),),
            ),
        }
        calls: list[tuple[str | None, tuple[str, ...] | None]] = []

        class Renderer:
            def begin_mode(self, title: str) -> None:
                pass

        with patch.object(app_module, "PDF_OUTPUT", True), patch.object(
            app_module, "PDF_RENDERER", Renderer()
        ), patch.object(app_module, "available_story_nodes", return_value=(1, 2)), patch.object(
            app_module, "load_story", side_effect=lambda version, resource, node: views[node]
        ), patch.object(
            app_module,
            "render_highmode",
            side_effect=lambda view, **kwargs: calls.append(
                (
                    kwargs.get("title"),
                    tuple(buff.name for buff in kwargs.get("prelude_buffs", ())),
                )
            ),
        ), patch.object(app_module, "_batch_separator"):
            app_module._render_show_all("4.4.54", record, False)

        self.assertEqual(calls, [(None, ("共通效果",)), (None, ())])

    def test_export_without_mode_routes_to_batch_renderers(self) -> None:
        record = VersionRecord(
            name="4.4",
            versions=("4.4.51", "4.4.54"),
            character=(),
            lightcone=(),
            maze="",
            story="",
            boss="",
            peak="",
        )
        with patch.object(app_module, "_load_data", return_value=(record,)), patch.object(
            app_module, "_render_show_all"
        ) as show_all, patch.object(app_module, "_render_diff_all", return_value=False) as diff_all, patch.object(
            app_module, "_print_no_changes"
        ), patch.object(app_module.sys.stdout, "isatty", return_value=False
        ):
            app_module.show("4.4.54", None, None, False, True, False)
            app_module.diff("4.4.51", "4.4.54", None, None, False, True, False)

        show_all.assert_called_once_with("4.4.54", record, False)
        diff_all.assert_called_once_with("4.4.51", "4.4.54", record, record, False)


if __name__ == "__main__":
    unittest.main()
