"""
Extract: load all sheets from the raw xlsx export as-is into a DuckDB
'raw' schema. No transformation here — this mirrors landing a real
source extract untouched, so the pipeline is auditable end to end.
"""
import duckdb
import pandas as pd
from pathlib import Path

RAW_XLSX = Path(__file__).resolve().parents[1] / "data" / "raw" / "dataset.xlsx"
DB_PATH = Path(__file__).resolve().parents[1] / "warehouse" / "warehouse.duckdb"


def extract():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    xl = pd.ExcelFile(RAW_XLSX)
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        table_name = f"raw.{sheet.lower()}"
        con.execute(f"DROP TABLE IF EXISTS {table_name}")
        con.register("tmp_df", df)
        con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")
        print(f"  loaded {table_name}  ({len(df)} rows)")

    con.close()
    print("Extract complete ->", DB_PATH)


if __name__ == "__main__":
    extract()
