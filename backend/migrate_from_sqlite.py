"""Copy an Accounts.ai SQLite database (the old data/accounts.db) into the PostgreSQL database in DATABASE_URL.

    python migrate_from_sqlite.py                      # data/accounts.db next to this file
    python migrate_from_sqlite.py path/to/accounts.db  # another copy (e.g. on the server)

Run it once, with the backend stopped, into an empty database: it refuses a database that already holds data. It keeps
every id (uploads, sets, vouchers, ledgers...) and every uploaded sheet's row numbers (an imported bill names its row,
"import:ds1_sheet1:111"), moves the Supabase copies still waiting on disk into the database, sets every counter past
the copied ids, and checks the copy: row counts, every sheet's row numbers, and the books' rupee and gold totals.
The SQLite file is only read, never changed. Prints only the database host, never the address or the password.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import BigInteger, Column, Identity, MetaData, Table, create_engine, func, insert, select, text

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from app import config, database  # noqa: E402
from app import main as _main  # noqa: E402,F401  (registers every table: books, cloud copies, MongoDB queue)
from app.cloud import cloud_outbox  # noqa: E402

CHUNK = 1000


def fail(message: str) -> None:
    raise SystemExit(f"Not copied: {message}")


def sqlite_engine(path: Path):
    """The SQLite file, read-only (it is never changed)."""
    return create_engine(f"sqlite:///file:{path.as_posix()}?mode=ro&uri=true")


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "data" / "accounts.db"
    if not source.exists():
        fail(f"{source} does not exist.")
    problem = database.storage_problem()
    if problem:
        fail(problem)
    print(f"From {source}\nInto the database at {config.database_host()} (schema {config.DATABASE_SCHEMA})")

    old = sqlite_engine(source)
    with old.connect() as s:
        old_tables = set(s.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").scalars())
        old_columns = {t: {r[1] for r in s.exec_driver_sql(f"PRAGMA table_info({database.quote_ident(t)})")} for t in old_tables}
        sheet_tables = list(s.exec_driver_sql("SELECT table_name FROM dataset_sheets ORDER BY id").scalars()) \
            if "dataset_sheets" in old_tables else []
        high_water = dict(s.exec_driver_sql("SELECT name, value FROM id_high_water").all()) if "id_high_water" in old_tables else {}

    database.init_db()
    tables = [t for t in database.metadata.sorted_tables if t.name in old_tables]
    with database.engine.connect() as pg:
        filled = [t.name for t in database.metadata.sorted_tables if pg.execute(select(func.count()).select_from(t)).scalar()]
        existing_sheets = [t for t in sheet_tables if t in database.app_tables(pg)]
    if filled or existing_sheets:
        fail(f"the database already holds data ({', '.join(filled + existing_sheets)}). Copy only into an empty database.")

    copied: dict[str, int] = {}
    with old.connect() as s, database.engine.begin() as pg:
        # The books' and registry tables, parents before children, with their own ids.
        for table in tables:
            columns = [c for c in table.columns if c.name in old_columns[table.name]]
            result = s.execute(select(*columns))  # SQLAlchemy reads SQLite's dates, times and 0/1 as Python values
            count = 0
            while rows := result.mappings().fetchmany(CHUNK):
                pg.execute(insert(table), [dict(r) for r in rows])
                count += len(rows)
            copied[table.name] = count
        # Each uploaded sheet with its own row numbers (SQLite's rowid becomes "_rowid").
        for name in sheet_tables:
            if name not in old_tables:
                print(f"  sheet table {name} is missing from the SQLite file: skipped")
                continue
            frame = pd.read_sql_query(f'SELECT rowid AS "_rowid", * FROM {database.quote_ident(name)} ORDER BY rowid', s)
            columns = [c for c in frame.columns if c != database.ROWID]
            sheet = Table(name, MetaData(), Column(database.ROWID, BigInteger, Identity(always=False), primary_key=True),
                          *(Column(c, database._sheet_column_type(frame[c])) for c in columns))
            sheet.create(pg)
            if len(frame):
                quoted = ", ".join(database.quote_ident(c) for c in [database.ROWID, *columns])
                with pg.connection.driver_connection.cursor() as cur:
                    with cur.copy(f"COPY {database.quote_ident(name)} ({quoted}) FROM STDIN") as copy:
                        for row in frame.itertuples(index=False, name=None):
                            copy.write_row([database._cell(v) for v in row])
                pg.execute(text(f"SELECT setval(pg_get_serial_sequence(:t, :c), :v)"),
                           {"t": database.quote_ident(name), "c": database.ROWID, "v": int(frame[database.ROWID].max())})
            copied[name] = len(frame)
        # Supabase copies that were still waiting on disk (the old data/cloud_outbox folder).
        waiting = 0
        outbox = source.parent / "cloud_outbox"
        known = set(pg.execute(select(cloud_outbox.c.dataset_id)).scalars())
        if outbox.is_dir():
            ids = set(pg.execute(text("SELECT dataset_id FROM cloud_files WHERE status <> 'done'")).scalars())
            for file in outbox.iterdir():
                if file.is_file() and file.name.isdigit() and int(file.name) in ids and int(file.name) not in known:
                    pg.execute(insert(cloud_outbox).values(dataset_id=int(file.name), content=file.read_bytes()))
                    waiting += 1
        # Counters past every copied id: each table's own id sequence, and the upload / set numbers.
        for table in tables:
            pk = list(table.primary_key.columns)
            if len(pk) == 1 and pk[0].name == "id" and pk[0].autoincrement is not False:
                sequence = pg.execute(text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table.name}).scalar()
                highest = pg.execute(select(func.max(table.c.id))).scalar()
                if sequence and highest:
                    pg.execute(text("SELECT setval(:s, :v)"), {"s": sequence, "v": int(highest)})
        all_tables = database.app_tables(pg)
        database._raise_sequence(pg, "dataset_ids", max(int(high_water.get("datasets", 0)), database._highest_dataset_id(pg, all_tables)))
        database._raise_sequence(pg, "book_ids", max(int(high_water.get("books", 0)), database._highest_book_id(pg)))

    # The check: counts, row numbers, money and gold, compared with the SQLite file.
    problems = []
    with old.connect() as s, database.engine.connect() as pg:
        for table in tables:
            before = s.execute(select(func.count()).select_from(table)).scalar()
            after = pg.execute(select(func.count()).select_from(table)).scalar()
            if before != after:
                problems.append(f"{table.name}: {before} rows in SQLite, {after} copied")
        for name in sheet_tables:
            if name not in old_tables:
                continue
            before = list(s.exec_driver_sql(f"SELECT rowid FROM {database.quote_ident(name)} ORDER BY rowid").scalars())
            after = list(pg.exec_driver_sql(f'SELECT "_rowid" FROM {database.quote_ident(name)} ORDER BY "_rowid"').scalars())
            if before != after:
                problems.append(f"{name}: row numbers differ")
        for table, columns in (("voucher_lines", ("dr_paise", "cr_paise")), ("metal_lines", ("dr_mg", "cr_mg"))):
            if table in old_tables:
                sums = ", ".join(f"COALESCE(SUM({c}), 0)" for c in columns)
                before = tuple(int(v) for v in s.exec_driver_sql(f"SELECT {sums} FROM {table}").one())
                after = tuple(int(v) for v in pg.exec_driver_sql(f"SELECT {sums} FROM {table}").one())
                if before != after:
                    problems.append(f"{table} totals differ: {before} in SQLite, {after} copied")
    for name, count in copied.items():
        print(f"  {name}: {count}")
    print(f"  waiting Supabase copies moved from disk: {waiting}")
    if problems:
        raise SystemExit("CHECK FAILED:\n  " + "\n  ".join(problems))
    print("Checked: every table, every sheet's row numbers and the books' totals match the SQLite file.")


if __name__ == "__main__":
    main()
