# sqlite-fixture-closure

Open a SQLite source read-only, follow declared parent primary-key foreign keys to a fixed point, and emit deterministic INSERTs with per-row inclusion evidence.

For: Developers reducing a local SQLite bug reproduction to selected rows and their required parents. Copying a few tables or rows naively can lose required parents, while exporting the whole source shares unrelated data and makes reproduction cumbersome.

## Quickstart

Python 3.10 or newer. No runtime packages or network requests. The initial wheel build needs setuptools from the normal Python package registry.

```sh
git clone https://github.com/nripankadas07/sqlite-fixture-closure.git
cd sqlite-fixture-closure
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/sqlite-fixture-closure --make-example example-work
.venv/bin/sqlite-fixture-closure example-work/source.db --table invoice --keys example-work/keys.json
```

The synthetic example selects exactly two rows: invoice100 and its required account1. The report contains INSERT SQL and root/foreign-key inclusion reasons.

Windows: use `.venv\Scripts\python.exe` and `.venv\Scripts\sqlite-fixture-closure.exe` instead. Windows is documented but has not been executed in this release's Linux CI.

## Input and result contract

Existing main SQLite file <=64 MiB; ordinary tables only, <=100 user tables, <=256 columns/table, explicit primary keys of 1..32 columns, <=64 foreign keys/reached table. Root key file is UTF-8 JSON, <=1 MiB, with 1..256 scalar primary-key tuples; no booleans/null/nonfinite values. Foreign keys must target the complete parent primary key in declared order; implicit primary-key targets and composite keys are supported. Parent equality uses SQLite collation/affinity. Any partially-null child key is exempt (MATCH SIMPLE). Selected NULL primary keys, missing parents, virtual/generated/hidden columns and non-PK targets are refused. Budget: <=10000 selected rows, <=16 MiB SQL-literal data, <=50000 inclusion edges, bounded SQLite progress callback. A read transaction keeps the observed source consistent.

Output is JSON on stdout. Exit 0 means complete/no findings; exit 1 means a valid report with missing coverage, prices, capacity, or capture findings, where applicable. SQLite extraction has no exit-1 state. Exit 2 means invalid input or an I/O failure, with an error on stderr and no partial report. `--help` describes command options. Inputs stay local; review output before sharing it.

## Limits

Parent closure only, not child closure, representative sampling, anonymization or a production-database access policy. INSERT SQL requires an empty matching schema with foreign_keys=ON; schema/views/triggers/extensions are not exported or run. Output preserves source row contents and may contain sensitive data: review locally before sharing. Arbitrary UNIQUE FK targets and generated/virtual tables are intentionally unsupported. No network, source writes or remote database support.

## Verify

```sh
python3 -m unittest -v test_behavior
python3 -m compileall -q .
python3 -m pip wheel --no-deps --wheel-dir dist .
python3 -m venv /tmp/sqlite-fixture-closure-check
/tmp/sqlite-fixture-closure-check/bin/python -m pip install --no-deps dist/*.whl
python3 verify_installed.py /tmp/sqlite-fixture-closure-check/bin/python
```

The installed-command check runs outside the checkout. See [validation](VALIDATION.md), [research and tradeoffs](RESEARCH.md), [contributing](CONTRIBUTING.md), [support](SUPPORT.md) and [security](SECURITY.md).

Original implementation and synthetic fixtures, developed with AI assistance and reviewed through executable checks. MIT license. No customer/adoption claims, copied competitor implementation, or performance-superiority claim.
