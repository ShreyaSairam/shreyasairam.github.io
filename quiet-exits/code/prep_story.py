"""Data for the visual story: every customer, strategy curves, and three customers' month-by-month warning signs."""
import json, pathlib, duckdb, numpy as np, pandas as pd

R = pathlib.Path(__file__).parent; OUT = R / "out"
con = duckdb.connect(str(OUT / "bank.duckdb"), read_only=True)
df = pd.DataFrame(json.loads((OUT / "today_all.json").read_text()))
df = df[df.drift.notna()].reset_index(drop=True)
N = len(df)

# customers for the dot field (stable order, random-looking layout done in browser)
cust = [[round(r.usual), round(r.lost), int(r.drift), round(r.at_risk)] for r in df.itertuples()]

# strategy curves: drifting money reached and drifters reached for each number of calls
steps = list(range(0, 1001, 10))
def curve(order):
    lost = df.loc[order, "lost"].values; dr = df.loc[order, "drift"].values
    cl, cd = np.concatenate([[0], np.cumsum(lost)]), np.concatenate([[0], np.cumsum(dr)])
    return dict(money=[round(float(cl[s])) for s in steps], people=[int(cd[s]) for s in steps])
model = curve(df.sort_values("at_risk", ascending=False).index)
rich = curve(df.sort_values("usual", ascending=False).index)
tl, td = df.lost.sum(), df.drift.sum()
rand = dict(money=[round(float(tl * s / N)) for s in steps], people=[round(float(td * s / N), 1) for s in steps])
ranks = dict(model=df.at_risk.rank(ascending=False, method="first").astype(int).tolist(),
             rich=df.usual.rank(ascending=False, method="first").astype(int).tolist())

# three story customers: real drifters with visible warning signs
NAMES = {"F": ["Lucie", "Petra", "Hana", "Eva", "Tereza"], "M": ["Pavel", "Tomas", "Jan", "Martin", "Karel"]}
cands = []
for i, r in enumerate(df[df.drift == 1].sort_values("at_risk", ascending=False).head(160).itertuples()):
    cands.append(dict(id=r.id, name=NAMES[r.gender][(i // 2) % 5], age=r.age, region=r.region, usual=round(r.usual), next3=round(r.next3),
                      reasons=[x["text"] for x in r.reasons]))
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
stories = []
for c in cands:
    m = con.execute(f"""SELECT month, avg_balance, money_in, cash_out, overdraft_charges, received_other_bank
        FROM monthly_view WHERE account_id={c['id']} AND month BETWEEN DATE '1997-07-01' AND DATE '1998-12-01' ORDER BY month""").df()
    m["month"] = pd.to_datetime(m.month)
    usual = c["usual"]; ev = []
    base_in = m[m.month <= "1998-03-01"].money_in.tail(6).mean()
    seen = set()
    for i, r in m.iterrows():
        if r.month > pd.Timestamp("1998-09-01"): break
        lab = MON[r.month.month - 1] + " " + str(r.month.year)[2:]
        if r.month >= pd.Timestamp("1998-03-01"):
            if r.cash_out > 0.2 * usual and "cash" not in seen:
                ev.append(dict(i=int(i), t="cash", text=f"Took out {r.cash_out:,.0f} CZK in cash")); seen.add("cash")
            if base_in > 0 and r.money_in < 0.4 * base_in and "income" not in seen:
                ev.append(dict(i=int(i), t="income", text="Money coming in dropped")); seen.add("income")
            if r.avg_balance < 0.75 * usual and "low" not in seen and len(seen) >= 1:
                ev.append(dict(i=int(i), t="low", text="Balance dips below usual")); seen.add("low")
            if r.overdraft_charges > 0 and "od" not in seen:
                ev.append(dict(i=int(i), t="od", text="Went overdrawn")); seen.add("od")
    if len(ev) >= 2 and c["name"] not in [x["name"] for x in stories] and len({e["t"] for e in ev}) >= 2:
        stories.append(dict(name=c["name"], age=c["age"], region=c["region"], usual=usual, next3=c["next3"],
                            months=[MON[d.month - 1] + " " + str(d.year)[2:] for d in m.month],
                            bal=[round(v) for v in m.avg_balance], events=ev[:3], today=int((m.month <= "1998-09-01").sum() - 1),
                            reasons=c["reasons"]))


# pick three whose first warning sign came earliest, with different names
pool = sorted(stories, key=lambda st: (min(e["i"] for e in st["events"]), -len(st["events"])))
stories = []
for st in pool:
    if st["name"] in [x["name"] for x in stories]: continue
    stories.append(st)
    if len(stories) == 3: break
d = json.loads((OUT / "dashboard_data.json").read_text())
PLAIN = {"balance_vs_peak": "Balance well below its recent high", "cash_share": "Lots of cash withdrawals",
         "balance_trend": "Balance falling month after month", "net_flow_3": "More going out than coming in",
         "log_balance": "Size of the usual balance", "income_change": "Income dropping", "regular_income": "No regular salary",
         "activity_change": "Using the account less", "months_since_credit": "No money coming in", "tenure_m": "How long they've banked here"}
signs = [dict(label=PLAIN.get(x["f"], x["label"]), v=x["v"]) for x in d["model"]["importance"][:6]]

data = dict(n=N, cust=cust, steps=steps, model=model, rich=rich, rand=rand, ranks=ranks,
            total_lost=round(float(tl)), total_drifters=int(td), stories=stories, signs=signs,
            recall=d["model"]["test"]["recall_top10"], trans=d["meta"]["stage1"]["trans"])
(OUT / "story_data.json").write_text(json.dumps(data, separators=(",", ":")))
i300 = steps.index(300)
print(N, td, round(tl), "at 300 calls: model", model["money"][i300], model["people"][i300], "rich", rich["money"][i300], rich["people"][i300], "rand", rand["money"][i300])
for s in stories: print(s["name"], [e["text"] + "@" + s["months"][e["i"]] for e in s["events"]])
