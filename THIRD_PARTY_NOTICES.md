# Sources and licenses

The project combines existing academic-search implementations with a unified workflow and an official-PDF acquisition module. New integration code is MIT-licensed; the upstream copyright and permission notices below remain applicable to their respective material.

| Source | Pinned source | Copyright | Preserved license |
|---|---|---|---|
| paper-lookup in K-Dense-AI/scientific-agent-skills | Commit `0b2afe68a5f9379097ad815e028af664f1e222b7`, skill version 2.2 | 2025 K-Dense Inc. | [MIT](LICENSES/paper-lookup-MIT.txt) |
| wp-a/nature-academic-search | Commit `9e4496ff7fd52ee91fde84bf944d7f5ff6085315`, package 0.3.1 | 2026 wp-a | [MIT](LICENSES/nature-academic-search-MIT.txt) |

Upstream repositories: [Scientific Agent Skills](https://github.com/K-Dense-AI/scientific-agent-skills) and [nature-academic-search](https://github.com/wp-a/nature-academic-search).

The adapted Python code is under src/literature_workflow/_vendor/nature_academic_search/. The source manifest records individual file origins and changes. The upstream installer, MCP server, LLM relay, old CLI and embedded Skill are not included. The paper-lookup contribution is procedural source knowledge incorporated into the source guide and semantic-response checks; its full eighteen-source library is not presented as implemented here.

The PDF module reorganizes the publisher-source rules and validation policy of a local official-PDF workflow into new acquisition and identity-check functions. The original local CLI is not bundled. The earlier workflow used ScanSci PDF during development; this release neither vendors nor imports ScanSci or PyMuPDF. [ScanSci PDF](https://github.com/Rimagination/scansci-pdf) is acknowledged as a historical reference, with its [Apache-2.0 text](LICENSES/scansci-pdf-Apache-2.0.txt) retained. This history is not a claim that every element of the workflow was invented here.

Requests, pypdf, and the optional CloakBrowser wrapper are installed dependencies and retain their own licenses. CloakBrowser's browser binary has a [separate binary license](https://github.com/CloakHQ/CloakBrowser/blob/v0.4.10/BINARY-LICENSE.md); the project does not redistribute that binary.

Article PDFs, browser profiles, account credentials, cookies and runtime environments are not part of this repository. A source-code license does not grant redistribution rights for retrieved papers.

See [the contribution map](references/contribution-map.md) for the integration work and [the source manifest](references/source-manifest.json) for versioned provenance.
