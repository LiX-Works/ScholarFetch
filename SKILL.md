---
name: scholarfetch
description: >-
  Search scholarly literature, resolve paper identifiers, verify bibliographic
  metadata, download and check PDFs from official publisher sources, and export
  verified candidate citations. Use for topic searches, DOI or citation checks,
  paper lists, and search-to-download requests. Does not edit Zotero or Word
  citations or decide which papers support manuscript claims.
---

# ScholarFetch

**Academic Literature Search & PDF Download**

Handle topic searches, verification of existing references, official PDF downloads, and candidate citation exports in one workflow. The user can provide a topic, DOI, title, citation, or list; run the stages required by the request without requiring a CSV or splitting the task into multiple rounds.

<!-- Agent instruction: Before execution, check the executable and dependencies needed for the requested stages. When a dependency or tool is missing, tell the user its exact name, the affected stage, and the minimum preparation needed. Continue independent stages that remain available. Never invent execution or success, silently substitute an old local runtime, install paid services without authorization, or copy/export keys, cookies, or browser profiles. -->

## Before execution

Use `python scripts/literature.py` from this Skill's root directory, or `literature-workflow` after installation. First run `doctor --mode all` and check `--help` for the required commands. Diagnostics check only local dependencies and some configuration; they do not establish network access or browser binary availability. See [setup.md](references/setup.md) for dependencies and installation. Do not assume that an older Skill, MCP server, or browser is installed on the host.

Clarify the topic, years, document types, preprint policy, scale, and output directory where they affect the results. Convert Chinese topics into English free-text keywords first. If MeSH is needed, separately verify the subject headings appropriate to the biomedical question; this CLI does not provide a MeSH verification command. Retain the original topic and actual query separately, and do not describe a translated search expression as verified terminology.

## Route by request

| Request | Stages | Delivery focus |
|---|---|---|
| Find papers on a topic | Search → deduplicate; verify when needed | Candidates, sources actually queried, source failures, and coverage gaps |
| Verify a DOI or citation | Resolve identity → compare supplied expected fields | Matching evidence, conflicts, and unchecked fields |
| Download DOIs, official links, or a list | Resolve and verify as needed → acquire from official sources → check PDFs | Accepted files, per-item statuses, and pending items |
| Search and download | Search → verify → acquire from official sources → check PDFs | Keep candidates linked to files and complete authorized stages in the same round |
| Export citations | Read verification results → export eligible records | Export counts and omission reasons; no automatic import into a reference library |

The corresponding commands are `search`, `verify`, `download`, `search-download`, and `export`. Pass `--output` explicitly for workflow commands and set `--language zh|en` as needed. See the [workflow and output contract](references/workflow-contract.md). Read the [source guide](references/source-guide.md) as needed when choosing sources or handling abnormal source responses. The default sources are `crossref,europe_pmc`; do not claim that this implementation supports every source merely because upstream documentation describes multiple databases.

## Core rules

- Distinguish actual queries, valid zero results, request failures, sources not queried, and limited search scope. Retain successful results and isolate failed sources or ambiguous records.
- Merge using strong identifiers and version evidence; title similarity is a clue. Do not silently overwrite conflicting strong identifiers or merge preprints and published versions into one identity.
- Finding a record by DOI establishes only the resolution result. Checking whether the original citation is correct also requires comparison with the user's expected fields. State which fields were checked and which could not be checked.
- Report metadata matches, PDF identity checks, claim support, and manual citation selection separately. Do not assess claim support or decide the user's final citations by default.
- Automated downloads accept only verifiable official publisher sources. A supplied PDF URL is a candidate entry point whose provenance and file identity still require checks; do not fall back to repository or third-party copies.
- Record pending reasons for missing access rights, HTTP 403, unresolved access verification, non-PDF responses, or identity conflicts. Do not keep repeating aggressive retries or bypass access controls.
- HTTP 200, a download event, an existing file, or a successful command exit does not establish that a file is deliverable. Only files that pass provenance and PDF checks enter the final papers directory.
- Follow the user's output directory and retain this run's records in a separate run directory. Logs and exchange files must not contain keys, authorization headers, cookies, browser credentials, or signed URL parameters.
- Do not call external LLMs, relay services, or paid APIs by default, and do not send private full text to external services. Preparing dependencies does not authorize new external writes or additional costs.

## Delivery

First explain, in the user's requested language, what was obtained, which stages completed, and which items need attention; then link the results actually generated. Report sources, access dates, scope limits, and verification evidence. Citation export is data exchange only and does not automatically modify Zotero, Word, or a manuscript.

See [examples/requests.md](examples/requests.md) for request examples.
