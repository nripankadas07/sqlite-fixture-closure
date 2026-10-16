# Research and scope — 16 October 2026

## Brief

User: Developers reducing a local SQLite bug reproduction to selected rows and their required parents.

Pain: Copying a few tables or rows naively can lose required parents, while exporting the whole source shares unrelated data and makes reproduction cumbersome.

Smallest useful capability: Open a SQLite source read-only, follow declared parent primary-key foreign keys to a fixed point, and emit deterministic INSERTs with per-row inclusion evidence.

Acceptance: Selecting synthetic invoice100 includes exactly invoice100 and account1, excludes unrelated rows, and restores into an empty matching schema with no foreign-key violations. Composite keys, SQLite parent collation, cycles and BLOB/NUL-text round trips are tested; source bytes remain unchanged.

Demand is inferred from the workflow and adjacent public discussions, not a verified request for this project. Discovery: precise GitHub topics, this runnable example and the chronological profile index; no unsolicited outreach or activity manipulation.

## Comparables

Live GitHub repository search, sort **Most stars**, query `database subsetting`. Highest-star relevant comparable found within this search scope: **Wisser/Jailer**. Search coverage is limited; this is not an exhaustive worldwide ranking. Broad queries returned unrelated products and were filtered by the actual user workflow.

| Repository | Stars observed | Last push observed (UTC) | Archived | API license classification |
| --- | ---: | --- | --- | --- |
| [Wisser/Jailer](https://github.com/Wisser/Jailer) | 3211 | 2026-10-15T11:12:20Z | False | Apache-2.0 |
| [TonicAI/condenser](https://github.com/TonicAI/condenser) | 337 | 2025-07-28T13:29:47Z | False | MIT |
| [18F/rdbms-subsetter](https://github.com/18F/rdbms-subsetter) | 310 | 2017-12-13T16:25:28Z | True | CC0-1.0 |

Exact observation times, README blob identities and up to five issue/PR references per comparable are in [research provenance](RESEARCH_PROVENANCE.json). NOASSERTION means the API did not classify the license; it is not permission to reuse. Stars are discovery evidence, not a measure of quality, performance or reliability.

Jailer already supports referentially intact subsetting and multiple export formats across JDBC databases, including SQLite. Condenser is a config-driven Postgres/MySQL tool, not a SQLite adapter. 18F rdbms-subsetter is archived (last push2017), so its maintenance is historical. Our fixed local SQLite primary-key closure is deliberately smaller, not a feature-absence or reliability-superiority claim.

Workflow alternatives: Jailer for broad relational browsing/subsetting; Condenser for Postgres/MySQL; archived rdbms-subsetter as historical Python precedent. msg555/subsetter and DBSubsetter were also inspected as low-star alternatives and are not presented as widely adopted.

Our install is a small Python wheel and two or fewer input steps, with a synthetic example and explicit failure states. Competitors offer broader interfaces, integrations, formats, documentation and support communities; their current READMEs/code and issue discussions were inspected, but their installations, reliability, support response and time to first useful result were not measured here. Our successful example establishes only our stated behavior. Licensing was recorded, not used as a proxy for capability.

Portfolio distinction: sqlite-rehearsal rehearses migrations and sqlite-plan-witness explains query plans. This extracts row-level parent closure and executable INSERT fixtures from a real SQLite file.

## Claims and reuse

No technical performance benchmark was conducted. There is no speed, memory, reliability or feature-absence superiority claim. Standard algorithms/formats are not inventions of this project. Source references were read for semantics and workflow comparison; implementation, prose and synthetic fixtures were written for this project. No third-party code, font assets or sample user data is bundled. No competitor logos/branding are reused.
