# Validation

Acceptance contract: Selecting synthetic invoice100 includes exactly invoice100 and account1, excludes unrelated rows, and restores into an empty matching schema with no foreign-key violations. Composite keys, SQLite parent collation, cycles and BLOB/NUL-text round trips are tested; source bytes remain unchanged.

The behavior suite has 17 test methods; this includes meaningful malformed-input cases. CI executes unit tests, Python compilation, wheel build and a new-environment installed-console-command check on Linux/Python 3.10, 3.12 and 3.14. A configured workflow is not proof it passed: inspect this repository's current Actions run before making a health claim.

Preparation: all behavior tests passed on Python 3.12.14. Clean wheel/CLI evidence is recorded in `PREPARATION.json` after execution. Future security advisories, all possible inputs and Windows/macOS behavior are not certified by these checks. No performance benchmark or production-use evidence is claimed.
