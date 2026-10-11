"""
Stages 2-6: insight, model, governance checks, RM call list, proof.
Reads the Stage 1 monthly view from DuckDB, writes out/dashboard_data.json
and out/model.json (LightGBM trees for the in-browser what-if tool).
"""
import json, pathlib, duckdb, numpy as np, pandas as pd, lightgbm as lgb
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score, average_precision_score

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
con = duckdb.connect(str(OUT / "bank.duckdb"), read_only=True)
mv = con.execute("SELECT * FROM monthly_view ORDER BY account_id, month").df()
prof = con.execute("SELECT * FROM customer_profile").df()
mv["month"] = pd.to_datetime(mv["month"])

DRIFT_RATIO = 0.70      # next-3-month balance below 70% of 6-month average
MIN_BALANCE = 10_000    # CZK: ignore near-empty accounts
MIN_TENURE = 8          # months of history needed

# ---------------------------------------------------------------- features
g = mv.groupby("account_id", sort=False)
roll = lambda col, w: g[col].transform(lambda s: s.rolling(w, min_periods=w).sum())
rmean = lambda col, w: g[col].transform(lambda s: s.rolling(w, min_periods=w).mean())
mv["tenure_m"] = g.cumcount()
mv["past6"] = rmean("avg_balance", 6)
mv["past3"] = rmean("avg_balance", 3)
mv["prior3"] = g["avg_balance"].transform(lambda s: s.shift(3).rolling(3).mean())
mv["peak12"] = g["balance"].transform(lambda s: s.rolling(12, min_periods=6).max())
mv["fut3"] = g["avg_balance"].transform(lambda s: s[::-1].rolling(3).mean()[::-1].shift(-1))
for c in ["money_in", "money_out", "sent_other_bank", "cash_out", "received_other_bank", "n_tx"]:
    mv[c + "_3"] = roll(c, 3)
    mv[c + "_p3"] = g[c].transform(lambda s: s.shift(3).rolling(3).sum())
mv["overdraft_6"] = roll("overdraft_charges", 6)
mv["pension_6"] = g["got_pension"].transform(lambda s: s.rolling(6, min_periods=1).max())
mv["had_credit"] = (mv["money_in"] > 0).astype(int)
mv["last_credit_idx"] = mv["tenure_m"].where(mv["had_credit"] == 1)
mv["last_credit_idx"] = mv.groupby("account_id")["last_credit_idx"].ffill()
mv["months_since_credit"] = (mv["tenure_m"] - mv["last_credit_idx"]).fillna(99)

d = mv[(mv.tenure_m >= MIN_TENURE) & (mv.past6 >= MIN_BALANCE)].merge(prof, on="account_id", how="left")
eps = 1.0
d["age"] = (d["month"] - pd.to_datetime(d["birth_date"])).dt.days / 365.25
d["balance_trend"] = d["past3"] / (d["prior3"] + eps)
d["balance_vs_peak"] = d["balance"] / (d["peak12"] + eps)
d["net_flow_3"] = (d["money_in_3"] - d["money_out_3"]) / (d["past6"] + eps)
d["sent_other_share"] = d["sent_other_bank_3"] / (d["money_out_3"] + eps)
d["sent_other_change"] = (d["sent_other_bank_3"] - d["sent_other_bank_p3"]) / (d["past6"] + eps)
d["cash_share"] = d["cash_out_3"] / (d["money_out_3"] + eps)
d["income_change"] = d["money_in_3"] / (d["money_in_p3"] + eps)
d["regular_income"] = d["received_other_bank_3"] / (d["past6"] + eps)
d["activity_change"] = d["n_tx_3"] / (d["n_tx_p3"] + eps)
d["has_card"] = d["card_type"].notna() & (pd.to_datetime(d["card_issued"]) <= d["month"])
d["gold_card"] = d["has_card"] & (d["card_type"] == "G")
d["has_loan"] = d["loan_granted"].notna() & (pd.to_datetime(d["loan_granted"]) <= d["month"])
d["loan_in_trouble"] = d["has_loan"] & d["loan_status"].isin(["B", "D"])
d["joint_account"] = d["n_holders"] > 1
d["monthly_statements"] = d["statement_freq"] == "M"
for b in ["has_card", "gold_card", "has_loan", "loan_in_trouble", "joint_account", "monthly_statements"]:
    d[b] = d[b].astype(int)
d["log_balance"] = np.log10(d["past6"].clip(lower=1))
d["drift"] = (d["fut3"] < DRIFT_RATIO * d["past6"]).astype(int)
d["lost_balance"] = (d["past6"] - d["fut3"]).clip(lower=0) * d["drift"]

FEATURES = ["log_balance", "balance_trend", "balance_vs_peak", "net_flow_3", "sent_other_share",
            "sent_other_change", "cash_share", "income_change", "regular_income", "activity_change",
            "months_since_credit", "overdraft_6", "pension_6", "tenure_m", "has_card", "gold_card",
            "has_loan", "loan_in_trouble", "joint_account", "monthly_statements",
            "district_avg_salary", "unemployment_96", "urban_pct"]
LABELS = {  # plain-English names for staff
    "log_balance": "Usual balance size", "balance_trend": "Balance trend (last 3 vs previous 3 months)",
    "balance_vs_peak": "Balance vs its 12-month high", "net_flow_3": "Money in minus money out (3 months)",
    "sent_other_share": "Share of spending sent to other banks", "sent_other_change": "Rise in transfers to other banks",
    "cash_share": "Share taken out as cash", "income_change": "Income vs previous 3 months",
    "regular_income": "Regular income from another bank (salary-like)", "activity_change": "Activity vs previous 3 months",
    "months_since_credit": "Months since money last came in", "overdraft_6": "Overdraft charges (6 months)",
    "pension_6": "Receives a pension", "tenure_m": "Months as a customer", "has_card": "Has a card",
    "gold_card": "Has a gold card", "has_loan": "Has a loan", "loan_in_trouble": "Loan in arrears",
    "joint_account": "Joint account", "monthly_statements": "Monthly statements",
    "district_avg_salary": "Average salary in branch area", "unemployment_96": "Unemployment in branch area",
    "urban_pct": "How urban the branch area is"}

# ---------------------------------------------------------------- splits (out-of-time, like a bank would)
train = d[(d.month >= "1994-01-01") & (d.month <= "1997-06-01") & d.fut3.notna()]
test = d[(d.month >= "1997-10-01") & (d.month <= "1998-06-01") & d.fut3.notna()]
today = d[d.month == "1998-09-01"].copy()   # "today": outcome Oct-Dec 1998 is hidden from the model

params = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=80,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1, seed=7)
model = lgb.train(params, lgb.Dataset(train[FEATURES], train.drift), num_boost_round=350)
baseline = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)).fit(train[FEATURES], train.drift)

def evaluate(df):
    p = model.predict(df[FEATURES]); pb = baseline.predict_proba(df[FEATURES])[:, 1]
    y = df.drift.values; n = len(y); base = y.mean()
    order = np.argsort(-p); top = order[: max(1, n // 10)]
    return dict(n=int(n), drift_rate=float(base), auc=float(roc_auc_score(y, p)),
                pr_auc=float(average_precision_score(y, p)), auc_baseline=float(roc_auc_score(y, pb)),
                pr_auc_baseline=float(average_precision_score(y, pb)),
                precision_top10=float(y[top].mean()), lift_top10=float(y[top].mean() / base),
                recall_top10=float(y[top].sum() / y.sum())), p

m_train, _ = evaluate(train)
m_test, p_test = evaluate(test)
test = test.assign(p=p_test)
print("train", m_train); print("test", m_test)

# precision / recall by share of customers contacted (test)
curve = []
o = test.sort_values("p", ascending=False)
for pct in range(1, 51):
    k = int(len(o) * pct / 100); top = o.iloc[:k]
    curve.append(dict(pct=pct, precision=float(top.drift.mean()), recall=float(top.drift.sum() / o.drift.sum())))

# calibration (test)
test["bin"] = pd.qcut(test.p, 10, labels=False, duplicates="drop")
calib = test.groupby("bin").agg(pred=("p", "mean"), actual=("drift", "mean"), n=("p", "size")).reset_index().to_dict("records")

# confusion at the operating threshold = top 10% of scores
thr = float(np.quantile(test.p, 0.9))
tp = int(((test.p >= thr) & (test.drift == 1)).sum()); fp = int(((test.p >= thr) & (test.drift == 0)).sum())
fn = int(((test.p < thr) & (test.drift == 1)).sum()); tn = int(((test.p < thr) & (test.drift == 0)).sum())

# feature importance (mean |SHAP| on test)
contrib = model.predict(test[FEATURES], pred_contrib=True)
imp = np.abs(contrib[:, :-1]).mean(0)
importance = sorted([dict(f=f, label=LABELS[f], v=float(v)) for f, v in zip(FEATURES, imp)], key=lambda x: -x["v"])

# ---------------------------------------------------------------- governance: fairness (test, top 10% flagged)
test["flag"] = (test.p >= thr).astype(int)
test["age_band"] = pd.cut(test.age, [0, 30, 45, 60, 120], labels=["Under 30", "30 to 44", "45 to 59", "60+"])
test["gender_label"] = test.gender.map({"M": "Men", "F": "Women"})
def fair(col):
    rows = []
    for k, x in test.groupby(col, observed=True):
        rows.append(dict(group=str(k), n=int(len(x)), actual_drift=float(x.drift.mean()), flagged=float(x.flag.mean()),
                         caught=float(x[x.drift == 1].flag.mean()) if x.drift.sum() else None,
                         precision=float(x[x.flag == 1].drift.mean()) if x.flag.sum() else None))
    return rows
fairness = dict(gender=fair("gender_label"), age=fair("age_band"))

# monitoring: population stability index, train vs today
def psi(a, b, bins=10):
    q = np.unique(np.quantile(a, np.linspace(0, 1, bins + 1)))
    if len(q) < 3: return 0.0
    ea = np.histogram(np.clip(a, q[0], q[-1]), q)[0] / len(a); eb = np.histogram(np.clip(b, q[0], q[-1]), q)[0] / len(b)
    ea, eb = np.clip(ea, 1e-4, None), np.clip(eb, 1e-4, None)
    return float(((eb - ea) * np.log(eb / ea)).sum())
today["p"] = model.predict(today[FEATURES])
monitor = sorted([dict(f=f, label=LABELS[f], psi=psi(train[f].values, today[f].values)) for f in FEATURES], key=lambda x: -x["psi"])
score_psi = psi(model.predict(train[FEATURES]), today.p.values)

# ---------------------------------------------------------------- stage 2: insight
port = mv.groupby("month").agg(total_balance=("balance", "sum"), accounts=("account_id", "nunique")).reset_index()
rate = d[d.fut3.notna()].groupby("month").agg(rate=("drift", "mean"), lost=("lost_balance", "sum"), n=("drift", "size")).reset_index()
rate = rate[rate.month >= "1994-01-01"]
seg_df = d[d.fut3.notna() & (d.month >= "1994-01-01")].copy()
seg_df["age_band"] = pd.cut(seg_df.age, [0, 30, 45, 60, 120], labels=["Under 30", "30 to 44", "45 to 59", "60+"])
seg_df["balance_band"] = pd.cut(seg_df.past6, [0, 30000, 60000, 100000, 1e9], labels=["Under 30k", "30k to 60k", "60k to 100k", "100k+"])
seg_df["income_type"] = np.where(seg_df.pension_6 == 1, "Pension", np.where(seg_df.regular_income > 0.05, "Salary-like income", "No regular income"))
seg_df["products"] = np.select([seg_df.has_loan.eq(1) & seg_df.has_card.eq(1), seg_df.has_loan.eq(1), seg_df.has_card.eq(1)],
                               ["Loan + card", "Loan only", "Card only"], "Account only")
segments = {}
for col, title in [("age_band", "Age"), ("balance_band", "Usual balance (CZK)"), ("income_type", "Income type"), ("products", "Products held"), ("region", "Region")]:
    s = seg_df.groupby(col, observed=True).agg(rate=("drift", "mean"), n=("drift", "size"), lost=("lost_balance", "sum")).reset_index()
    segments[title] = [dict(k=str(r[col]), rate=float(r.rate), n=int(r.n), lost=float(r.lost)) for _, r in s.iterrows()]

# what happens before and after a drift (event study): median balance index, months -6..+3
ev = d[d.fut3.notna() & (d.month >= "1994-06-01") & (d.month <= "1998-06-01")][["account_id", "month", "drift", "past6"]]
ev = ev.sort_values(["account_id", "month"]).groupby("account_id").apply(lambda x: x.sample(1, random_state=1), include_groups=False).reset_index()
mvi = mv.set_index(["account_id", "month"])
traj = {0: [], 1: []}
for _, r in ev.iterrows():
    row = []
    for k in range(-6, 4):
        key = (r.account_id, r.month + pd.DateOffset(months=k))
        row.append(mvi.at[key, "avg_balance"] / r.past6 if key in mvi.index else np.nan)
    traj[int(r.drift)].append(row)
event = dict(months=list(range(-6, 4)),
             drift=[float(np.nanmedian(np.array(traj[1])[:, i])) for i in range(10)],
             stable=[float(np.nanmedian(np.array(traj[0])[:, i])) for i in range(10)],
             n_drift=len(traj[1]), n_stable=len(traj[0]))
# transfers to other banks before drift
other = {}
for lab, x in seg_df.groupby("drift"):
    other[int(lab)] = dict(sent_other_share=float(x.sent_other_share.median()), balance_trend=float(x.balance_trend.median()),
                           income_change=float(x.income_change.median()), activity_change=float(x.activity_change.median()))

# ---------------------------------------------------------------- stage 5: today's call list
drop_frac = float((train.loc[train.drift == 1, "lost_balance"] / train.loc[train.drift == 1, "past6"]).mean())
today["at_risk"] = today.p * today.past6 * drop_frac
tc = model.predict(today[FEATURES], pred_contrib=True)
base_logit = float(tc[0, -1])

def reason_text(f, val, c):
    up = c > 0
    t = {
        "balance_trend": f"Balance {'falling' if val < 1 else 'rising'}: last 3 months at {val*100:.0f}% of the 3 before",
        "balance_vs_peak": f"Balance now at {val*100:.0f}% of its 12-month high",
        "net_flow_3": f"{'More money going out than coming in' if val < 0 else 'More money coming in than going out'} over 3 months",
        "sent_other_share": f"{val*100:.0f}% of outgoing money sent to other banks",
        "sent_other_change": "Transfers to other banks rising" if val > 0 else "Transfers to other banks steady or falling",
        "cash_share": f"{val*100:.0f}% of outgoing money withdrawn as cash",
        "income_change": f"Income at {val*100:.0f}% of the previous 3 months",
        "regular_income": "Regular salary-like income from another bank" if val > 0.05 else "No regular salary-like income",
        "activity_change": f"Activity at {val*100:.0f}% of the previous 3 months",
        "months_since_credit": f"{int(val)} months since money last came in",
        "overdraft_6": f"{int(val)} overdraft charges in 6 months",
        "pension_6": "Receives a pension" if val else "No pension income",
        "tenure_m": f"Customer for {int(val)} months",
        "log_balance": f"Usual balance around {10**min(val, 9):,.0f} CZK",
        "has_loan": "Has a loan with us" if val else "No loan with us",
        "loan_in_trouble": "Loan in arrears" if val else "Loan in good standing",
        "has_card": "Holds a card" if val else "No card",
        "gold_card": "Gold card holder" if val else "No gold card",
        "joint_account": "Joint account" if val else "Single holder",
        "monthly_statements": "Monthly statements" if val else "Frequent statements",
        "district_avg_salary": f"Branch area average salary {val:,.0f} CZK",
        "unemployment_96": f"Branch area unemployment {val:.1f}%",
        "urban_pct": f"Branch area {val:.0f}% urban"}[f]
    return dict(text=t, up=bool(up), f=f)

def action_for(reasons):
    fs = [r["f"] for r in reasons if r["up"]]
    # stress first: a struggling customer needs care, not a sales call
    if "overdraft_6" in fs or "loan_in_trouble" in fs:
        return ("Signs of financial stress", "Handle with care. Offer a repayment review, not a sales pitch.")
    if "sent_other_share" in fs or "sent_other_change" in fs:
        return ("Money is moving to another bank", "Call to understand why. Offer a savings or investment product so the money stays with us.")
    if "income_change" in fs or "months_since_credit" in fs or "regular_income" in fs:
        return ("Income has slowed or moved", "Check in on a change in job or salary account. Offer to move salary crediting back.")
    if "cash_share" in fs:
        return ("Large cash withdrawals", "Possible big purchase. Offer a loan or instalment option instead of draining savings.")
    if "overdraft_6" in fs or "loan_in_trouble" in fs:
        return ("Signs of financial stress", "Handle with care. Offer a repayment review, not a sales pitch.")
    return ("Balance sliding", "Friendly check-in call. Ask about upcoming plans and review their products.")

calls = []
for i in np.argsort(-today.at_risk.values)[:300]:
    r = today.iloc[i]; c = tc[i, :-1]
    idx = np.argsort(-c)[:3]
    reasons = [reason_text(FEATURES[j], float(r[FEATURES[j]]), float(c[j])) for j in idx if c[j] > 0]
    title, act = action_for(reasons)
    calls.append(dict(id=int(r.account_id), p=float(r.p), at_risk=float(r.at_risk), balance=float(r.balance), usual=float(r.past6),
                      age=int(r.age), gender=r.gender, region=r.region, tenure=int(r.tenure_m), reasons=reasons,
                      signal=title, action=act, x=[float(r[f]) for f in FEATURES],
                      outcome=dict(drifted=int(r.drift) if not np.isnan(r.fut3) else None,
                                   next3=float(r.fut3) if not np.isnan(r.fut3) else None),
                      hist=[float(v) for v in mv[(mv.account_id == r.account_id) & (mv.month <= "1998-09-01")].tail(15).avg_balance],
                      after=[float(v) for v in mv[(mv.account_id == r.account_id) & (mv.month > "1998-09-01")].avg_balance]))

# ---------------------------------------------------------------- stage 6: backtest of the budget decision
bt = today[today.fut3.notna()].copy()
bt["lost"] = bt.lost_balance
order_model = bt.sort_values("at_risk", ascending=False)
rng = np.random.default_rng(3)
budget = []
for n in [50, 100, 150, 200, 300, 400, 500, 750, 1000]:
    mlost = order_model.head(n).lost.sum(); mdr = order_model.head(n).drift.sum()
    rl = [bt.sample(n, random_state=int(s)).lost.sum() for s in rng.integers(0, 10_000, 200)]
    budget.append(dict(n=n, model_lost=float(mlost), model_drifters=int(mdr), random_lost=float(np.mean(rl))))

stats1 = json.loads((OUT / "stage1_stats.json").read_text())
data = dict(
    meta=dict(currency="CZK", period="1993 to 1998", drift_ratio=DRIFT_RATIO, min_balance=MIN_BALANCE,
              today="September 1998", drop_frac=drop_frac, stage1=stats1,
              n_train=int(len(train)), n_test=int(len(test)), n_today=int(len(today)),
              train_window="Jan 1994 to Jun 1997", test_window="Oct 1997 to Jun 1998",
              total_drifters_today=int(bt.drift.sum()), total_lost_today=float(bt.lost.sum())),
    insight=dict(portfolio=[dict(m=str(r.month.date())[:7], bal=float(r.total_balance), n=int(r.accounts)) for _, r in port.iterrows()],
                 drift_rate=[dict(m=str(r.month.date())[:7], rate=float(r.rate), lost=float(r.lost)) for _, r in rate.iterrows()],
                 segments=segments, event=event, medians=other),
    model=dict(train=m_train, test=m_test, curve=curve, calibration=calib, importance=importance,
               confusion=dict(tp=tp, fp=fp, fn=fn, tn=tn, threshold=thr)),
    governance=dict(fairness=fairness, monitor=monitor[:10], score_psi=score_psi),
    calls=calls, budget=budget, features=FEATURES, labels=LABELS, base_logit=base_logit)
(OUT / "dashboard_data.json").write_text(json.dumps(data, default=float))
(OUT / "model.json").write_text(json.dumps(model.dump_model()))
print("drop_frac", drop_frac, "score_psi", score_psi)
print("budget", budget[:5])
print("fair", json.dumps(fairness, indent=0)[:800])
print("top imp", importance[:8])

# ---------------------------------------------------------------- export for the RM game
rows = []
for i in range(len(today)):
    r = today.iloc[i]; c = tc[i, :-1]
    idx = np.argsort(-c)[:3]
    reasons = [reason_text(FEATURES[j], float(r[FEATURES[j]]), float(c[j])) for j in idx if c[j] > 0]
    sig, act = action_for(reasons)
    rows.append(dict(id=int(r.account_id), p=float(r.p), at_risk=float(r.at_risk), usual=float(r.past6), balance=float(r.balance),
                     drift=None if np.isnan(r.fut3) else int(r.drift), lost=float(r.lost_balance) if not np.isnan(r.fut3) else 0.0,
                     next3=None if np.isnan(r.fut3) else float(r.fut3), signal=sig, age=int(r.age), gender=r.gender,
                     region=r.region, tenure=int(r.tenure_m), has_loan=int(r.has_loan), loan_trouble=int(r.loan_in_trouble),
                     pension=int(r.pension_6), overdraft=int(r.overdraft_6), income_change=float(r.income_change),
                     regular_income=float(r.regular_income), reasons=reasons, x=[float(r[f]) for f in FEATURES]))
(OUT / "today_all.json").write_text(json.dumps(rows))
print("today rows", len(rows))
