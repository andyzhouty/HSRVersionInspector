"""Batch show/diff orchestration.

The functions here know the stable mode order, but not Typer, Rich, or module
globals.  The application supplies rendering and data-loading callbacks so
the orchestration remains easy to test in isolation.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..data import VersionRecord
from ..diff import (
    compare_all_boss_versions,
    compare_all_character_versions,
    compare_all_lightcone_versions,
    compare_all_maze_versions,
    compare_all_story_versions,
    compare_highmode_versions,
)

Render = Callable[..., None]
ErrorTypes = (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError)
BATCH_PEAK_SECTIONS = (
    ("knight", 1),
    ("knight", 2),
    ("knight", 3),
    ("king", None),
    ("hard-king", None),
)


@dataclass(frozen=True)
class BatchRenderContext:
    available_maze_nodes: Callable[[str, str], tuple[int, ...]]
    available_story_nodes: Callable[[str, str], tuple[int, ...]]
    available_boss_nodes: Callable[[str, str], tuple[int, ...]]
    load_character: Callable[[str, str], Any]
    load_lightcone: Callable[[str, str], Any]
    load_maze: Callable[[str, str, int], Any]
    load_story: Callable[[str, str, int], Any]
    load_boss: Callable[[str, str, int], Any]
    load_peak: Callable[[str, str, str, int | None], Any]
    render_character: Render
    render_lightcone: Render
    render_maze: Render
    render_highmode: Render
    render_boss: Render
    render_character_diff: Render
    render_lightcone_diff: Render
    render_highmode_diff: Render
    render_batch_error: Callable[[str, Exception], None]
    batch_separator: Callable[[bool], None]
    begin_pdf_mode: Callable[[str], None]
    begin_pdf_diff_mode: Callable[[str], None]
    register_diff_overview: Callable[..., None] | None = None
    mode_label: Callable[[str], str] = str
    pdf_output: bool = False
    pdf_renderer: Any = None


def render_show_all(version: str, record: VersionRecord, verbose: bool, context: BatchRenderContext) -> None:
    """Render every configured mode in the stable export order."""
    has_output = False

    def emit(title: str, render: Callable[[], None]) -> None:
        nonlocal has_output
        context.batch_separator(has_output)
        try:
            render()
        except ErrorTypes as error:
            context.render_batch_error(title, error)
        has_output = True

    def emit_error(title: str, error: Exception) -> None:
        nonlocal has_output
        context.batch_separator(has_output)
        context.render_batch_error(title, error)
        has_output = True

    for index, resource_id in enumerate(record.character):
        if index == 0:
            context.begin_pdf_mode("角色")
        emit(
            f"角色 · {resource_id}",
            lambda resource_id=resource_id: context.render_character(
                context.load_character(version, resource_id), verbose
            ),
        )
    for index, resource_id in enumerate(record.lightcone):
        if index == 0:
            context.begin_pdf_mode("光锥")
        emit(
            f"光锥 · {resource_id}",
            lambda resource_id=resource_id: context.render_lightcone(
                context.load_lightcone(version, resource_id)
            ),
        )

    if record.maze:
        try:
            maze_nodes = context.available_maze_nodes(version, record.maze)
        except ErrorTypes as error:
            context.begin_pdf_mode("混沌")
            emit_error("混沌", error)
        else:
            if maze_nodes:
                context.begin_pdf_mode("混沌")
            seen_maze_buffs: set[tuple[str, str]] = set()
            for maze_node in maze_nodes:
                emit(
                    f"混沌 · 节点 {maze_node}",
                    lambda maze_node=maze_node: context.render_maze(
                        context.load_maze(version, record.maze, maze_node),
                        seen_maze_buffs,
                    ),
                )

    if record.story:
        try:
            story_nodes = context.available_story_nodes(version, record.story)
        except ErrorTypes as error:
            context.begin_pdf_mode("虚构")
            emit_error("虚构", error)
        else:
            if story_nodes:
                context.begin_pdf_mode("虚构")

            def render_story_node(node: int, first: bool) -> None:
                view = context.load_story(version, record.story, node)
                context.render_highmode(view, prelude_buffs=view.season_buffs if first else ())

            for index, node in enumerate(story_nodes):
                emit(
                    f"虚构 · 节点 {node}",
                    lambda node=node, index=index: render_story_node(node, index == 0),
                )

    if record.boss:
        try:
            boss_nodes = context.available_boss_nodes(version, record.boss)
        except ErrorTypes as error:
            context.begin_pdf_mode("末日")
            emit_error("末日", error)
        else:
            if boss_nodes:
                context.begin_pdf_mode("末日")
            for node in boss_nodes:
                emit(
                    f"末日 · 节点 {node}",
                    lambda node=node: context.render_boss(
                        context.load_boss(version, record.boss, node)
                    ),
                )

    if record.peak:
        context.begin_pdf_mode("异相")
        for mode, node in BATCH_PEAK_SECTIONS:
            title = context.mode_label(mode) if node is None else f"{context.mode_label(mode)} {node}"
            emit(
                title,
                lambda mode=mode, node=node: context.render_highmode(
                    context.load_peak(version, record.peak, mode, node)
                ),
            )


def render_diff_all(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    verbose: bool,
    context: BatchRenderContext,
) -> bool:
    """Render changed resources in the same order used by batch show."""
    has_output = False

    def emit(render: Callable[[], None]) -> None:
        nonlocal has_output
        context.batch_separator(has_output)
        render()
        has_output = True

    def register(reports: tuple[Any, ...], *args: Any) -> None:
        if context.pdf_output and context.register_diff_overview is not None:
            for report in reports:
                context.register_diff_overview(report, *args)

    if record_one.character and record_two.character:
        all_reports = compare_all_character_versions(version_one, version_two, record_one, record_two)
        register(all_reports, verbose)
        reports = tuple(
            report for report in all_reports
            if any(section.status != "unchanged" and (verbose or section.name != "特殊效果") for section in report.sections)
        )
        if reports:
            context.begin_pdf_diff_mode("角色差异")
        for report in reports:
            emit(lambda report=report: context.render_character_diff(report, verbose))

    if record_one.lightcone and record_two.lightcone:
        all_reports = compare_all_lightcone_versions(version_one, version_two, record_one, record_two)
        register(all_reports)
        reports = tuple(report for report in all_reports if report.changed_sections)
        if reports:
            context.begin_pdf_diff_mode("光锥差异")
        for report in reports:
            emit(lambda report=report: context.render_lightcone_diff(report))

    if record_one.maze and record_two.maze:
        all_reports = compare_all_maze_versions(version_one, version_two, record_one, record_two)
        register(all_reports)
        reports = tuple(report for report in all_reports if report.changed_sections)
        if reports:
            context.begin_pdf_diff_mode("混沌差异")
        for index, report in enumerate(reports):
            emit(lambda report=report, index=index: context.render_highmode_diff(report, index == 0))

    if record_one.story and record_two.story:
        all_reports = compare_all_story_versions(version_one, version_two, record_one, record_two)
        register(all_reports)
        reports = tuple(report for report in all_reports if report.changed_sections)
        if reports:
            context.begin_pdf_diff_mode("虚构差异")
        for index, report in enumerate(reports):
            emit(lambda report=report, index=index: context.render_highmode_diff(report, index == 0))

    if record_one.boss and record_two.boss:
        all_reports = compare_all_boss_versions(version_one, version_two, record_one, record_two)
        register(all_reports)
        reports = tuple(report for report in all_reports if report.changed_sections)
        if reports:
            context.begin_pdf_diff_mode("末日差异")
        for index, report in enumerate(reports):
            emit(lambda report=report, index=index: context.render_highmode_diff(report, index == 0))

    if record_one.peak and record_two.peak:
        report = compare_highmode_versions(version_one, version_two, "peak", None, record_one, record_two)
        register((report,))
        if report.changed_sections:
            context.begin_pdf_diff_mode("异相差异")
            emit(lambda: context.render_highmode_diff(report))

    return has_output
