# HSRVersionInspector

一个基于 Typer 的终端界面，用于浏览 `versionID.json` 中的版本数据。

## 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## 使用

安装锁定的依赖并启动交互式浏览器：

```bash
uv sync
uv run hvi
```

如果希望从当前项目安装命令供日常使用：

```bash
uv tool install .
hvi
```

发布软件包后，可以使用以下命令安装：

```bash
uv tool install hsr-version-inspector
```

常用的非交互式命令：

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

`show` 命令用于显示角色和光锥描述，或选择指定版本的最高难度并显示高难度关卡效果、敌人波次和生命值。
关卡模式省略节点时会显示全部节点；角色和光锥序号使用 `versionID.json` 中的数组顺序，并且仍然是必填的。
角色默认显示 80 级、预设技能等级以及特殊效果。光锥默认显示 80 级的全部叠影数据，相同文本只显示一次。
支持的异相快捷方式包括 `knight 1`、`knight 2`、`knight 3`、`king` 和 `hard-king`。
混沌只显示最高难度层及其三个节点，不会额外显示较低难度层或内部的 `pre_id` 记录。
省略 `knight` 的版本时，会使用目录中的最新版本。怪物基础数据由 `download` 下载到
`data/{version}/zh/monster/{id}.json`，敌人倍率配置下载到 `data/config/`。

`query` 命令用于按真实数据 ID 查询全量数据。省略参数时，会先选择模式，再输入 `full.json` 中的真实资源 ID，
然后使用本地目录中的最新版本，不使用 `versionID.json` 的数组序号。例如：`query character 1512` 和
`query lightcone 23063`。高难度模式的查询格式为 `query 模式 数据ID [节点]`，例如 `query story 2026 3`。
异相资源可使用 `peak`、`knight`、`king` 或 `hard-king` 作为模式。
原有的 `show` 和 `diff` 命令仍使用各自的版本范围、数组序号和节点规则。

`diff` 命令用于比较同一 `major.minor` 版本线中的两个不同小版本。支持的模式包括 `character`、`lightcone`、
`maze`、`story`、`boss`、`peak`、`knight`、`king` 和 `hard-king`；例如 `4.4.54` 与 `4.5.51` 这样的跨版本线
比较会被拒绝。`lightcone 1` 用于比较一个光锥，省略序号时比较列表中的全部光锥。
高难度比较中，`peak` 会比较三个骑士、王棋和绝境王棋；`knight` 比较三个骑士，`knight 1/2/3` 可单独选择一个骑士。
旧版的 `story 1`、`story 2` 等格式仍可用于比较单个虚构节点。
高难度输出会比较关卡效果和敌人生命值，包括阶段生命值与敌人数量。
角色比较使用角色数组序号，例如 `character 1`；省略序号时比较列表中的全部角色，并比较展开后的技能、忆灵技能、行迹、
特殊效果和星魂描述。

`download` 会读取 `versionID.json` 中的全部 `version` 项。它只为最新版本下载 `full.json` 覆盖的完整资源，
旧版本则只保留 `show` 和 `diff` 所需的 `versionID.json` 资源。下载完成后，会自动删除旧版本中多余的全量缓存。
运行 `hvi cleanup` 可以在不下载数据的情况下单独执行本地清理。
已存在的文件会跳过，因此可以在中断后安全地继续下载；返回 HTTP 404 的资源会被记录，但不会中断其他下载。
`download` 默认使用 40 路并行请求，可通过 `HVI_DOWNLOAD_WORKERS` 设置 1 到 64 之间的并发数。
敌人生命值使用下载的 `HardLevelGroup`、`EliteGroup` 和 `InfiniteEliteGroup` 配置计算，而不是使用固定的版本系数。

下载得到的 `data/` 目录不会被打包进安装包。从项目目录运行时，HVI 使用项目目录下的 `data/`。
从其他目录运行已安装的 `hvi` 命令时，Linux 默认使用 `~/.local/share/hsr-version-inspector/data`，
Windows 或 macOS 使用对应的应用数据目录。如需指定其他位置，可设置 `HVI_DATA_DIR`。

运行测试：

```bash
uv run tests
uv run ruff check src tests
```

## 项目结构

- `src/hsr_version_inspector/app.py`：Typer app、公共渲染入口、输出状态和兼容导出。
- `src/hsr_version_inspector/cli.py`：组装 Typer app，并调用各命令模块完成注册。
- `src/hsr_version_inspector/navigation.py`：交互式导航、选择器和命令向导。
- `src/hsr_version_inspector/commands/`：各命令的注册、参数处理、资源路由和批量渲染编排。
- `src/hsr_version_inspector/output/`：公共标签、文本转换、差异标记和语义输出模型。
- `src/hsr_version_inspector/render/`：终端和 Markdown 渲染器。
- `src/hsr_version_inspector/pdf/`：保持 `PdfRenderer` 公共入口，包含 PDF 基础组件、展示和差异渲染。
- `src/hsr_version_inspector/boss.py`：首领选择、生命值计算和效果格式化。
- `src/hsr_version_inspector/character.py`：角色技能、行迹、效果和星魂解析。
- `src/hsr_version_inspector/lightcone.py`：光锥属性和叠影数据解析。
- `src/hsr_version_inspector/highmode/`：异相、虚构等高难度数据解析、敌人组装及视图模型。
- `src/hsr_version_inspector/scaling.py`：敌人生命值倍率表加载和计算公式。
- `src/hsr_version_inspector/data.py`：JSON 目录加载和校验。
- `src/hsr_version_inspector/download/`：下载模型、目标发现和 HTTP 传输；兼容入口保留在包内。
- `src/hsr_version_inspector/commands/download.py`：并发执行、清理和下载结果汇总。
- `src/hsr_version_inspector/diff/`：差异比较兼容入口、模型、统一分词和各领域比较实现。
- `versionID.json`：默认版本元数据目录。
- `full.json`：`query` 和 `download` 使用的完整资源 ID 目录。
