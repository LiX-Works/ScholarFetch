# Integration and changes

| Area | Upstream basis | Work in this release |
|---|---|---|
| Retrieval and identity | Selected nature-academic-search 0.3.1 modules | One execution route, bounded queries, source success/failure/not-queried distinction, conservative citation resolution, explicit identity conflicts and version separation |
| Source behavior | paper-lookup's procedural knowledge | Source guide and checks for HTTP-200 semantic failures, arXiv version/error feeds, incomplete coverage and ambiguous records |
| Verification | Upstream identifier lookups and field comparisons | Declared verification scope, partial and unchecked fields, distinct input references, no automatic claim support or manuscript selection |
| Official acquisition | Local workflow source policy and publisher URL conventions | HTTP-first requests, validation before redirects, optional isolated browser acquisition, file/identity checks, quarantine and no-overwrite output |
| Authentication and privacy | Existing HTTP clients and local workflow practices | Explicit service configuration, no implicit personal .netrc authentication, signed URL/auth redaction across JSON, reports, RIS and BibTeX |
| User entry point | New integration | One CLI for search, verify, download, search-download, export and dependency diagnosis; missing components reported without fabricating success |

The release does not claim eighteen executable sources, unrestricted publisher access, exhaustive literature coverage or a newly built MCP. The supported routes and actual regression scope are documented in the README.
