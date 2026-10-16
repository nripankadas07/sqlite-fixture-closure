"""Read-only SQLite parent closure with row-level inclusion evidence and INSERT SQL."""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import defaultdict, deque
from pathlib import Path

MAX_BYTES = 16 * 1024 * 1024


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"
    if isinstance(value, str):
        if "\0" in value:
            return "CAST(X'" + value.encode("utf-8").hex() + "' AS TEXT)"
        return "'" + value.replace("'", "''") + "'"
    if type(value) in (int, float) and (type(value) is int or math.isfinite(value)):
        return repr(value)
    raise ValueError("unsupported SQLite value")


def json_value(value):
    return {"blob_hex": value.hex()} if isinstance(value, bytes) else value


def extract(path, root_table, keys, max_rows=10000):
    source = Path(path).resolve()
    if not source.is_file() or source.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("source must be an existing SQLite file of at most 64 MiB")
    if not isinstance(root_table, str) or not 1 <= len(root_table) <= 256:
        raise ValueError("invalid root table")
    if type(max_rows) is not int or not 1 <= max_rows <= 10000:
        raise ValueError("row budget must be in 1..10000")
    if not isinstance(keys, list) or not 1 <= len(keys) <= 256:
        raise ValueError("keys must be 1..256 primary-key tuples")
    for key in keys:
        if not isinstance(key, list) or not 1 <= len(key) <= 32:
            raise ValueError("each primary key must be an array of 1..32 scalars")
        for value in key:
            if type(value) not in (str, int, float) or isinstance(value, float) and not math.isfinite(value):
                raise ValueError("root keys accept finite numbers and strings only")
            if isinstance(value, str) and len(value) > 65536:
                raise ValueError("root key string too large")
            if type(value) is int and not -(2**63) <= value < 2**63:
                raise ValueError("root integer key outside signed64")
    con = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=2)
    try:
        con.execute("PRAGMA query_only=ON")
        con.execute("PRAGMA trusted_schema=OFF")
        if hasattr(con, "setlimit"):
            con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_BYTES)
        ticks = [0]

        def progress():
            ticks[0] += 1
            return ticks[0] > 10000

        con.set_progress_handler(progress, 1000)
        con.execute("BEGIN")
        schema = dict(con.execute("SELECT name,sql FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        if len(schema) > 100:
            raise ValueError("at most 100 user tables")
        actual = {name.lower(): name for name in schema}
        if root_table.lower() not in actual:
            raise ValueError("root must name an ordinary table in main")
        metadata = {}

        def info(table):
            table = actual.get(table.lower(), table)
            if table not in schema or not schema[table] or schema[table].lstrip().upper().startswith("CREATE VIRTUAL"):
                raise ValueError("only ordinary main tables are supported")
            if table in metadata:
                return metadata[table]
            columns = list(con.execute("PRAGMA table_xinfo(" + quote(table) + ")"))
            if not 1 <= len(columns) <= 256 or any(c[6] for c in columns):
                raise ValueError("generated/hidden columns or excessive columns are unsupported")
            pk = [c[1] for c in sorted(columns, key=lambda c: c[5]) if c[5]]
            if not 1 <= len(pk) <= 32:
                raise ValueError("each reached table needs an explicit primary key")
            fk_groups = defaultdict(list)
            for row in con.execute("PRAGMA foreign_key_list(" + quote(table) + ")"):
                fk_groups[row[0]].append(row)
            if len(fk_groups) > 64:
                raise ValueError("at most 64 foreign keys per reached table")
            value = {"table": table, "columns": [c[1] for c in columns], "pk": pk,
                     "foreign_keys": [(k, sorted(v, key=lambda r: r[1])) for k, v in sorted(fk_groups.items())]}
            metadata[table] = value
            return value

        def find(meta, cols, values):
            if len(cols) != len(values):
                raise ValueError("key arity does not match primary key")
            sql = "SELECT " + ",".join(map(quote, meta["columns"])) + " FROM " + quote(meta["table"])
            sql += " WHERE " + " AND ".join(quote(c) + " = ?" for c in cols) + " LIMIT 2"
            result = con.execute(sql, values).fetchall()
            if len(result) != 1:
                raise ValueError("selected root or required parent missing/nonunique: " + meta["table"])
            return dict(zip(meta["columns"], result[0]))

        root = info(actual[root_table.lower()])
        queue = deque((root["table"], key, {"kind": "root", "key_index": i})
                      for i, key in enumerate(keys))
        selected = {}
        reasons = []
        size = 0
        while queue:
            table, key_values, reason = queue.popleft()
            meta = info(table)
            row = find(meta, meta["pk"], key_values)
            primary = tuple(row[c] for c in meta["pk"])
            if any(v is None for v in primary):
                raise ValueError("NULL primary key in a selected row is unsupported")
            token = table, primary
            reasons.append({"table": table, "primary_key": [json_value(v) for v in primary], **reason})
            if len(reasons) > 50000:
                raise ValueError("inclusion evidence exceeds 50000 edges")
            if token in selected:
                continue
            if len(selected) >= max_rows:
                raise ValueError("selected-row budget exceeded; no partial fixture emitted")
            encoded = [literal(row[c]) for c in meta["columns"]]
            size += sum(len(x.encode("utf-8")) for x in encoded)
            if size > MAX_BYTES:
                raise ValueError("selected data exceeds 16 MiB output budget")
            selected[token] = row
            for fk_id, group in meta["foreign_keys"]:
                parent_name = group[0][2]
                if parent_name.lower() not in actual:
                    raise ValueError("foreign key parent table is absent")
                parent = info(actual[parent_name.lower()])
                child_lookup = {c.lower(): c for c in meta["columns"]}
                values = [row[child_lookup[g[3].lower()]] for g in group]
                if any(v is None for v in values):
                    continue  # SQLite MATCH SIMPLE exempts any partially-null child key.
                target = [g[4] for g in group]
                if all(v is None for v in target):
                    target = parent["pk"]
                if len(target) != len(parent["pk"]) or any(v is None for v in target) or [v.lower() for v in target] != [v.lower() for v in parent["pk"]]:
                    raise ValueError("foreign keys must target the complete parent primary key in declared order")
                queue.append((parent["table"], values, {"kind": "foreign_key", "from_table": table,
                                                          "from_primary_key": [json_value(v) for v in primary], "foreign_key_id": fk_id}))
        ordered = sorted(selected, key=lambda x: (x[0], json.dumps([json_value(v) for v in x[1]], sort_keys=True)))
        tables = []
        statements = ["BEGIN;", "PRAGMA defer_foreign_keys=ON;"]
        for table in sorted({x[0] for x in ordered}):
            meta = info(table)
            data = []
            for token in (t for t in ordered if t[0] == table):
                row = selected[token]
                data.append([json_value(row[c]) for c in meta["columns"]])
                statements.append("INSERT INTO " + quote(table) + " (" + ",".join(map(quote, meta["columns"])) + ") VALUES (" +
                                  ",".join(literal(row[c]) for c in meta["columns"]) + ");")
            tables.append({"name": table, "columns": meta["columns"], "primary_key_columns": meta["pk"], "rows": data})
        statements.append("COMMIT;")
        return {"selected_rows": len(selected), "tables": tables, "inclusion": reasons,
                "insert_sql": "\n".join(statements) + "\n", "sqlite_version": sqlite3.sqlite_version,
                "scope": "Parent closure only. Apply INSERTs to an empty matching schema with foreign_keys=ON; no schema/triggers exported."}
    finally:
        con.close()


def make_example(directory):
    target = Path(directory)
    target.mkdir()  # Refuse to overwrite any existing directory.
    ddl = "CREATE TABLE account(id INTEGER PRIMARY KEY,name TEXT);\nCREATE TABLE invoice(id INTEGER PRIMARY KEY,account_id INTEGER REFERENCES account(id),total TEXT);\n"
    (target / "schema.sql").write_text(ddl, encoding="utf-8")
    (target / "keys.json").write_text("[[100]]\n", encoding="utf-8")
    with sqlite3.connect(target / "source.db") as c:
        c.executescript(ddl)
        c.executemany("INSERT INTO account VALUES(?,?)", [(1, "Synthetic account"), (2, "Unrelated account")])
        c.executemany("INSERT INTO invoice VALUES(?,?,?)", [(100, 1, "12.50"), (200, 2, "99.00")])


def read_keys(path):
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d:
                raise ValueError("duplicate JSON key")
            d[k] = v
        return d
    with Path(path).open("rb") as f:
        raw = f.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("root keys exceed 1 MiB")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", nargs="?")
    p.add_argument("--table")
    p.add_argument("--keys", help="JSON file containing primary-key arrays")
    p.add_argument("--format", choices=("json", "sql"), default="json")
    p.add_argument("--max-rows", type=int, default=10000)
    p.add_argument("--make-example", metavar="NEW_DIRECTORY")
    a = p.parse_args()
    try:
        if a.make_example:
            if a.source or a.table or a.keys:
                raise ValueError("--make-example cannot be combined with a source/table/keys")
            make_example(a.make_example)
            print(json.dumps({"example_directory": a.make_example}))
            return 0
        if not (a.source and a.table and a.keys):
            raise ValueError("source, --table and --keys are required")
        report = extract(a.source, a.table, read_keys(a.keys), a.max_rows)
        print(report["insert_sql"] if a.format == "sql" else json.dumps(report, sort_keys=True, indent=2), end="" if a.format == "sql" else "\n")
        return 0
    except (ValueError, OSError, UnicodeError, sqlite3.Error, OverflowError, RecursionError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
