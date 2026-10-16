# Architecture decision records

One file per significant decision about the pipeline, especially a decision
made to resolve a problem. Each record says what happened, which options we
weighed, what we chose and what it costs us. Then a reviewer, a new teammate
or a grader can see *why* the pipeline looks the way it does, not just what it
does.

| # | Decision | Status | Date |
|---|---|---|---|
| [0001](0001-gitleaks-scan-range.md) | Scope Gitleaks scans to the commits being built | Accepted | 2026-10-11 |

## Adding a record

1. Copy [TEMPLATE.md](TEMPLATE.md) to `NNNN-short-title.md`, using the next
   number.
2. Fill in every section. Link the issue, PR and runs as evidence.
3. Add a row to the table above.
4. Never rewrite an accepted record. If a later decision replaces it, write a
   new record and set the old one's status to "Superseded by NNNN".
