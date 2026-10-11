"""Export both models + real starting customers for the 'Check a customer' tool."""
import json, pathlib, duckdb, numpy as np, pandas as pd, lightgbm as lgb
R = pathlib.Path(__file__).parent; OUT = R / "out"
con = duckdb.connect(str(OUT / "bank.duckdb"), read_only=True)
meta = json.load(open(OUT / "drift_meta.json")); FEAT = meta["features"]
drift = lgb.Booster(model_file=str(OUT / "drift_model.txt"))

# ---- rebuild type model exactly as in prep_final (import its logic by exec up to training)
src = (R / "prep_final.py").read_text()
cut = src.index("d[\"p_drift\"]")
ns = {"__file__": str(R / "prep_final.py")}; exec(src[:cut], ns)
d, TF, type_model, TYPES = ns["d"], ns["TF"], ns["type_model"], ns["TYPES"]
type_model.save_model(str(OUT / "type_model.txt"))

def compact(booster):
    trees = []
    for t in booster.dump_model()["tree_info"]:
        f, th, l, r, v = [], [], [], [], []
        def walk(n):
            i = len(f)
            if "leaf_value" in n: f.append(-1); th.append(0); l.append(-1); r.append(-1); v.append(n["leaf_value"]); return i
            f.append(n["split_feature"]); th.append(n["threshold"]); l.append(0); r.append(0); v.append(0)
            l[i] = walk(n["left_child"]); r[i] = walk(n["right_child"]); return i
        walk(t["tree_structure"]); trees.append([f, th, l, r, v])
    return trees

# ---- starting customers: real accounts on 30 Sep 1998
s = d[d.month == "1998-09-01"].copy()
s["p"] = drift.predict(s[FEAT]); pt = type_model.predict(TF.loc[s.index])
for k in range(3): s[f"pt{k}"] = pt[:, k]
mv = con.execute("""SELECT account_id, month, avg_balance, balance, money_in, money_out, cash_out, received_other_bank
                    FROM monthly_view WHERE month BETWEEN DATE '1997-10-01' AND DATE '1998-12-01'""").df()
mv["month"] = pd.to_datetime(mv.month)
mx = con.execute("""SELECT account_id, date_trunc('month', tx_date)::DATE m, MAX(abs(amount)) mx FROM trans
                    WHERE operation='WIC' AND tx_date BETWEEN DATE '1998-07-01' AND DATE '1998-09-30' GROUP BY 1,2""").df()

def pick(cond, n=1, seed=0):
    c = s[cond]
    return c.sample(n, random_state=seed) if len(c) >= n else c
chosen = [("Steady saver", pick((s.drift == 0) & (s.p < 0.03) & (s.past6 > 40000), seed=4)),
          ("Big withdrawal coming", pick((s.drift == 1) & (s.type == 0) & (s.pt0 > 0.5) & (s.p > 0.3), seed=1)),
          ("Income stopping", pick((s.drift == 1) & (s.type == 1) & (s.pt1 > 0.5) & (s.p > 0.3), seed=2)),
          ("Slow drain", pick((s.drift == 1) & (s.type == 2) & (s.pt2 > 0.5) & (s.p > 0.2), seed=3))]
presets = []
for name, row in chosen:
    r = row.iloc[0]; aid = int(r.account_id)
    m = mv[mv.account_id == aid].sort_values("month")
    past = m[m.month <= "1998-09-01"].tail(12); after = m[m.month > "1998-09-01"]
    mc = mx[mx.account_id == aid]
    maxm = past.tail(3).cash_out.abs().max()
    ratio = float(mc.mx.max() / maxm) if len(mc) and maxm > 0 else 1.0
    presets.append(dict(name=name, id=aid, age=int(r.age), gender=r.gender, region=r.region,
        bal=[round(v) for v in past.avg_balance], end=[round(v) for v in past.balance], inn=[round(v) for v in past.money_in], out=[round(v) for v in past.money_out],
        cash=[round(v) for v in past.cash_out], salary=[round(v) for v in past.received_other_bank],
        x=[float(v) for v in r[FEAT]], tf=[float(v) for v in TF.loc[row.index[0]]], cash_ratio=min(1.0, ratio),
        p=float(r.p), pt=[float(r.pt0), float(r.pt1), float(r.pt2)],
        drift=int(r.drift), type=int(r.type), after=[round(v) for v in after.avg_balance], usual=round(r.past6)))
    print(name, aid, round(r.p, 3), [round(x, 2) for x in (r.pt0, r.pt1, r.pt2)], "drift", r.drift, "type", r.type)

data = dict(feat=FEAT, tfeat=list(TF.columns), types=TYPES, drift_trees=compact(drift), type_trees=compact(type_model),
            presets=presets, drop_frac=meta["drop_frac"])
(OUT / "tool_data.json").write_text(json.dumps(data, separators=(",", ":")))
print("size", (OUT / "tool_data.json").stat().st_size)
