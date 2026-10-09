# 文献检索与官方 PDF 下载

将查找论文、核对文献信息和获取官方 PDF 整合为一次任务，并留下可检查的结果与失败记录。这个 Skill 为 Agent（AI 助手）提供操作流程和配套命令。

适用于研究人员、学生，以及需要整理学术材料的使用者。你可以提供研究主题、DOI（论文标识符）、题名、官方出版社链接或文献列表；Agent 根据需求运行必要步骤，返回候选论文、核验结果、通过检查的 PDF 和待人工处理的项目。

## 能做什么

| 你的需求 | 工作方式 | 主要结果 |
|---|---|---|
| 按主题找论文 | 选择来源、检索、合并重复记录 | 候选列表与来源记录 |
| 核对已有文献 | 回查标识符，比较题名、作者、年份等信息 | 匹配结果、冲突与缺失字段 |
| 下载指定论文 | 查找官方页面与 PDF，检查来源和文件身份 | 官方 PDF 与待处理记录 |
| 找论文并下载 | 连续完成检索、核验和下载 | 文献记录与文件的对应关系 |
| 导出文献列表 | 按核验状态导出 RIS 或 BibTeX | 供后续文献管理使用的文件 |

检索结果是候选文献。书目信息匹配、PDF 身份通过检查，以及论文是否支持某个论点，是不同判断；正式选用哪些引用仍由使用者决定。本 Skill 不自动导入 Zotero 或修改 Word 引用。

## 准备依赖

| 依赖 | 用途 | 是否必须 | 用户准备 | 缺失影响 |
|---|---|---|---|---|
| Python ≥ 3.11 | 运行命令 | 必须 | 安装 Python，建议使用独立虚拟环境 | 所有脚本无法运行 |
| requests ≥ 2.31、< 3 | 数据库请求与 HTTP 下载 | 基础安装必须 | 在仓库根目录运行 `python -m pip install .` | 检索、核验与直接下载不可用 |
| pypdf ≥ 6、< 7 | 读取 PDF、检查页数与身份 | 基础安装必须 | 同上，自动随基础依赖安装 | PDF 不能完成验收 |
| cloakbrowser ≥ 0.4.10、< 0.5 及其浏览器二进制 | 处理需要浏览器访问的官方页面 | 可选 | 安装 `.[browser]`，按官方方式准备本地二进制 | 浏览器获取不可用，其他步骤可继续 |
| 数据源配置与网络 | 访问选定数据库和出版社 | 按来源需要 | PubMed 配置 `PUBMED_EMAIL`；其他邮件或 API key 按诊断提示配置 | 受影响来源会失败或受限，其余结果保留 |
| 出版社访问权限 | 获取受访问限制的论文 | 按论文需要 | 使用自己已有的合法访问权限；必要时在本次可见浏览器中手动登录 | 对应论文列入待处理记录 |

不需要 MCP、外部 LLM 或付费中转。项目不附带账号、Cookie、浏览器 profile 或浏览器二进制。更详细的准备方式见 [安装与依赖](references/setup.md)。

## 开始使用

下载本仓库，在仓库根目录安装并检查环境：

```bash
python -m pip install .
literature-workflow doctor --mode all
```

需要浏览器获取功能时，另行安装可选依赖：

```bash
python -m pip install ".[browser]"
```

将本仓库目录作为 `literature-search-download` Skill 放入 Agent 的技能目录。Codex 的常用位置是 `~/.codex/skills/literature-search-download/`；安装细节见 [setup.md](references/setup.md)。

安装后，直接告诉 Agent：

```text
使用 $literature-search-download，查找二维材料中激子的近年研究，
说明检索来源和范围，核对候选论文，并尝试下载其官方 PDF。
```

可以指定年份、文献数量、是否包含预印本和输出目录。无需先把输入整理成固定 CSV；文件输入可用 JSON、CSV 或文本，RIS/BibTeX 输入当前仅支持其中含 DOI 的记录，无 DOI 的 RIS/BibTeX 文件会被拒绝。普通题名或引用请作为文本提供，由保守解析流程处理。更多请求见 [使用示例](examples/requests.md)。Agent 发现依赖不全时应说明缺少什么、影响哪一步和最少需要准备什么，并继续可运行的阶段。

也可以直接运行命令：

```bash
literature-workflow search "exciton transport two dimensional materials" --sources crossref,europe_pmc --rows 3 --language zh --output runs/search
literature-workflow verify --doi "10.1371/journal.pone.0000308" --language zh --output runs/verify
literature-workflow download --input papers.txt --no-browser --language zh --output runs/download
literature-workflow search-download "exciton transport two dimensional materials" --rows 3 --no-browser --language zh --output runs/search-download
literature-workflow export --input runs/search-download/records.json --format ris --language zh --output runs/export
```

示例 DOI 对应 2007 年的 *Sharing Detailed Research Data Is Associated with Increased Citation Rate*，已完成元数据回查；这不承诺以后每次运行都可下载。每次选择新的或空的输出目录，已有结果不会覆盖。单独 DOI 回查不等于核对原引用，核验原引用时可用 `--expected-title`、`--expected-year` 提供预期字段。源仓库内也可使用 `python scripts/literature.py` 运行相同命令；完整参数以 `--help` 为准。

## 来源与结果

已接入的论文来源为 Crossref、PubMed、arXiv、OpenAlex、Europe PMC 和 Semantic Scholar。默认查询 Crossref 与 Europe PMC；Agent 按主题与可用配置选择来源，每次报告实际查询、失败和范围限制。

正常完成的业务任务生成 `run.json`、`records.json` 和 `report.md`。下载还生成 `download_manifest.json`，通过检查的 PDF 放入 `papers/`；未获取或身份不确定的项目保留在 JSON 和报告中。导出产生 `references.ris` 或 `references.bib`。字段与状态见 [工作流契约](references/workflow-contract.md)。

这是有数量边界的检索流程，不保证穷尽数据库。自动 PDF 获取仅限可核实的官方出版社来源，不回退到仓储或第三方副本；页面变化、访问限制和身份证据不足都可能需要人工处理。浏览器每次使用新的独立 profile；`--profile-root` 只指定其容器目录，不复用既有登录或 Cookie。`doctor` 检查本地依赖与部分配置，不证明浏览器二进制、网络或出版社访问已可用；具体可用性以实际运行结果为准。

## 已验证的范围

65 项离线测试已通过，覆盖来源异常、标识符与版本冲突、PDF 身份检查、禁止覆盖和敏感信息处理。安装包已在独立环境安装并验证命令入口。

在 Python 3.12、requests 2.34.2、pypdf 6.20.0 的隔离环境中，已完成 Crossref 与 Europe PMC 的真实主题检索（每源 2 条，共 4 条记录）、示例 PLOS DOI 的独立元数据核验，以及官方 HTTP PDF 下载的页数和身份检查。单候选的检索→核验→下载链路取得 1 份验收通过的 PDF，RIS 导出得到 1 条记录。

负例验证确认题名或年份冲突的记录不进入引用导出，RIS/BibTeX 中的签名 URL 参数与邮件信息经过脱敏，遗漏记录保留输入关联和原因。浏览器备用获取路径尚未完成真实回归；PubMed、arXiv、OpenAlex 和 Semantic Scholar 尚未完成本版本联网回归。上述验证不代表所有来源、平台或出版社均可用。

## 来源与许可

本项目整合 [nature-academic-search](https://github.com/wp-a/nature-academic-search) 的检索与核验代码、[K-Dense Scientific Agent Skills](https://github.com/K-Dense-AI/scientific-agent-skills) 中 `paper-lookup` 的数据源操作知识，以及官方 PDF 下载流程。本项目新增统一命令入口、阶段衔接、依赖诊断与可追踪输出。上游知识覆盖不代表所有数据源都已接入。

本项目新代码按 [MIT](LICENSE) 许可发布；上游代码与运行依赖保留各自许可。贡献归属与保留的许可文本见 [第三方记录](THIRD_PARTY_NOTICES.md)。
