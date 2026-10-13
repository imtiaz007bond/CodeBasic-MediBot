import sqlite3
from pathlib import Path
p=Path(__file__).resolve().parents[2]/"data"/"mediassist.db"
with sqlite3.connect(p) as c:
 for (name,sql) in c.execute("select name,sql from sqlite_master where type='table'"):
  print(f"\n{name}:\n{sql}")
  print("rows:",c.execute(f"select count(*) from {name}").fetchone()[0])
