"""Build the RM game data: three 'weeks' of 10 customers, each with a real story from their transactions."""
import json, pathlib, random, duckdb, numpy as np, pandas as pd

R = pathlib.Path(__file__).parent; OUT = R / "out"
con = duckdb.connect(str(OUT / "bank.duckdb"), read_only=True)
allc = json.loads((OUT / "today_all.json").read_text())
df = pd.DataFrame(allc)
df["rank"] = df.p.rank(ascending=False, method="first").astype(int)
known = df[df.drift.notna()]

random.seed(11)
NAMES_F = ["Jana", "Eva", "Petra", "Lucie", "Hana", "Marie", "Alena", "Tereza", "Martina", "Lenka", "Zuzana", "Katerina", "Veronika", "Ivana", "Monika"]
NAMES_M = ["Jan", "Petr", "Josef", "Pavel", "Martin", "Tomas", "Jiri", "Karel", "Milan", "Lukas", "Ondrej", "Michal", "Jakub", "David", "Vaclav"]

drifters = known[(known.drift == 1) & (known["rank"] <= 400)].sort_values("rank")
false_al = known[(known.drift == 0) & (known["rank"] <= 150)].sort_values("rank")
stable = known[(known.drift == 0) & (known["rank"] > 1500)]

def pick_drifters(n_week):
    # vary signals, include one stress case per week where possible
    out = []
    pool = drifters.sample(frac=1, random_state=n_week).to_dict("records")
    stress = [c for c in pool if c["signal"] == "Signs of financial stress"]
    if stress: out.append(stress[0])
    for c in pool:
        if len(out) >= 3: break
        if c["id"] in [o["id"] for o in out]: continue
        if c["signal"] in [o["signal"] for o in out] and len(pool) > 10: continue
        out.append(c)
    return out

used = set(); weeks = []
for w in range(3):
    d = [c for c in pick_drifters(w + 1) if c["id"] not in used][:3]
    while len(d) < 3:
        c = drifters[~drifters.id.isin(used | {x["id"] for x in d})].iloc[0].to_dict(); d.append(c)
    fa = false_al[~false_al.id.isin(used)].sample(1, random_state=w).to_dict("records")
    st = stable[~stable.id.isin(used)].sample(6, random_state=w).to_dict("records")
    book = d + fa + st
    used |= {c["id"] for c in book}
    random.shuffle(book)
    weeks.append(book)

ids = [c["id"] for wk in weeks for c in wk]
idlist = ",".join(map(str, ids))
mv = con.execute(f"SELECT account_id, month, avg_balance, received_other_bank, got_pension, overdraft_charges FROM monthly_view WHERE account_id IN ({idlist}) AND month BETWEEN DATE '1997-10-01' AND DATE '1998-12-01' ORDER BY 1,2").df()
cash = con.execute(f"""SELECT account_id, date_trunc('month', tx_date) AS m, MAX(amount) AS amt FROM trans
  WHERE account_id IN ({idlist}) AND operation='WIC' AND tx_date BETWEEN DATE '1998-06-01' AND DATE '1998-09-30' GROUP BY 1,2""").df()
since = con.execute(f"SELECT account_id, year(opened) AS y FROM account WHERE account_id IN ({idlist})").df().set_index("account_id").y.to_dict()
cards = con.execute(f"""SELECT d.account_id, c.card_type FROM card c JOIN disp d USING (disp_id) WHERE d.account_id IN ({idlist}) AND c.issued <= DATE '1998-09-30'""").df().set_index("account_id").card_type.to_dict()

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
def story(c):
    m = mv[mv.account_id == c["id"]].copy(); m["month"] = pd.to_datetime(m.month)
    past = m[m.month <= "1998-09-01"]; after = m[m.month > "1998-09-01"]
    facts = []
    ratio = past.avg_balance.iloc[-1] / c["usual"]
    if ratio < 0.8: facts.append(("down", f"Balance is down to {ratio*100:.0f}% of usual"))
    elif ratio > 1.15: facts.append(("up", f"Balance is up to {ratio*100:.0f}% of usual"))
    else: facts.append(("flat", "Balance is steady"))
    inc = past.set_index("month").received_other_bank
    if c["pension"]: facts.append(("pension", "A pension arrives every month"))
    elif (inc.iloc[-6:-2] > 0).sum() >= 3 and (inc.iloc[-2:] > 0).sum() == 0:
        last = inc[inc > 0].index.max()
        facts.append(("stop", f"Regular income stopped after {MON[last.month-1]}"))
    elif (inc.iloc[-6:] > 0).sum() >= 5: facts.append(("salary", "Salary-like income arrives every month"))
    F = json.loads((OUT / "dashboard_data.json").read_text())["features"]; x = dict(zip(F, c["x"]))
    if x["months_since_credit"] >= 2: facts.append(("stop", f"No money has come in for {int(x['months_since_credit'])} months"))
    elif x["income_change"] < 0.7: facts.append(("stop", f"Money coming in fell to {x['income_change']*100:.0f}% of the months before"))
    elif x["income_change"] > 1.4: facts.append(("up", "More money coming in than before"))
    if x["cash_share"] > 0.5: facts.append(("cash", f"{x['cash_share']*100:.0f}% of spending taken out as cash"))
    cc = cash[cash.account_id == c["id"]]
    if len(cc) and cc.amt.max() > 0.25 * c["usual"]:
        r = cc.loc[cc.amt.idxmax()]
        facts.append(("cash", f"Took out {r.amt:,.0f} CZK in cash in {MON[pd.Timestamp(r.m).month-1]}"))
    if c["loan_trouble"]: facts.append(("loan", "Loan repayments are behind"))
    elif c["has_loan"]: facts.append(("loanok", "Repaying a loan on time"))
    od = int(past.overdraft_charges.iloc[-6:].sum())
    if od: facts.append(("overdraft", f"Went overdrawn {od} time{'s' if od > 1 else ''} in 6 months"))
    ct = cards.get(c["id"])
    if ct: facts.append(("card", {"G": "Gold card holder", "C": "Classic card holder", "J": "Junior card holder"}[ct]))
    facts.append(("since", f"With the bank since {int(since[c['id']]) - 20 if since[c['id']] > 2000 else int(since[c['id']])}"))
    stress = bool(c["loan_trouble"] or od >= 2)
    return dict(hist=[round(v) for v in past.avg_balance.tail(12)], after=[round(v) for v in after.avg_balance],
                facts=facts[:4], stress=stress)

out_weeks = []
for wk in weeks:
    book = []
    for c in wk:
        s = story(c)
        pool = [n for n in (NAMES_F if c["gender"] == "F" else NAMES_M) if n not in [b["name"] for b in book]]
        name = random.choice(pool)
        book.append(dict(id=c["id"], name=name, age=c["age"], region=c["region"], p=round(c["p"], 4), rank=int(c["rank"]),
                         drift=int(c["drift"]), usual=round(c["usual"]), next3=round(c["next3"]), signal=c["signal"],
                         reasons=[r["text"] for r in c["reasons"]], **s))
    out_weeks.append(book)

order = df.sort_values("at_risk", ascending=False)
branch = dict(drift=[int(v) if v == v else 0 for v in order.drift], lost=[round(v) for v in order.lost],
              total_drifters=int(known.drift.sum()), total_lost=round(float(known.lost.sum())))
rng = np.random.default_rng(5); lost_arr = np.array(branch["lost"]); drift_arr = np.array(branch["drift"])
# expected random reach for any n = n/N of totals
(OUT / "rm_data.json").write_text(json.dumps(dict(weeks=out_weeks, branch=branch)))
for b in out_weeks[0]: print(b["name"], b["drift"], b["rank"], b["signal"], b["stress"], [f[1] for f in b["facts"]])
