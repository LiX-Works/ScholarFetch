# Setup and dependencies

## Install the base functionality

Python 3.11 or later is required. Install from the downloaded repository's root using a separate Python environment:

```bash
python -m pip install .
literature-workflow doctor --mode all
```

The base dependencies are `requests>=2.31,<3` and `pypdf>=6,<7`, installed automatically with the package. The installed command is `literature-workflow`; from the source checkout, `python scripts/literature.py` accepts the same arguments.

`doctor` performs local diagnostics only and sends no network requests. It can check whether dependencies and configuration exist, but cannot establish that database requests or publisher downloads have succeeded. Use `--mode search` or `--mode download` to diagnose only the relevant stage. Actual command results determine workflow capability.

Batch input can use JSON, CSV, or text. RIS/BibTeX input currently extracts DOI-bearing records only; files without DOIs are rejected, and full format syntax is not imported. Supply ordinary citations or titles through a text file or `--citation`; ambiguous items remain pending. Choose a new or empty directory for `--output` on each run, and use a different directory when repeating a command; existing results are not overwritten. Use `--language zh` for Chinese reports.

## Install as an Agent Skill

Place the complete repository in a skill directory supported by your Agent, using the folder name `scholarfetch`. Keep `SKILL.md`, `scripts/`, `src/`, `references/`, and the license files.

The usual Codex location is `~/.codex/skills/scholarfetch/`. If a custom skill directory is configured, follow that configuration. After installing the Python dependencies from the Skill root, invoke it with `$scholarfetch`. Installing the Python package and placing the Skill are separate steps; package installation alone does not automatically register an Agent Skill or MCP server.

## Source configuration

The default search sources are `crossref,europe_pmc`. Use `--sources` to select `crossref`, `pubmed`, `arxiv`, `openalex`, `europe_pmc`, or `semantic_scholar`.

This implementation requires `PUBMED_EMAIL` for PubMed; when it is missing, the source is marked as not queried. `doctor` reports whether `PUBMED_EMAIL`, `NCBI_API_KEY`, `OPENALEX_API_KEY`, and `S2_API_KEY` exist without showing their values. Prepare email or API key settings for other sources according to diagnostic guidance and the selected sources' requirements. An existing adapter does not establish that credentials are unnecessary or access will succeed. See [source-guide.md](source-guide.md) for source selection.

Configure personal email addresses or keys only in local environment variables; do not write them into the repository, examples, result files, or shared reports. Missing configuration for one source does not invalidate existing results from other sources. Network restrictions, rate limits, and service status can also cause request failures.

## Optional browser acquisition

HTTP is the preferred acquisition path. When official pages require browser access, you can install:

```bash
python -m pip install ".[browser]"
```

This extra uses `cloakbrowser>=0.4.10,<0.5`. Prepare the browser binary separately using the [official CloakBrowser instructions](https://github.com/CloakHQ/CloakBrowser), and keep its cache local. Successful Python package installation does not replace a binary availability check. The browser binary has its own license and is not distributed by this repository.

Use `--no-browser` on download commands to explicitly use HTTP only. Browser acquisition creates a separate profile with a new UUID under the current run's `private_profiles/` directory by default. `--profile-root` specifies the parent directory for these separate profiles, not an existing profile, and does not reuse previous logins or cookies. When necessary, the user can log in manually in the current visible browser using existing authorized access. This project does not extract cookies from personal browsers or automatically transfer login state. Do not publish profiles or the entire run directory as public source code; select only checked artifacts when sharing results.

`--headless` runs without showing the browser; do not assume it can complete tasks requiring interactive login or manual access verification. Set the wait duration with `--wait`; the current command help defines the default.

## Agent behavior when dependencies are missing

First state the missing component's name, affected stage, and minimum preparation, then continue other stages that can run. For example:

- Missing `pypdf`: do not mark PDFs as accepted; retain resolution results and pending records.
- Missing `cloakbrowser` or its browser binary: continue search, verification, and HTTP acquisition, and report the browser stage as unavailable.
- Missing required source configuration: record the source gap and continue configured sources; do not describe missing configuration as "no relevant papers."
- Missing paper access rights: retain the official entry point and failure reason for the user to address, and continue other papers in the batch.

Do not describe component installation, existing configuration, or successful local diagnostics as successful live network execution. Do not enable paid services without authorization, export credentials, or present execution from an older local environment as execution of this project.
