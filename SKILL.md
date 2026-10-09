---
name: literature-search-download
description: >-
  Search scholarly literature, resolve paper identifiers, verify bibliographic
  metadata, download and check PDFs from official publisher sources, and export
  verified candidate citations. Use for topic searches, DOI or citation checks,
  paper lists, and search-to-download requests. Does not edit Zotero or Word
  citations or decide which papers support manuscript claims.
---

# Literature Search and Download

统一处理主题检索、已有文献核验、官方 PDF 下载与候选引用导出。使用者提供主题、DOI、题名、引用或列表；根据请求运行必要阶段，无需强制准备 CSV 或拆成多轮任务。

<!-- Agent instruction: Before execution, check the executable and dependencies needed for the requested stages. When a dependency or tool is missing, tell the user its exact name, the affected stage, and the minimum preparation needed. Continue independent stages that remain available. Never invent execution or success, silently substitute an old local runtime, install paid services without authorization, or copy/export keys, cookies, or browser profiles. -->

## 执行前

从本 Skill 根目录使用 `python scripts/literature.py`，或安装后使用 `literature-workflow`；先执行 `doctor --mode all` 并确认所需命令的 `--help`。诊断只检查本地依赖与部分配置，不证明网络或浏览器二进制可用。依赖和安装方式见 [setup.md](references/setup.md)。不假设主机已安装旧版 Skill、MCP 或浏览器。

明确会影响结果的主题、年份、文献类型、预印本政策、规模和输出目录。中文主题先整理英文自由词；如需 MeSH，应另行查证适用于该生物医学问题的主题词，本 CLI 不提供 MeSH 核验命令。原始主题与实际查询分别保留，不把翻译后的检索式描述成已核验术语。

## 按需求路由

| 请求 | 运行阶段 | 交付重点 |
|---|---|---|
| 按主题找论文 | 检索 → 去重；需要时核验 | 候选、实际查询来源、来源失败与范围缺口 |
| 核验 DOI 或引用 | 身份解析 → 比较提供的预期字段 | 匹配依据、冲突、未核验字段 |
| 下载 DOI、官方链接或列表 | 解析与必要核验 → 官方获取 → PDF 检查 | 通过检查的文件、逐条状态、待处理项目 |
| 检索并下载 | 检索 → 核验 → 官方获取 → PDF 检查 | 保持候选与文件对应，同轮完成已获授权步骤 |
| 导出引用 | 读取核验结果 → 导出合格记录 | 导出数量、未导出原因，不自动导入文献库 |

对应命令为 `search`、`verify`、`download`、`search-download` 和 `export`。业务命令显式传入 `--output`，按需要设置 `--language zh|en`。详见 [工作流与结果契约](references/workflow-contract.md)。选择来源或遇到来源响应异常时，按需读取 [来源指南](references/source-guide.md)。默认查询 `crossref,europe_pmc`，不要因上游文档介绍多个数据库就声称本实现已接入全部来源。

## 核心规则

- 对实际查询、零结果、请求失败、未查询和检索范围受限分别说明。保留成功结果，隔离失败来源或歧义记录。
- 合并以强标识符及版本证据为依据；题名相似是线索。强标识符冲突不静默覆盖，预印本与出版版不混成同一身份。
- 单独 DOI 查找到记录仅证明解析结果；判断原引用是否正确还需比较使用者提供的预期字段。说明具体核验字段与无法核验的字段。
- 元数据匹配、PDF 身份检查、论断支持和人工选引分别报告。默认不判定论断支持、不替使用者决定最终引用。
- 自动下载仅接受可核实的官方出版社来源。传入 PDF URL 是候选入口，仍须查来源和文件身份；不回退到仓储或第三方副本。
- 对无权限、403、未解决的访问验证、非 PDF 或身份冲突记录待处理原因，不持续重复硬重试，不绕过访问控制。
- HTTP 200、下载事件、文件存在或命令退出成功不代表文件可交付。只有来源与 PDF 检查通过的文件进入最终论文目录。
- 遵循使用者指定输出目录，使用独立运行目录保留本次记录。日志和交换文件不含密钥、认证头、Cookie、浏览器凭据或签名 URL 参数。
- 不默认调用外部 LLM、中转服务或付费接口，不把私有正文发送到外部服务。准备依赖不代表获得新外部写操作或额外费用授权。

## 交付

先用使用者要求的语言说明得到什么、哪些步骤完成、哪些项目需要处理，再链接实际生成的结果。报告来源、访问日期、范围限制和验证依据；引用导出只是数据交换，不自动修改 Zotero、Word 或稿件。

请求示例见 [examples/requests.md](examples/requests.md)。
