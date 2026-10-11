"""Town data: ~150 real customers with monthly money flows Apr to Dec 1998, grouped by region."""
import json, pathlib, duckdb, numpy as np, pandas as pd
R = pathlib.Path(__file__).parent; OUT = R / "out"
con = duckdb.connect(str(OUT / "bank.duckdb"), read_only=True)
df = pd.DataFrame(json.loads((OUT / "today_all.json").read_text()))
df = df[df.drift.notna()].copy()
df["rank"] = df.p.rank(ascending=False, method="first").astype(int)

rng = np.random.default_rng(4)
drift = df[df.drift == 1]
# leakers: a mix the model caught and missed, weighted to sizeable balances so the flows are visible
lk = pd.concat([drift[drift["rank"] <= 450].sample(14, random_state=2), drift[drift["rank"] > 450].sample(4, random_state=2)])
stay = df[df.drift == 0]
st = pd.concat([stay[stay["rank"] <= 450].sample(8, random_state=3), stay[stay["rank"] > 450].sample(110, random_state=3)])
town = pd.concat([lk, st])

ids = ",".join(map(str, town.id))
mv = con.execute(f"""SELECT account_id, month, avg_balance, money_in, money_out, cash_out, sent_other_bank
  FROM monthly_view WHERE account_id IN ({ids}) AND month BETWEEN DATE '1998-04-01' AND DATE '1998-12-01' ORDER BY 1, 2""").df()
F = {"F": ["Jana", "Eva", "Petra", "Lucie", "Hana", "Marie", "Alena", "Tereza", "Martina", "Lenka", "Zuzana", "Katerina", "Veronika", "Ivana", "Monika", "Klara", "Anna", "Barbora"],
     "M": ["Jan", "Petr", "Josef", "Pavel", "Martin", "Tomas", "Jiri", "Karel", "Milan", "Lukas", "Ondrej", "Michal", "Jakub", "David", "Vaclav", "Filip", "Adam", "Radek"]}
cnt = {"F": 0, "M": 0}
houses = []
for r in town.sample(frac=1, random_state=5).itertuples():
    m = mv[mv.account_id == r.id]
    if len(m) < 9: continue
    g = r.gender; name = F[g][cnt[g] % len(F[g])]; cnt[g] += 1
    houses.append(dict(name=name, age=int(r.age), region=r.region, p=round(float(r.p), 3), rank=int(r["rank"]) if False else int(r.rank),
                       leak=int(r.drift), usual=round(r.usual),
                       bal=[round(v) for v in m.avg_balance], inn=[round(v) for v in m.money_in], out=[round(v) for v in m.money_out],
                       cash=[round(v) for v in m.cash_out], other=[round(v) for v in m.sent_other_bank]))
regions = sorted({h["region"] for h in houses})
data = dict(months=["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], today=5, houses=houses, regions=regions,
            leakers=sum(h["leak"] for h in houses))
(OUT / "town_data.json").write_text(json.dumps(data, separators=(",", ":")))
print(len(houses), data["leakers"], regions)
mtop = sorted(houses, key=lambda h: -h["p"])[:data["leakers"]]
print("model top-k catches", sum(h["leak"] for h in mtop), "of", data["leakers"])
