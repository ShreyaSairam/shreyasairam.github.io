"""Experiment: can we tell, 3 months early, HOW a customer's money will leave?
1. Label past drift events by the shape of the exit in the next 3 months.
2. Train a classifier on what the account looked like before.
3. Test on later months it never saw."""
import json, pathlib, duckdb, numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

R = pathlib.Path(__file__).parent; OUT = R / "out"
con = duckdb.connect(str(OUT / "bank.duckdb"), read_only=True)
mv = con.execute("SELECT * FROM monthly_view ORDER BY account_id, month").df(); mv["month"] = pd.to_datetime(mv.month)
mx = con.execute("""SELECT account_id, date_trunc('month', tx_date)::DATE AS month,
     MAX(CASE WHEN operation='WIC' THEN abs(amount) ELSE 0 END) AS max_cash,
     SUM(CASE WHEN operation='ROB' AND category NOT IN ('HH','IN','LO') THEN abs(amount) ELSE 0 END) AS rob_free,
     SUM(CASE WHEN category IN ('LO') THEN abs(amount) ELSE 0 END) AS loan_pay
   FROM trans GROUP BY 1,2""").df(); mx["month"] = pd.to_datetime(mx.month)
mv = mv.merge(mx, on=["account_id", "month"], how="left").fillna({"max_cash": 0, "rob_free": 0, "loan_pay": 0})
g = mv.groupby("account_id", sort=False)
fwd = lambda c: g[c].transform(lambda s: s[::-1].rolling(3).sum()[::-1].shift(-1))
back = lambda c, w=3: g[c].transform(lambda s: s.rolling(w, min_periods=w).sum())
mv["past6"] = g.avg_balance.transform(lambda s: s.rolling(6).mean())
mv["fut3"] = g.avg_balance.transform(lambda s: s[::-1].rolling(3).mean()[::-1].shift(-1))
mv["f_in"] = fwd("money_in"); mv["f_cashmax"] = g.max_cash.transform(lambda s: s[::-1].rolling(3).max()[::-1].shift(-1))
mv["f_rob"] = fwd("rob_free"); mv["f_out"] = fwd("money_out")
mv["b_in"] = back("money_in"); mv["b_rob"] = back("rob_free"); mv["b_cash"] = back("cash_out"); mv["b_out"] = back("money_out")
mv["b_cashmax"] = g.max_cash.transform(lambda s: s.rolling(3).max()); mv["b_in6"] = back("money_in", 6)
mv["tenure"] = g.cumcount()
mv["bal_trend"] = g.avg_balance.transform(lambda s: s.rolling(3).mean() / (s.shift(3).rolling(3).mean() + 1))
mv["peak"] = g.balance.transform(lambda s: s.rolling(12, min_periods=6).max())

d = mv[(mv.tenure >= 8) & (mv.past6 >= 10000) & mv.fut3.notna()].copy()
d = d[d.fut3 < 0.7 * d.past6]   # drift events only
lost = (d.past6 - d.fut3)
def label(r, lost):
    if r.b_in > 0 and r.f_in < 0.3 * r.b_in: return "Income stopped"
    if abs(r.f_cashmax) > 0.4 * r.past6: return "Big one-off withdrawal"
    return "Gradual spending"
d["exit"] = [label(r, l) for r, l in zip(d.itertuples(), lost)]
print("Exit types (all drift events):"); print(d.exit.value_counts(normalize=True).round(3))

eps = 1
F = pd.DataFrame({
    "log_bal": np.log10(d.past6), "bal_trend": d.bal_trend, "bal_vs_peak": d.balance / (d.peak + eps),
    "in_vs_bal": d.b_in / (d.past6 + eps), "in_change": d.b_in / (d.b_in6 - d.b_in + eps),
    "cash_share": d.b_cash.abs() / (d.b_out.abs() + eps), "max_cash_vs_bal": d.b_cashmax.abs() / (d.past6 + eps),
    "rob_share": d.b_rob.abs() / (d.b_out.abs() + eps), "out_vs_in": d.b_out.abs() / (d.b_in + eps),
    "pension": (d.got_pension > 0).astype(int), "overdraft": d.overdraft_charges, "tenure": d.tenure, "loan_pay": (d.loan_pay > 0).astype(int)})
classes = sorted(d.exit.unique()); y = d.exit.map({c: i for i, c in enumerate(classes)})
tr = (d.month >= "1994-01-01") & (d.month <= "1997-06-01"); te = (d.month >= "1997-10-01") & (d.month <= "1998-06-01")
m = lgb.train(dict(objective="multiclass", num_class=len(classes), learning_rate=0.05, num_leaves=15, min_data_in_leaf=30,
                   feature_fraction=0.8, verbose=-1, seed=3), lgb.Dataset(F[tr], y[tr]), 250)
pred = m.predict(F[te]).argmax(1)
base = y[tr].value_counts().idxmax()
print(f"\nTrain events {tr.sum()}, test events {te.sum()}")
print("Accuracy (test):", round(accuracy_score(y[te], pred), 3), " | always guessing the most common type:", round((y[te] == base).mean(), 3))
print(classification_report(y[te], pred, labels=list(range(len(classes))), target_names=classes, digits=2))
print("Confusion (rows = actual):"); print(pd.DataFrame(confusion_matrix(y[te], pred), index=classes, columns=classes))
imp = pd.Series(m.feature_importance("gain"), index=F.columns).sort_values(ascending=False); print("\nTop signals:", imp.head(6).round(0).to_dict())
json.dump(dict(classes=classes, share=d.exit.value_counts(normalize=True).round(4).to_dict(),
               acc=accuracy_score(y[te], pred), base=float((y[te] == base).mean()),
               report=classification_report(y[te], pred, labels=list(range(len(classes))), target_names=classes, output_dict=True),
               confusion=confusion_matrix(y[te], pred).tolist(), n_train=int(tr.sum()), n_test=int(te.sum())),
          open(OUT / "exit_type_results.json", "w"), default=float)
