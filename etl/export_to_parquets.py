import duckdb
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "warehouse" / "warehouse.duckdb"
EXPORT_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(DB_PATH))

tables = con.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'marts'
    ORDER BY table_name
""").fetchall()

for (name,) in tables:
    out_path = EXPORT_DIR / f"{name}.parquet"
    con.execute(f"COPY marts.{name} TO '{out_path}' (FORMAT PARQUET)")
    print(f"exported marts.{name} -> {out_path}")

con.close()