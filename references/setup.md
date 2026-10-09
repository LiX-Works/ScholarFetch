# 安装与依赖

## 安装基础功能

需要 Python 3.11 或以上。在下载的仓库根目录使用独立 Python 环境安装：

```bash
python -m pip install .
literature-workflow doctor --mode all
```

基础依赖为 `requests>=2.31,<3` 和 `pypdf>=6,<7`，随安装自动准备。安装后的命令是 `literature-workflow`；源仓库也可用 `python scripts/literature.py`，参数相同。

`doctor` 只做本地诊断，不发送网络请求。它可以检查依赖和配置是否存在，不能证明数据库请求或出版社下载已成功。使用 `--mode search` 或 `--mode download` 可只诊断相关阶段。业务能力以实际命令结果为准。

准备批量输入时可使用 JSON、CSV 或文本。RIS/BibTeX 输入当前仅支持提取含 DOI 的记录；无 DOI 的 RIS/BibTeX 文件会被拒绝，不属于完整语法导入。普通引用或题名请通过文本文件或 `--citation` 提供，解析不明确的项目会保留待处理状态。运行时每次为 `--output` 选择新的或空的目录，重复执行应更换目录；已有结果不会覆盖。中文报告可指定 `--language zh`。

## 安装为 Agent Skill

将本仓库的完整目录放入 Agent 支持的技能目录，文件夹名称为 `literature-search-download`。保留 `SKILL.md`、`scripts/`、`src/`、`references/` 和许可文件。

Codex 的常用目录为 `~/.codex/skills/literature-search-download/`。如果配置了自定义技能目录，以实际配置为准。在 Skill 根目录安装 Python 依赖后，通过 `$literature-search-download` 调用。安装 Python 包与放置 Skill 是两个步骤；只安装包不会自动注册 Agent Skill 或 MCP。

## 数据源配置

默认检索来源是 `crossref,europe_pmc`。可通过 `--sources` 选择 `crossref`、`pubmed`、`arxiv`、`openalex`、`europe_pmc`、`semantic_scholar`。

本实现使用 PubMed 时需要 `PUBMED_EMAIL`；缺失时该来源标为未查询。`doctor` 显示 `PUBMED_EMAIL`、`NCBI_API_KEY`、`OPENALEX_API_KEY` 和 `S2_API_KEY` 是否存在，不显示值。其他来源的邮件或 API key 配置按诊断提示与所选来源的要求准备；不能从适配器存在推断无需凭据或一定能够访问。来源选择参考 [source-guide.md](source-guide.md)。

只在本地环境变量中配置个人邮件或密钥，不写入仓库、示例、结果文件或共享报告。未配置某一来源不会把其他来源的已有结果作废。网络限制、限流和服务状态也可能使请求失败。

## 可选浏览器获取

HTTP 是优先获取路径；需要浏览器访问官方页面时，可安装：

```bash
python -m pip install ".[browser]"
```

该额外依赖使用 `cloakbrowser>=0.4.10,<0.5`。浏览器二进制需按 [CloakBrowser 官方说明](https://github.com/CloakHQ/CloakBrowser) 单独准备，缓存保留在本地；Python 包安装成功不能替代二进制可用性检查。浏览器二进制适用其独立许可，本仓库不分发它。

下载命令可用 `--no-browser` 明确只走 HTTP。浏览器获取默认在本次运行目录的 `private_profiles/` 下以新 UUID 创建独立 profile。`--profile-root` 指定这些独立 profile 的容器目录，不指定已有 profile，也不复用以前的登录或 Cookie。必要时，用户可在本次可见浏览器内手动登录，使用已有合法访问权限；本项目不从个人浏览器提取 Cookie，不自动搬迁登录状态。profile 及整个运行目录不得直接作为公开源码发布；共享结果时只选择检查过的产物。

`--headless` 用于不显示浏览器的执行方式；需要交互登录或手动处理访问验证时，不应假定无界面执行可以完成。等待时长可用 `--wait` 设置，默认值以当前命令帮助为准。

## 缺依赖时 Agent 的处理

先说明缺少的组件名称、受影响阶段和最小准备办法，再继续其他可执行步骤。例如：

- 缺少 `pypdf`：不能把 PDF 标为已验收；仍可保留解析结果和待处理记录。
- 缺少 `cloakbrowser` 或浏览器二进制：继续检索、核验与 HTTP 获取，浏览器步骤报告不可用。
- 缺少来源所需配置：记录该来源缺口，继续已配置来源，不把缺配置写成“没有相关论文”。
- 没有论文访问权限：保留官方入口和失败原因，交给用户处理，继续批次中其他论文。

不要将组件安装、配置存在或本地诊断通过描述为真实联网成功。不要擅自启用付费服务、导出凭据或以其他本机旧环境冒充本项目执行。
