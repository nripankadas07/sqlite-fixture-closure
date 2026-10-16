"""Exercise the installed wheel's actual console entry point outside this checkout."""
import hashlib, json, os, pathlib, shutil, sqlite3, subprocess, sys, tempfile

SOURCE=pathlib.Path(__file__).absolute().parent
PYTHON=pathlib.Path(sys.argv[1]).absolute()  # Do not resolve a venv symlink to its base interpreter.
COMMAND=PYTHON.parent / ("sqlite-fixture-closure.exe" if os.name=="nt" else "sqlite-fixture-closure")
CASES=0
def run(args, expected=0, data=True):
    global CASES
    p=subprocess.run([str(COMMAND), *map(str,args)],cwd=WORK,text=True,capture_output=True,timeout=30)
    assert p.returncode==expected, (args,p.returncode,p.stdout,p.stderr)
    CASES+=1
    if expected==2:
        assert not p.stdout and p.stderr, (args,p.stdout,p.stderr)
        return None
    return json.loads(p.stdout) if data else p.stdout

with tempfile.TemporaryDirectory(prefix="installed-command-") as tmp:
    WORK=pathlib.Path(tmp)
    assert not WORK.is_relative_to(SOURCE)
    env=subprocess.run([str(PYTHON),"-c","import sqlite_fixture_closure; print(sqlite_fixture_closure.__file__)"],cwd=WORK,text=True,capture_output=True,check=True)
    installed=pathlib.Path(env.stdout.strip()).absolute()
    assert not installed.is_relative_to(SOURCE), installed
    assert installed.read_bytes()==(SOURCE/"sqlite_fixture_closure.py").read_bytes()
    run(["--help"],data=False)
    run(["--make-example","fixture"])
    db=WORK/"fixture/source.db";digest=hashlib.sha256(db.read_bytes()).hexdigest()
    args=["fixture/source.db","--table","invoice","--keys","fixture/keys.json"]
    r=run(args);assert r["selected_rows"]==2
    sql=run(args+["--format","sql"],data=False)
    target=sqlite3.connect(WORK/"restored.db");target.execute("PRAGMA foreign_keys=ON")
    target.executescript((WORK/"fixture/schema.sql").read_text());target.executescript(sql)
    assert target.execute("PRAGMA foreign_key_check").fetchall()==[]
    assert target.execute("SELECT id FROM invoice").fetchall()==[(100,)]
    assert target.execute("SELECT id FROM account").fetchall()==[(1,)]
    target.close();assert hashlib.sha256(db.read_bytes()).hexdigest()==digest
    run(args+["--max-rows","1"],2)
    (WORK/"fixture/keys.json").write_text("[[999]]");run(args,2)
    (WORK/"fixture/keys.json").write_bytes(b"x"*(1024*1024+1));run(args,2)
    run(["--make-example","fixture"],2)
    run(["missing.db","--table","invoice","--keys","fixture/keys.json"],2);assert not (WORK/"missing.db").exists()
print(json.dumps({"installed_command":"sqlite-fixture-closure","cases":CASES,"module_bytes_match_source":True,"outside_checkout":True,"python":subprocess.check_output([str(PYTHON),"--version"],text=True).strip()}))
