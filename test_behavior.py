import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from sqlite_fixture_closure import extract, make_example


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / 'source.db'

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, schema, statements=()):
        with sqlite3.connect(self.db) as c:
            c.executescript(schema)
            for sql, params in statements:
                c.execute(sql, params)

    def test_parent_closure_excludes_unrelated_children(self):
        make_example(self.root / 'demo')
        r = extract(self.root / 'demo/source.db', 'invoice', [[100]])
        self.assertEqual(r['selected_rows'], 2)
        self.assertEqual({t['name']:len(t['rows']) for t in r['tables']}, {'account':1,'invoice':1})
        self.assertIn('foreign_key', [x['kind'] for x in r['inclusion']])

    def test_generated_sql_restores_into_empty_matching_schema(self):
        make_example(self.root / 'demo')
        r = extract(self.root / 'demo/source.db', 'invoice', [[100]])
        with sqlite3.connect(self.root / 'restored.db') as c:
            c.execute('PRAGMA foreign_keys=ON')
            c.executescript((self.root / 'demo/schema.sql').read_text())
            c.executescript(r['insert_sql'])
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(c.execute('SELECT id FROM invoice').fetchall(), [(100,)])

    def test_composite_parent_key_and_partial_null(self):
        self.build('CREATE TABLE p(a TEXT,b INTEGER,PRIMARY KEY(a,b)); CREATE TABLE c(id INTEGER PRIMARY KEY,a TEXT,b INTEGER,FOREIGN KEY(a,b) REFERENCES p(a,b));',
                   [('INSERT INTO p VALUES(?,?)',('x',2)),('INSERT INTO c VALUES(?,?,?)',(1,'x',2)),('INSERT INTO c VALUES(?,?,?)',(2,'absent',None))])
        self.assertEqual(extract(self.db,'c',[[1]])['selected_rows'],2)
        self.assertEqual(extract(self.db,'c',[[2]])['selected_rows'],1)

    def test_parent_collation_and_affinity_use_sqlite_comparison(self):
        self.build('CREATE TABLE p(id TEXT PRIMARY KEY COLLATE NOCASE);CREATE TABLE c(id INTEGER PRIMARY KEY,p TEXT REFERENCES p);',
                   [('INSERT INTO p VALUES(?)',('Alice',)),('INSERT INTO c VALUES(?,?)',(1,'alice'))])
        r=extract(self.db,'c',[[1]])
        self.assertEqual(next(t for t in r['tables'] if t['name']=='p')['rows'],[['Alice']])

    def test_cycle_terminates_and_deferred_sql_restores(self):
        schema='CREATE TABLE a(id INTEGER PRIMARY KEY,b INTEGER REFERENCES b(id));CREATE TABLE b(id INTEGER PRIMARY KEY,a INTEGER REFERENCES a(id));'
        self.build(schema,[('INSERT INTO a VALUES(?,?)',(1,2)),('INSERT INTO b VALUES(?,?)',(2,1))])
        r=extract(self.db,'a',[[1]])
        self.assertEqual(r['selected_rows'],2)
        with sqlite3.connect(':memory:') as c:
            c.execute('PRAGMA foreign_keys=ON');c.executescript(schema);c.executescript(r['insert_sql'])
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_diamond_and_duplicate_roots_deduplicate_rows(self):
        self.build('CREATE TABLE p(id INTEGER PRIMARY KEY);CREATE TABLE c(id INTEGER PRIMARY KEY,p INTEGER REFERENCES p);',
                   [('INSERT INTO p VALUES(?)',(1,)),('INSERT INTO c VALUES(?,?)',(10,1)),('INSERT INTO c VALUES(?,?)',(20,1))])
        self.assertEqual(extract(self.db,'c',[[10],[20],[10]])['selected_rows'],3)

    def test_blob_null_and_embedded_nul_text_roundtrip(self):
        schema='CREATE TABLE t(id INTEGER PRIMARY KEY,b BLOB,s TEXT,n TEXT,r REAL);'
        self.build(schema,[('INSERT INTO t VALUES(?,?,?,?,?)',(1,b'\x00\xff',"a\0b'c",None,1.25))])
        r=extract(self.db,'t',[[1]])
        with sqlite3.connect(':memory:') as c:
            c.executescript(schema);c.executescript(r['insert_sql'])
            self.assertEqual(c.execute('SELECT * FROM t').fetchone(),(1,b'\x00\xff',"a\0b'c",None,1.25))

    def test_quoted_table_and_column_names(self):
        self.build('CREATE TABLE "odd""table"("id""x" INTEGER PRIMARY KEY);', [('INSERT INTO "odd""table" VALUES(?)',(1,))])
        self.assertEqual(extract(self.db,'odd"table',[[1]])['selected_rows'],1)

    def test_missing_root_or_parent_refuses_partial(self):
        self.build('CREATE TABLE p(id INTEGER PRIMARY KEY);CREATE TABLE c(id INTEGER PRIMARY KEY,p INTEGER REFERENCES p);', [('INSERT INTO c VALUES(?,?)',(1,9))])
        for table,keys in [('c',[[1]]),('c',[[9]]),('absent',[[1]])]:
            with self.subTest(table=table,keys=keys),self.assertRaises(ValueError):extract(self.db,table,keys)

    def test_non_primary_target_refused_explicitly(self):
        self.build('CREATE TABLE p(id INTEGER PRIMARY KEY,u TEXT UNIQUE);CREATE TABLE c(id INTEGER PRIMARY KEY,p TEXT REFERENCES p(u));', [('INSERT INTO p VALUES(?,?)',(1,'x')),('INSERT INTO c VALUES(?,?)',(1,'x'))])
        with self.assertRaisesRegex(ValueError,'primary key'):extract(self.db,'c',[[1]])

    def test_generated_columns_refused(self):
        self.build('CREATE TABLE t(id INTEGER PRIMARY KEY,x INTEGER GENERATED ALWAYS AS(id*2));', [('INSERT INTO t(id) VALUES(?)',(1,))])
        with self.assertRaisesRegex(ValueError,'generated'):extract(self.db,'t',[[1]])

    def test_no_primary_key_and_null_primary_key_refused(self):
        self.build('CREATE TABLE t(x TEXT);CREATE TABLE p(id TEXT PRIMARY KEY);', [('INSERT INTO t VALUES(?)',('x',)),('INSERT INTO p VALUES(?)',(None,))])
        with self.assertRaises(ValueError):extract(self.db,'t',[['x']])
        with self.assertRaises(ValueError):extract(self.db,'p',[[None]])

    def test_without_rowid_composite_primary_key(self):
        self.build('CREATE TABLE t(a TEXT,b TEXT,PRIMARY KEY(a,b)) WITHOUT ROWID;', [('INSERT INTO t VALUES(?,?)',('x','y'))])
        self.assertEqual(extract(self.db,'t',[['x','y']])['selected_rows'],1)

    def test_key_shapes_and_row_budget(self):
        self.build('CREATE TABLE t(id INTEGER PRIMARY KEY);', [('INSERT INTO t VALUES(?)',(1,)),('INSERT INTO t VALUES(?)',(2,))])
        for keys in [[],[1],[[True]],[[None]],[[{}]],[[1,2]],[[2**70]]]:
            with self.subTest(keys=keys),self.assertRaises(ValueError):extract(self.db,'t',keys)
        with self.assertRaisesRegex(ValueError,'budget'):extract(self.db,'t',[[1],[2]],1)

    def test_source_bytes_unchanged(self):
        make_example(self.root/'demo');p=self.root/'demo/source.db'
        before=hashlib.sha256(p.read_bytes()).hexdigest();extract(p,'invoice',[[100]])
        self.assertEqual(before,hashlib.sha256(p.read_bytes()).hexdigest())

    def test_example_refuses_overwrite(self):
        make_example(self.root/'demo')
        with self.assertRaises(FileExistsError):make_example(self.root/'demo')

    def test_missing_database_does_not_get_created(self):
        with self.assertRaises(ValueError):extract(self.db,'t',[[1]])
        self.assertFalse(self.db.exists())


if __name__=='__main__':unittest.main()
