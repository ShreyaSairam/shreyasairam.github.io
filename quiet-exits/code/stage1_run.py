"""Stage 1 runner: executes the SQL and saves the bank's monthly view."""
import duckdb, time, json, pathlib

ROOT = pathlib.Path(__file__).parent
con = duckdb.connect(str(ROOT / "out" / "bank.duckdb"))
t = time.time()
con.execute((ROOT / "sql" / "01_build_monthly_view.sql").read_text().replace("'data/", f"'{ROOT}/data/"))
stats = {}
for tbl in ["trans", "account", "client", "loan", "card", "district", "monthly_view", "customer_profile"]:
    stats[tbl] = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
stats["date_range"] = [str(x) for x in con.execute("SELECT MIN(tx_date), MAX(tx_date) FROM trans").fetchone()]
stats["seconds"] = round(time.time() - t, 1)
print(json.dumps(stats, indent=1))
(ROOT / "out" / "stage1_stats.json").write_text(json.dumps(stats, indent=1))
print(con.execute("SELECT * FROM monthly_view WHERE account_id=1 ORDER BY month LIMIT 5").df())
print(con.execute("SELECT * FROM customer_profile LIMIT 3").df().T)
