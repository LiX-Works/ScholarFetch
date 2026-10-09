# 工作流与结果契约

本文说明统一命令的阶段、实际产物和结果解释。参数以当前命令 `--help` 为准；字段以实际 JSON 输出为准，不把示例作为执行证据。

## 命令与输入

源仓库使用 `python scripts/literature.py`，安装 Python 包后使用 `literature-workflow`。

| 命令 | 输入与关键选项 | 运行阶段 |
|---|---|---|
| `doctor` | `--mode search\|download\|all` | 本地依赖与配置诊断，无网络请求 |
| `search QUERY` | `--sources`、`--rows`、日期/作者/文献类型过滤 | 按来源检索、规范化与去重 |
| `verify` | 可重复的 `--doi`、`--id`、`--citation` 或 `--input`；可提供 `--expected-title`、`--expected-year` | 输入解析、标识符回查和预期字段比较 |
| `download` | 可重复的 `--doi`、`--url`、`--citation` 或 `--input`；可设 `--no-browser`、`--profile-root`、`--headless`、`--wait` | 解析、必要核验、官方获取与 PDF 检查 |
| `search-download QUERY` | 检索和下载选项 | 连续执行检索、核验、官方下载 |
| `export` | `--input`、`--format ris\|bibtex` | 从记录导出合格引用 |

业务命令均支持 `--output` 和 `--language zh|en`（CLI 默认英语）。建议每次显式指定新的或空的独立输出目录；非空目录会被拒绝，已有结果不会覆盖。省略 `--output` 时，命令在 `outputs/` 下创建本次独立目录。

`search` 和 `search-download` 支持 `--date-from YYYY-MM-DD`、`--date-to YYYY-MM-DD`、`--author TEXT` 和可重复的 `--document-type TYPE`（例如 `journal-article`）。请求过滤条件写入 `run.json` 的 `requested_filters`。具体来源支持和执行方式可能不同，应结合结果中的来源记录与实际范围说明，不能只因传入参数就声称所有来源都按同一规则过滤。

可直接提供 DOI、标识符、题名、普通引用或官方链接。文件输入支持 JSON、CSV 和文本。RIS/BibTeX 输入当前只提取含 DOI 的记录，不提供完整格式语法导入；没有 DOI 的 RIS/BibTeX 文件会被 CLI 拒绝，不能把它们描述成已完整导入。普通题名或引用应以文本或 `--citation` 提供，走保守身份解析。无法确定身份时保留待处理项目，不强行补造记录；单个歧义记录不应阻止可解析项目继续处理。

## 实际产物

| 文件或目录 | 内容 |
|---|---|
| `run.json` | 本次任务、执行阶段、范围与状态 |
| `records.json` | 文献记录、来源信息、核验与冲突 |
| `report.md` | 给使用者阅读的结果、范围缺口与待处理事项 |
| `download_manifest.json` | 下载目标、获取结果、文件验证与来源关联 |
| `papers/` | 通过来源及 PDF 检查的文件 |
| `references.ris` 或 `references.bib` | 引用交换文件，由 `export` 生成 |

前三项是业务任务的通用产物；下载额外产生 manifest 和论文目录。只有实际生成的文件才能在交付中链接。未通过检查的响应或文件不进入 `papers/`。失败和待处理项目在 JSON 与报告中保留。

## 来源与检索范围

实际接入六个论文来源：`crossref`、`pubmed`、`arxiv`、`openalex`、`europe_pmc`、`semantic_scholar`。默认查询 `crossref,europe_pmc`。来源适配器存在、配置存在和上游文档覆盖，都不证明本次已成功查询。

结果以 `sources_queried`、`sources_succeeded`、`sources_failed`、`sources_not_queried` 和 `errors` 记录实际来源操作；`coverage` 保留来源报告总数、获取数量与截断原因（若源提供）。有效零结果与请求失败不同，HTTP 200 中的错误响应也不能作为成功。`--rows` 当前接受 1—50，是每个来源的获取数量边界，不是最终去重后的论文总数；不能用一次有限检索声称完整覆盖。

同一规范化请求只走一条检索执行路径，不因上游来源重叠而重复查询。独立核验与有理由的重试可以作为新的操作记录。

## 文献身份与核验

保留原输入与解析记录的对应关系，使用 DOI、PMID、arXiv 等强标识符提供身份依据。题名相似只能提出匹配线索。冲突的标识符或书目字段不能被最后一次返回值静默覆盖；预印本、修订版和正式出版版需要保留版本差异。

核验说明回查依据、比较字段、匹配或冲突，以及来源无法提供的字段。单独 DOI 回查找到记录不等于证明原引用题名、作者或年份正确。用户提供预期题名或年份后，应报告该字段的实际比较结果；未比较的字段仍属未核验。

| `metadata_status` | 含义 |
|---|---|
| `not_checked` | 仅为候选，尚未进行独立回查 |
| `verified` | 声明核验范围内的字段匹配，没有未解决身份冲突 |
| `partial` | 部分预期字段或标识符缺失、无法核验 |
| `mismatch` | 预期字段、标识符或版本存在冲突 |
| `unresolved` | 尚未取得可靠的匹配记录 |

结合 `verification_scope`、`field_checks`、`verified_fields`、`unchecked_fields`、`unchecked_identifiers` 和 `conflicts` 解读状态。`verified` 仅覆盖已声明的核验范围，不代表整篇内容已读或所有书目字段均已检查。

以下判断彼此独立：

- 候选与身份解析：得到一条可能相关的文献记录。
- 元数据核验：所声明字段与来源一致。
- PDF 验收：文件来源合格、可读且身份符合目标论文。
- 论断支持：阅读论文后判断是否支持特定论点，本 CLI 不自动完成。
- 人工选引：使用者决定在文稿中引用哪些论文。

## 官方 PDF 获取与验收

DOI 或官方出版社文章页作为稳定入口；给定 PDF URL 仍是候选，必须检查主机来源及文件身份。HTTP 优先，浏览器获取按环境与请求选用。浏览器每次创建新的独立 UUID profile；`--profile-root` 仅指定容器目录，不复用用户既有登录或 Cookie。需要授权访问时，用户可在本次可见浏览器中手动登录；不承诺持久复用。未知或不合格来源不作为官方文件交付。

通过文件验收需具备 PDF 格式、可读页面和与目标文献一致的身份依据，并保留来源及校验信息。文件存在、下载事件、HTTP 200 和 CLI 退出状态都不能单独替代验收。

无权限、访问验证未完成、非 PDF、身份不明或不匹配时保留待处理状态与原因。不要持续重复硬重试，不改用第三方副本，不绕过访问控制；继续批次中能够明确处理的记录。

## 引用导出与隐私

默认仅导出 `metadata_status=verified` 且 `entity_type=publication` 的记录，未匹配的强标识符不进入正式引用字段。未核验、冲突、无法解析以及试验注册记录不静默作为已核验论文导出。报告实际导出数量、未导出原因，以及核验范围和局部缺口。导出不代表正式选引，不自动修改文献库或稿件。

结果文件、报告和日志不得包含 API key、认证头、Cookie、浏览器登录状态或签名 URL 参数。浏览器 profile、二进制、虚拟环境和论文 PDF 是本地运行材料，不属于公开源码包。
