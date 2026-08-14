# HSRVersionInspector

A Typer-based terminal UI for browsing the version metadata in `versionID.json`.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Run

Install the locked dependencies and launch the interactive browser:

```bash
uv sync
uv run hvi
```

To install the command for regular use from this project:

```bash
uv tool install .
hvi
```

After publishing the package, the equivalent command is:

```bash
uv tool install hsr-version-inspector
```

Useful non-interactive commands:

```bash
uv run hvi list
uv run hvi download
uv run hvi cleanup
uv run hvi show 4.4.51 character 1
uv run hvi show 4.4.54 lightcone 1
uv run hvi show 4.4.51 boss 1
uv run hvi show 4.4.54 boss
uv run hvi show 4.4.54 story
uv run hvi show 4.4.54 maze
uv run hvi show 4.4.54 maze 3
uv run hvi show 4.4.54 peak
uv run hvi show 4.4.54 knight
uv run hvi show knight 1
uv run hvi show 4.4.51 king
uv run hvi show 4.4.51 hard-king
uv run hvi diff 4.4.51 4.4.54 story
uv run hvi diff 4.4.51 4.4.54 peak
uv run hvi diff 4.4.51 4.4.54 knight 1
uv run hvi diff 4.4.51 4.4.54 story 1
uv run hvi diff 4.4.51 4.4.54 character 1
uv run hvi query character 1512
uv run hvi query lightcone 23063
uv run hvi query maze 1034 1
uv run hvi query story 2026 3
uv run hvi query peak 9
uv run hvi list --markdown > versions.md
uv run hvi show 4.4.54 character 1 --markdown > character.md
uv run hvi diff 4.4.51 4.4.54 knight 1 --markdown > diff.md
uv run hvi show 4.4.54 --markdown > all-show.md
uv run hvi diff 4.4.51 4.4.54 --markdown > all-diff.md
uv run hvi show 4.4.54 character 1 --pdf > character.pdf
uv run hvi query character 1512 --pdf > character.pdf
uv run hvi diff 4.4.51 4.4.54 knight 1 --pdf > diff.pdf
uv run hvi show 4.4.54 --pdf > all-show.pdf
uv run hvi diff 4.4.51 4.4.54 --pdf > all-diff.pdf
```

直接运行 `uv run hvi` 时，会进入导航菜单。“查看数据”和“比较版本差异”向导会依次让你选择
版本、模式和资源编号；“全量数据查询”则先选择模式、再输入真实数据 ID，并自动使用最新版本。
所有选择都输入数字即可。直接运行
`uv run hvi show`、`uv run hvi diff` 或 `uv run hvi query` 也会进入对应向导，按 `q` 返回或退出。

`list`、`show`、`diff` 和 `query` 支持 `--markdown`，可配合 `>` 保存或转发。`show 版本`
会按角色、光锥、混沌、虚构、末日、异相（骑士、王棋、绝境）的顺序列出该版本的全部数据；
`diff 版本1 版本2` 使用相同顺序，并跳过没有变更的模式。
这些命令也支持 `--pdf`，PDF 由解析后的数据直接生成，保留颜色、表格、边框和分页；批量导出按模式分页，
同一模式内的角色、光锥或节点连续排版。使用
`>` 将二进制输出保存为文件。`--markdown` 和 `--pdf` 不能同时使用。交互式向导和
`download` 不使用这些选项。
PDF 字体按微软雅黑、Noto Sans CJK、兼容中文字体的顺序查找，并会嵌入可用字体。

The `show` command displays character and light-cone descriptions or selects
the highest difficulty for the requested release and displays high-mode stage
effects, enemy waves, and HP. Omitting a node displays all nodes for stage
modes; character and light-cone indexes use the order in `versionID.json` and
remain required. Character output uses level 80 with the configured skill
levels and includes special effects. Light cones use level 80 and show all
superimpositions with shared text rendered once. Supported peak
shortcuts are `knight 1`, `knight 2`, `knight 3`, `king`, and `hard-king`.
Maze output uses only the highest available layer and exposes its three nodes;
the lower layers and the internal `pre_id` record are not displayed as extra
nodes.
`knight` without a version uses the latest release in the catalog. Monster
base data is downloaded into `data/{version}/zh/monster/{id}.json` by
`download`. The same command also downloads the source-driven enemy
scaling tables into `data/config/`.

`query` is the full-data lookup command. Without arguments, it asks for a
mode and a real resource ID from `full.json`, then uses the newest version in
the local catalog. It does not use a `versionID.json` array index: for example,
`query character 1512` and `query lightcone 23063`. High-mode queries use
`query 模式 数据ID [节点]`, such as `query story 2026 3`.
For peak resources, use `peak`, `knight`, `king`, or `hard-king` as the mode.
The original `show` and `diff` commands continue to use their existing
version-scoped index and node behavior.

`diff` compares one mode between two different releases from the same
`major.minor` version line. Supported data modes are `character`, `lightcone`,
`maze`, `story`, `boss`, `peak`, `knight`, `king`, and `hard-king`; cross-line releases
such as `4.4.54` and `4.5.51` are rejected. `lightcone 1` compares one
light-cone, while omitting the index compares every light-cone in the list.
High-mode comparisons use `peak` for all three knights plus king and hard-king.
`knight` compares all three knights, while `knight 1/2/3` selects one knight.
The legacy `story 1`, `story 2`, etc. form remains available for one story node.
High-mode output compares effect descriptions and enemy HP, including phase HP
and enemy counts.
Character comparisons can use the character array index, for example
`character 1`; omitting the index compares every character in the list.
They compare expanded skill descriptions, 忆灵技能, traces, special
effects, and eidolons.

`download` reads every `version` entry from `versionID.json`. It downloads the
complete `full.json` resource set only for the newest release, while retaining
only the `versionID.json` resources required by `show` and `diff` for older
releases. After the download completes, redundant full-cache files from older
versions are removed automatically. Run `hvi cleanup` to perform that local
cleanup without downloading.
Existing files are skipped so the command can be safely resumed after an
interruption; resources that return HTTP 404 are reported and do not stop the
remaining downloads. `download` uses 40 concurrent requests by default. Set
`HVI_DOWNLOAD_WORKERS` to a value from 1 to 64 to tune this for the available
network connection. Enemy HP is calculated from the downloaded
`HardLevelGroup`, `EliteGroup`, and `InfiniteEliteGroup` tables rather than a
version-specific constant.

The downloaded `data/` directory is not included in the installed package.
When running from the project directory, HVI uses that directory's `data/`
folder. When running an installed `hvi` command elsewhere, it uses
`~/.local/share/hsr-version-inspector/data` on Linux, the corresponding
application data directory on Windows or macOS, and honors `HVI_DATA_DIR` when
an explicit location is needed.

Run the tests with:

```bash
uv run tests
```

## Layout

- `src/hsr_version_inspector/app.py`: Typer commands and Rich terminal UI.
- `src/hsr_version_inspector/boss.py`: Boss selection, HP calculation, and buff formatting.
- `src/hsr_version_inspector/character.py`: Character skill, trace, effect, and eidolon parsing.
- `src/hsr_version_inspector/lightcone.py`: Light-cone stats and superimposition parsing.
- `src/hsr_version_inspector/highmode.py`: Peak/story high-difficulty parsing and HP calculation.
- `src/hsr_version_inspector/scaling.py`: Enemy HP scaling table loading and formula.
- `src/hsr_version_inspector/data.py`: JSON catalog loading and validation.
- `src/hsr_version_inspector/download.py`: Resource URL generation and downloads.
- `versionID.json`: default version metadata catalog.
- `full.json`: complete resource IDs for `query` and `download`.
