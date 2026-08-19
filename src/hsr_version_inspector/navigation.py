"""Interactive navigation and command prompts."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from .boss import available_boss_nodes
from .data import FullCatalog, VersionRecord, find_release, latest_release
from .highmode import available_maze_nodes, available_story_nodes
from .output.labels import mode_label as _mode_label

console = Console()


def configure(
    *,
    console_obj: Console,
    load_full_data: Callable[[], FullCatalog],
    render_catalog: Callable[..., None],
    detail_panel: Callable[..., Any],
    show: Callable[..., None],
    diff: Callable[..., None],
    query: Callable[..., None],
    available_boss_nodes_fn: Callable[..., tuple[int, ...]] = available_boss_nodes,
    available_maze_nodes_fn: Callable[..., tuple[int, ...]] = available_maze_nodes,
    available_story_nodes_fn: Callable[..., tuple[int, ...]] = available_story_nodes,
    prompt_index: Callable[..., int | None] | None = None,
    prompt_record: Callable[..., VersionRecord | None] | None = None,
    prompt_release: Callable[..., str | None] | None = None,
    prompt_full_resource_id: Callable[..., int | None] | None = None,
    pause_interactive_result: Callable[[], None] | None = None,
) -> None:
    global console, _load_full_data, _render_catalog, _detail_panel, _show, _diff, _query
    global available_boss_nodes, available_maze_nodes, available_story_nodes
    global _prompt_index, _prompt_record, _prompt_release, _prompt_full_resource_id
    global _pause_interactive_result
    console = console_obj
    _load_full_data = load_full_data
    _render_catalog = render_catalog
    _detail_panel = detail_panel
    _show = show
    _diff = diff
    _query = query
    available_boss_nodes = available_boss_nodes_fn
    available_maze_nodes = available_maze_nodes_fn
    available_story_nodes = available_story_nodes_fn
    if prompt_index is not None:
        _prompt_index = prompt_index
    if prompt_record is not None:
        _prompt_record = prompt_record
    if prompt_release is not None:
        _prompt_release = prompt_release
    if prompt_full_resource_id is not None:
        _prompt_full_resource_id = prompt_full_resource_id
    if pause_interactive_result is not None:
        _pause_interactive_result = pause_interactive_result


def _load_full_data() -> FullCatalog:
    raise RuntimeError("navigation is not configured")


def _render_catalog(*args: Any, **kwargs: Any) -> None:
    raise RuntimeError("navigation is not configured")


def _detail_panel(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("navigation is not configured")


def _show(*args: Any, **kwargs: Any) -> None:
    raise RuntimeError("navigation is not configured")


def _diff(*args: Any, **kwargs: Any) -> None:
    raise RuntimeError("navigation is not configured")


def _query(*args: Any, **kwargs: Any) -> None:
    raise RuntimeError("navigation is not configured")

def _choice_table(
    title: str,
    options: tuple[tuple[str, str], ...],
    *,
    all_label: str | None = None,
) -> Table:
    table = Table(title=title, header_style="bold cyan")
    table.add_column("编号", justify="right", style="bold yellow", no_wrap=True, overflow="fold")
    table.add_column("选项", style="bold", overflow="fold")
    table.add_column("说明", overflow="fold")
    if all_label is not None:
        table.add_row("0", all_label, "选择全部")
    for index, (value, label) in enumerate(options, start=1):
        table.add_row(str(index), label, value)
    return table


def _prompt_index(
    title: str,
    options: tuple[tuple[str, str], ...],
    *,
    all_label: str | None = None,
) -> int | None:
    if not options:
        console.print("[yellow]没有可选择的项目。[/yellow]")
        return None
    console.print(_choice_table(title, options, all_label=all_label))
    choices = [str(index) for index in range(1, len(options) + 1)]
    if all_label is not None:
        choices.insert(0, "0")
    answer = Prompt.ask(
        title,
        choices=[*choices, "q"],
        default="q",
    )
    if answer == "q":
        return None
    return int(answer)


def _prompt_record(
    catalog: tuple[VersionRecord, ...],
    title: str = "选择版本组",
) -> VersionRecord | None:
    options = tuple(
        (
            record.name,
            f"版本组 {record.name}（{len(record.versions)} 个版本）",
        )
        for record in catalog
    )
    index = _prompt_index(title, options)
    return catalog[index - 1] if index is not None else None


def _prompt_release(
    record: VersionRecord,
    title: str,
    *,
    excluded: frozenset[str] = frozenset(),
) -> str | None:
    versions = tuple(version for version in record.versions if version not in excluded)
    options = tuple((version, "可比较版本") for version in versions)
    index = _prompt_index(title, options)
    return versions[index - 1] if index is not None else None


def _pause_interactive_result() -> None:
    Prompt.ask("按回车返回主菜单", default="")


def _query_mode_options() -> tuple[tuple[str, str], ...]:
    return (
        ("character", "角色"),
        ("lightcone", "光锥"),
        ("maze", "混沌"),
        ("story", "虚构"),
        ("boss", "末日"),
        ("peak", "异相（全部）"),
        ("knight", "骑士"),
        ("king", "王棋"),
        ("hard-king", "绝境"),
    )


def _query_resource_mode(mode: str) -> str:
    return "peak" if mode in {"peak", "knight", "king", "hard-king"} else mode


def _prompt_full_resource_id(full_catalog: FullCatalog, mode: str) -> int | None:
    label = _mode_label(mode)
    ids = full_catalog.resource_ids(mode)
    if not ids:
        console.print(f"[yellow]完整数据目录中没有{label}资源。[/yellow]")
        return None
    while True:
        answer = Prompt.ask(
            f"输入{label}数据 ID（{ids[0]} 至 {ids[-1]}，输入 q 返回）",
            default="q",
        )
        if answer.lower() == "q":
            return None
        if answer.isdigit() and full_catalog.contains(mode, answer):
            return int(answer)
        console.print(f"[red]{label}数据 ID {answer!r} 不在 full.json 中。[/red]")


def _show_mode_options(record: VersionRecord) -> tuple[tuple[str, str], ...]:
    options: list[tuple[str, str]] = []
    if record.character:
        options.append(("character", "角色"))
    if record.lightcone:
        options.append(("lightcone", "光锥"))
    if record.maze:
        options.append(("maze", "混沌"))
    if record.story:
        options.append(("story", "虚构"))
    if record.boss:
        options.append(("boss", "末日"))
    if record.peak:
        options.extend(
            (
                ("peak", "异相（全部）"),
                ("knight", "骑士"),
                ("king", "王棋"),
                ("hard-king", "绝境"),
            )
        )
    return tuple(options)


def _diff_mode_options(
    record_one: VersionRecord,
    record_two: VersionRecord,
) -> tuple[tuple[str, str], ...]:
    options: list[tuple[str, str]] = []
    for mode, label in (
        ("character", "角色"),
        ("lightcone", "光锥"),
        ("maze", "混沌"),
        ("story", "虚构"),
        ("boss", "末日"),
        ("peak", "异相（全部）"),
        ("knight", "骑士"),
        ("king", "王棋"),
        ("hard-king", "绝境"),
    ):
        resource_mode = "peak" if mode in {"knight", "king", "hard-king"} else mode
        first = getattr(record_one, resource_mode)
        second = getattr(record_two, resource_mode)
        if first and second:
            options.append((mode, label))
    return tuple(options)


def _run_show_wizard(
    catalog: tuple[VersionRecord, ...],
    version_or_mode: str | None = None,
    mode_or_node: str | None = None,
    node: int | None = None,
    verbose: bool = False,
) -> None:
    preset_node = node
    if version_or_mode == "knight":
        record = max(catalog, key=lambda item: max(item.versions, default=""))
        version = max(record.versions)
        preset_mode = "knight"
        if mode_or_node is not None:
            preset_node = int(mode_or_node)
    else:
        record = None
        version = version_or_mode
        preset_mode = mode_or_node.lower() if mode_or_node else None

    if record is None:
        if version is None:
            record = _prompt_record(catalog)
            if record is None:
                return
            version = _prompt_release(record, "选择版本")
            if version is None:
                return
        else:
            try:
                record = find_release(catalog, version)
            except KeyError:
                console.print(f"[red]未找到版本 {version}。[/red]")
                return

    if preset_mode is None:
        mode_index = _prompt_index("选择查看模式", _show_mode_options(record))
        if mode_index is None:
            return
        preset_mode = _show_mode_options(record)[mode_index - 1][0]
    if preset_mode not in {value for value, _ in _show_mode_options(record)}:
        console.print(f"[red]版本 {version} 不支持模式 {preset_mode}。[/red]")
        return
    if version is None:
        return

    if preset_mode == "character":
        if preset_node is None:
            index = _prompt_index(
                "选择角色",
                tuple((resource_id, f"角色 {index}") for index, resource_id in enumerate(record.character, 1)),
            )
            if index is None:
                return
            preset_node = index
        if not verbose:
            verbose_index = _prompt_index(
                "是否显示特殊效果",
                (("no", "不显示"), ("yes", "显示")),
            )
            if verbose_index is None:
                return
            verbose = verbose_index == 2
    elif preset_mode == "lightcone":
        if preset_node is None:
            index = _prompt_index(
                "选择光锥",
                tuple((resource_id, f"光锥 {index}") for index, resource_id in enumerate(record.lightcone, 1)),
            )
            if index is None:
                return
            preset_node = index
    elif preset_mode == "boss":
        nodes = available_boss_nodes(version, record.boss)
        if preset_node is None:
            index = _prompt_index(
                "选择末日节点",
                tuple((str(item), f"节点 {item}") for item in nodes),
                all_label="全部节点",
            )
            if index is None:
                return
            preset_node = None if index == 0 else index
    elif preset_mode == "story":
        nodes = available_story_nodes(version, record.story)
        if preset_node is None:
            index = _prompt_index(
                "选择虚构节点",
                tuple((str(item), f"节点 {item}") for item in nodes),
                all_label="全部节点",
            )
            if index is None:
                return
            preset_node = None if index == 0 else index
    elif preset_mode == "maze":
        nodes = available_maze_nodes(version, record.maze)
        if preset_node is None:
            index = _prompt_index(
                "选择混沌节点",
                tuple((str(item), f"节点 {item}") for item in nodes),
                all_label="全部节点",
            )
            if index is None:
                return
            preset_node = None if index == 0 else index
    elif preset_mode == "knight":
        if preset_node is None:
            index = _prompt_index(
                "选择骑士",
                tuple((str(item), f"骑士 {item}") for item in (1, 2, 3)),
                all_label="全部骑士",
            )
            if index is None:
                return
            preset_node = None if index == 0 else index
    else:
        preset_node = None

    _show(version, preset_mode, preset_node, verbose)
    _pause_interactive_result()


def _run_diff_wizard(
    catalog: tuple[VersionRecord, ...],
    version_one: str | None = None,
    version_two: str | None = None,
    mode: str | None = None,
    node: int | None = None,
    verbose: bool = False,
) -> None:
    record: VersionRecord | None = None
    if version_one is not None:
        try:
            record = find_release(catalog, version_one)
        except KeyError:
            console.print(f"[red]未找到版本 {version_one}。[/red]")
            return
    elif version_two is not None:
        try:
            record = find_release(catalog, version_two)
        except KeyError:
            console.print(f"[red]未找到版本 {version_two}。[/red]")
            return
    else:
        record = _prompt_record(catalog)
        if record is None:
            return

    if version_one is None:
        version_one = _prompt_release(
            record,
            "选择旧版本",
            excluded=frozenset({version_two}) if version_two else frozenset(),
        )
        if version_one is None:
            return
    if version_two is None:
        version_two = _prompt_release(
            record,
            "选择新版本",
            excluded=frozenset({version_one}),
        )
        if version_two is None:
            return

    record_two = find_release(catalog, version_two)
    if record.name != record_two.name:
        console.print("[red]两个版本必须属于同一版本组。[/red]")
        return

    if mode is None:
        mode_index = _prompt_index(
            "选择比较模式",
            _diff_mode_options(record, record_two),
        )
        if mode_index is None:
            return
        mode = _diff_mode_options(record, record_two)[mode_index - 1][0]
    mode = mode.lower()

    if mode in {"character", "lightcone"} and node is None:
        resources = getattr(record, mode)
        resource_name = "角色" if mode == "character" else "光锥"
        index = _prompt_index(
            f"选择{resource_name}",
            tuple((resource_id, f"{resource_name} {index}") for index, resource_id in enumerate(resources, 1)),
            all_label=f"全部{resource_name}",
        )
        if index is None:
            return
        node = None if index == 0 else index
        if mode == "character" and not verbose:
            verbose_index = _prompt_index(
                "是否显示特殊效果差异",
                (("no", "不显示"), ("yes", "显示")),
            )
            if verbose_index is None:
                return
            verbose = verbose_index == 2
    elif mode == "story" and node is None:
        nodes = available_story_nodes(version_one, record.story)
        index = _prompt_index(
            "选择虚构节点",
            tuple((str(item), f"节点 {item}") for item in nodes),
            all_label="全部节点",
        )
        if index is None:
            return
        node = None if index == 0 else index
    elif mode == "maze" and node is None:
        nodes = available_maze_nodes(version_one, record.maze)
        index = _prompt_index(
            "选择混沌节点",
            tuple((str(item), f"节点 {item}") for item in nodes),
            all_label="全部节点",
        )
        if index is None:
            return
        node = None if index == 0 else index
    elif mode == "knight" and node is None:
        index = _prompt_index(
            "选择骑士",
            tuple((str(item), f"骑士 {item}") for item in (1, 2, 3)),
            all_label="全部骑士",
        )
        if index is None:
            return
        node = None if index == 0 else index

    _diff(version_one, version_two, mode, node, verbose)
    _pause_interactive_result()


def _run_query_wizard(
    catalog: tuple[VersionRecord, ...],
    mode: str | None = None,
    resource_id: int | None = None,
    node: int | None = None,
    verbose: bool = False,
) -> None:
    if mode is None:
        mode_index = _prompt_index("选择查询模式", _query_mode_options())
        if mode_index is None:
            return
        mode = _query_mode_options()[mode_index - 1][0]
    mode = mode.lower()
    if mode not in {value for value, _ in _query_mode_options()}:
        console.print(f"[red]不支持的查询模式 {mode}。[/red]")
        return

    full_catalog = _load_full_data()
    resource_mode = _query_resource_mode(mode)
    if resource_id is None:
        resource_id = _prompt_full_resource_id(full_catalog, resource_mode)
        if resource_id is None:
            return

    version = latest_release(catalog)
    console.print(f"[dim]使用最新版本 {version}。[/dim]")

    if mode == "character" and not verbose:
        verbose_index = _prompt_index(
            "是否显示特殊效果",
            (("no", "不显示"), ("yes", "显示")),
        )
        if verbose_index is None:
            return
        verbose = verbose_index == 2
    elif mode == "boss" and node is None:
        nodes = available_boss_nodes(version, str(resource_id))
        index = _prompt_index(
            "选择末日节点",
            tuple((str(item), f"节点 {item}") for item in nodes),
            all_label="全部节点",
        )
        if index is None:
            return
        node = None if index == 0 else index
    elif mode == "story" and node is None:
        nodes = available_story_nodes(version, str(resource_id))
        index = _prompt_index(
            "选择虚构节点",
            tuple((str(item), f"节点 {item}") for item in nodes),
            all_label="全部节点",
        )
        if index is None:
            return
        node = None if index == 0 else index
    elif mode == "maze" and node is None:
        nodes = available_maze_nodes(version, str(resource_id))
        index = _prompt_index(
            "选择混沌节点",
            tuple((str(item), f"节点 {item}") for item in nodes),
            all_label="全部节点",
        )
        if index is None:
            return
        node = None if index == 0 else index
    elif mode == "knight" and node is None:
        index = _prompt_index(
            "选择骑士",
            tuple((str(item), f"骑士 {item}") for item in (1, 2, 3)),
            all_label="全部骑士",
        )
        if index is None:
            return
        node = None if index == 0 else index

    _query(mode, resource_id, node, verbose=verbose)
    _pause_interactive_result()


def _run_catalog_browser(catalog: tuple[VersionRecord, ...]) -> None:
    while True:
        console.clear()
        index = _prompt_index(
            "浏览版本信息",
            tuple(
                (record.name, f"版本组 {record.name}")
                for record in catalog
            ),
        )
        if index is None:
            return
        console.print(_detail_panel(catalog[index - 1]))
        action = Prompt.ask("按回车继续浏览，输入 q 返回主菜单", default="")
        if action.lower() == "q":
            return


def _run_tui(catalog: tuple[VersionRecord, ...]) -> None:
    if not catalog:
        console.print("[yellow]版本目录为空。[/yellow]")
        return

    if not sys.stdin.isatty():
        _render_catalog(catalog)
        return

    while True:
        console.clear()
        _render_catalog(catalog)
        choice = _prompt_index(
            "选择操作",
            (
                ("show", "查看数据"),
                ("diff", "比较版本差异"),
                ("query", "全量数据查询"),
                ("catalog", "浏览版本信息"),
            ),
        )
        if choice is None:
            return
        if choice == 1:
            _run_show_wizard(catalog)
        elif choice == 2:
            _run_diff_wizard(catalog)
        elif choice == 3:
            _run_query_wizard(catalog)
        else:
            _run_catalog_browser(catalog)


# Keep immutable references for the compatibility wrappers in app.py.  The
# configurable names above may point at test doubles or application callbacks.
default_choice_table = _choice_table
default_prompt_index = _prompt_index
default_prompt_record = _prompt_record
default_prompt_release = _prompt_release
default_pause_interactive_result = _pause_interactive_result
default_prompt_full_resource_id = _prompt_full_resource_id


def run_tui(catalog: tuple[VersionRecord, ...]) -> None:
    _run_tui(catalog)
