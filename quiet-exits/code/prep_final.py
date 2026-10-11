"""Final page data: quarterly forecast vs actual, exit-type forecast, typical patterns, examples."""
import json, pathlib, duckdb, numpy as np, pandas as pd, lightgbm as lgb

R = pathlib.Path(__file__).parent; OUT = R / "out"
con = duckdb.connect(str(OUT / "bank.duckdb"), read_only=True)
meta = json.load(open(OUT / "drift_meta.json")); FEAT = meta["features"]
drift_model = lgb.Booster(model_file=str(OUT / "drift_model.txt"))
fe = pd.read_parquet(OUT / "features.parquet"); fe["month"] = pd.to_datetime(fe.month)

# ---------- exit-type features for every account-month (same as the experiment)
mv = con.execute("SELECT * FROM monthly_view ORDER BY account_id, month").df(); mv["month"] = pd.to_datetime(mv.month)
mx = con.execute("""SELECT account_id, date_trunc('month', tx_date)::DATE AS month,
     MAX(CASE WHEN operation='WIC' THEN abs(amount) ELSE 0 END) AS max_cash,
     SUM(CASE WHEN category='LO' THEN abs(amount) ELSE 0 END) AS loan_pay FROM trans GROUP BY 1,2""").df()
mx["month"] = pd.to_datetime(mx.month)
mv = mv.merge(mx, on=["account_id", "month"], how="left").fillna({"max_cash": 0, "loan_pay": 0})
g = mv.groupby("account_id", sort=False)
fwd = lambda c: g[c].transform(lambda s: s[::-1].rolling(3).sum()[::-1].shift(-1))
back = lambda c, w=3: g[c].transform(lambda s: s.rolling(w, min_periods=w).sum())
mv["f_in"] = fwd("money_in"); mv["f_cashmax"] = g.max_cash.transform(lambda s: s[::-1].rolling(3).max()[::-1].shift(-1))
mv["b_in"] = back("money_in"); mv["b_cash"] = back("cash_out"); mv["b_out"] = back("money_out"); mv["b_in6"] = back("money_in", 6)
mv["b_cashmax"] = g.max_cash.transform(lambda s: s.rolling(3).max())
mv["peak"] = g.balance.transform(lambda s: s.rolling(12, min_periods=6).max())
mv["bal_trend"] = g.avg_balance.transform(lambda s: s.rolling(3).mean() / (s.shift(3).rolling(3).mean() + 1))
mv["tenure"] = g.cumcount()
d = fe.merge(mv[["account_id", "month", "f_in", "f_cashmax", "b_in", "b_cash", "b_out", "b_in6", "b_cashmax", "peak", "bal_trend",
                 "got_pension", "overdraft_charges", "loan_pay", "tenure"]], on=["account_id", "month"], how="left")
eps = 1
TF = pd.DataFrame({
    "log_bal": np.log10(d.past6), "bal_trend": d.bal_trend, "bal_vs_peak": d.balance / (d.peak + eps),
    "in_vs_bal": d.b_in / (d.past6 + eps), "in_change": d.b_in / (d.b_in6 - d.b_in + eps),
    "cash_share": d.b_cash.abs() / (d.b_out.abs() + eps), "max_cash_vs_bal": d.b_cashmax.abs() / (d.past6 + eps),
    "out_vs_in": d.b_out.abs() / (d.b_in + eps), "pension": (d.got_pension > 0).astype(int),
    "overdraft": d.overdraft_charges, "tenure": d.tenure, "loan_pay": (d.loan_pay > 0).astype(int)})
TYPES = ["Big one-off withdrawal", "Income stopped", "Gradual spending"]
def label(r):
    if r.b_in > 0 and r.f_in < 0.3 * r.b_in: return 1
    if abs(r.f_cashmax) > 0.4 * r.past6: return 0
    return 2
d["type"] = -1
dm = d.drift == 1
d.loc[dm, "type"] = [label(r) for r in d[dm].itertuples()]

tr = dm & (d.month >= "1994-01-01") & (d.month <= "1997-06-01")
type_model = lgb.train(dict(objective="multiclass", num_class=3, learning_rate=0.05, num_leaves=15, min_data_in_leaf=30,
                            feature_fraction=0.8, verbose=-1, seed=3), lgb.Dataset(TF[tr], d.type[tr]), 250)
d["p_drift"] = drift_model.predict(d[FEAT])
PT = type_model.predict(TF);
for k in range(3): d[f"pt{k}"] = PT[:, k]

# expected loss per drifting account, by type, learned on training years
d["dropf"] = (d.past6 - d.fut3) / d.past6
drop_by_type = {k: float(d[tr & (d.type == k)].dropf.mean()) for k in range(3)}
d["exp_loss"] = sum(d.p_drift * d[f"pt{k}"] * d.past6 * drop_by_type[k] for k in range(3))
for k in range(3): d[f"exp_loss{k}"] = d.p_drift * d[f"pt{k}"] * d.past6 * drop_by_type[k]

# calibrate on training quarter-ends
qe_train = pd.to_datetime(["1995-03-01", "1995-06-01", "1995-09-01", "1995-12-01", "1996-03-01", "1996-06-01", "1996-09-01", "1996-12-01", "1997-03-01", "1997-06-01"])
t = d[d.month.isin(qe_train)]
calib = float(t.lost_balance.sum() / t.exp_loss.sum())
# seasonal calibration: one factor per quarter-end month, learned only from earlier years
seas = {}
for mo in [3, 6, 9, 12]:
    tt = d[(d.month.dt.month == mo) & (d.month >= "1994-03-01") & (d.month <= "1997-06-01") & (d.month.dt.day == 1)]
    seas[mo] = float(tt.lost_balance.sum() / tt.exp_loss.sum())
print("seasonal factors", {k: round(v, 2) for k, v in seas.items()})
print("calibration factor", round(calib, 3), "drop by type", {TYPES[k]: round(v, 3) for k, v in drop_by_type.items()})

# ---------- quarterly backtest (out of time)
QE = pd.to_datetime(["1997-12-01", "1998-03-01", "1998-06-01", "1998-09-01"])
LBL = {"1997-12": "Q1 1998", "1998-03": "Q2 1998", "1998-06": "Q3 1998", "1998-09": "Q4 1998"}
quarters = []
for q in QE:
    s = d[d.month == q]
    act = s[s.drift == 1]
    cf = seas[q.month]
    quarters.append(dict(q=LBL[str(q.date())[:7]], made=str(q.date())[:7], forecast=round(float(s.exp_loss.sum() * cf)), plain=round(float(s.exp_loss.sum() * calib)),
                         actual=round(float(s.lost_balance.sum())), n=int(len(s)), drifters=int(s.drift.sum()),
                         f_type=[round(float(s[f"exp_loss{k}"].sum() * cf)) for k in range(3)],
                         a_type=[round(float(act[act.type == k].lost_balance.sum())) for k in range(3)]))
for q in quarters: print(q["q"], q["forecast"], q["actual"], q["f_type"], q["a_type"])

# ---------- where it's concentrated (Q4 1998 forecast)
s = d[d.month == "1998-09-01"].copy()
s["age_band"] = pd.cut(s.age, [0, 30, 45, 60, 120], labels=["Under 30", "30 to 44", "45 to 59", "60+"])
s["income"] = np.where(TF.loc[s.index, "pension"] == 1, "Pension", np.where(TF.loc[s.index, "in_vs_bal"] > 0.3, "Regular income", "Little income"))
def where(col):
    out = {}
    for k in range(3):
        grp = s.groupby(col, observed=True)[f"exp_loss{k}"].sum() * seas[9]
        out[TYPES[k]] = [dict(k=str(i), v=round(float(v))) for i, v in grp.sort_values(ascending=False).items()]
    return out
concentr = dict(age=where("age_band"), region=where("region"), income=where("income"))

# ---------- typical balance path per type (median, months -6..+3, as share of usual)
mvi = mv.set_index(["account_id", "month"]).avg_balance
paths = {}
ev = d[dm & (d.month >= "1994-06-01") & (d.month <= "1998-06-01")]
for k in range(3):
    e = ev[ev.type == k].sample(min(600, (ev.type == k).sum()), random_state=1)
    rows = []
    for r in e.itertuples():
        row = []
        for off in range(-6, 4):
            key = (r.account_id, r.month + pd.DateOffset(months=off))
            row.append(mvi.get(key, np.nan) / r.past6)
        rows.append(row)
    paths[TYPES[k]] = [round(float(np.nanmedian(np.array(rows)[:, i])), 3) for i in range(10)]
st = d[(d.drift == 0) & (d.month >= "1994-06-01") & (d.month <= "1998-06-01")].sample(800, random_state=2)
rows = [[mvi.get((r.account_id, r.month + pd.DateOffset(months=o)), np.nan) / r.past6 for o in range(-6, 4)] for r in st.itertuples()]
paths["Stayed"] = [round(float(np.nanmedian(np.array(rows)[:, i])), 3) for i in range(10)]

# ---------- early signs per type: median of signals before the exit vs accounts that stayed
sig = {}
base = TF[d.drift == 0].median()
for k in range(3):
    m = TF[dm & (d.type == k)].median()
    sig[TYPES[k]] = dict(in_change=float(m.in_change), base_in_change=float(base.in_change), max_cash=float(m.max_cash_vs_bal),
                         base_max_cash=float(base.max_cash_vs_bal), bal_trend=float(m.bal_trend), out_vs_in=float(m.out_vs_in),
                         base_out_vs_in=float(base.out_vs_in), bal_vs_peak=float(m.bal_vs_peak), base_bal_vs_peak=float(base.bal_vs_peak))

# ---------- examples: Q4 1998 accounts that drifted, one set per actual type
s2 = s[s.drift == 1].copy()
s2["pred_type"] = s2[["pt0", "pt1", "pt2"]].values.argmax(1)
examples = {}
for k in range(3):
    ex = s2[(s2.type == k)].sort_values("lost_balance", ascending=False).head(4)
    lst = []
    for r in ex.itertuples():
        h = mv[(mv.account_id == r.account_id) & (mv.month >= "1997-10-01") & (mv.month <= "1998-12-01")].avg_balance.round(-1).astype(int).tolist()
        lst.append(dict(id=int(r.account_id), age=int(r.age), g=r.gender, region=r.region, usual=round(r.past6), lost=round(r.lost_balance),
                        p=round(float(r.p_drift), 3), pt=[round(float(getattr(r, f"pt{j}")), 3) for j in range(3)], pred=int(r.pred_type), h=h))
    examples[TYPES[k]] = lst

res = json.load(open(OUT / "exit_type_results.json"))
data = dict(types=TYPES, quarters=quarters, calib=calib, seas=seas, concentr=concentr, paths=paths, signals=sig, examples=examples,
            type_acc=dict(acc=res["acc"], base=res["base"], per={t: dict(recall=res["report"][t]["recall"], precision=res["report"][t]["precision"]) for t in TYPES},
                          n_train=res["n_train"], n_test=res["n_test"]),
            share={t: res["share"].get(t, 0) for t in TYPES})
dd = json.load(open(OUT / "dashboard_data.json"))
data["model"] = dict(auc=dd["model"]["test"]["auc"], recall10=dd["model"]["test"]["recall_top10"], trans=dd["meta"]["stage1"]["trans"],
                     accounts=dd["meta"]["stage1"]["account"], fairness=dd["governance"]["fairness"])
(OUT / "final_data.json").write_text(json.dumps(data, separators=(",", ":"), default=float))
print("ok", (OUT / "final_data.json").stat().st_size)
print(json.dumps(sig, indent=0)[:600])
