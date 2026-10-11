"""Data for the console: simplified district map, every scored account, district totals, model stats."""
import json, math, pathlib, unicodedata, duckdb, numpy as np, pandas as pd
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

R = pathlib.Path(__file__).parent; OUT = R / "out"
con = duckdb.connect(str(OUT / "bank.duckdb"), read_only=True)
norm = lambda s: unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().replace(" ", "").replace("-", "").replace(".", "")
ALIAS = {"hlmpraha": "uzemihlavnihomestaprahy", "jablonecnnisou": "jablonecnadnisou"}

# ---------------- geometry
g = json.load(open("/home/claude/geo/czech-geojson/okresy.json"))
geo = {norm(f["name"]): (f["name"], shape(f["geometry"])) for f in g["features"]}
dist = con.execute("SELECT district_id, district, region, avg_salary, urban_pct FROM district ORDER BY 1").df()
LAT0 = 49.8; K = math.cos(math.radians(LAT0))
allg = unary_union([v[1] for v in geo.values()])
minx, miny, maxx, maxy = allg.bounds
Wd = 1000; S = Wd / ((maxx - minx) * K); Hd = (maxy - miny) * S
proj = lambda lon, lat: ((lon - minx) * K * S, (maxy - lat) * S)
def path(geom):
    geom = geom.simplify(0.004, preserve_topology=True)
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    out = []
    for p in polys:
        for ring in [p.exterior]:
            pts = [proj(x, y) for x, y in ring.coords]
            out.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
    return "".join(out)

districts, by_region = [], {}
for r in dist.itertuples():
    key = ALIAS.get(norm(r.district), norm(r.district))
    name, shp = geo[key]
    c = shp.representative_point(); cx, cy = proj(c.x, c.y)
    name = "Praha" if name.startswith("území") else name
    districts.append(dict(id=int(r.district_id), name=name, region=r.region, d=path(shp), cx=round(cx, 1), cy=round(cy, 1),
                          salary=float(r.avg_salary), urban=float(r.urban_pct)))
    by_region.setdefault(r.region, []).append(shp)
regions = [dict(name=k, d=path(unary_union(v))) for k, v in by_region.items()]

# ---------------- accounts (today = Sep 1998)
today = pd.DataFrame(json.loads((OUT / "today_all.json").read_text()))
today = today[today.drift.notna()].copy()
acc_d = con.execute("SELECT account_id AS id, district_id AS did FROM account").df()
today = today.merge(acc_d, on="id")
today["rank"] = today.at_risk.rank(ascending=False, method="first").astype(int)
today["prank"] = today.p.rank(ascending=False, method="first").astype(int)
today["rrank"] = today.usual.rank(ascending=False, method="first").astype(int)
ids = ",".join(map(str, today.id))
mv = con.execute(f"""SELECT account_id AS id, month, avg_balance FROM monthly_view
   WHERE account_id IN ({ids}) AND month BETWEEN DATE '1997-10-01' AND DATE '1998-12-01' ORDER BY 1,2""").df()
hist = mv.groupby("id").avg_balance.apply(lambda s: [int(round(v, -1)) for v in s]).to_dict()
SIG = ["Signs of financial stress", "Large cash withdrawals", "Income has slowed or moved", "Money is moving to another bank", "Balance sliding"]
FLAG_N = int(round(len(today) * 0.10))
accts = []
for r in today.sort_values("rank").itertuples():
    h = hist.get(r.id, [])
    a = dict(id=int(r.id), d=int(r.did), p=round(float(r.p), 4), risk=int(round(r.at_risk)), usual=int(round(r.usual)),
             leak=int(r.drift), lost=int(round(r.lost)), next3=int(round(r.next3)), age=int(r.age), g=r.gender,
             s=SIG.index(r.signal), rk=int(r.rank), pr=int(r.prank), rr=int(r.rrank), h=h, flag=int(r.prank <= FLAG_N))
    if r.rank <= 800:
        a["why"] = [x["text"] for x in r.reasons]
        a["x"] = [round(v, 5) for v in r.x]
    accts.append(a)

# ---------------- district totals
dt = today.groupby("did").agg(n=("id", "size"), risk=("at_risk", "sum"), leak=("drift", "sum"), lost=("lost", "sum"),
                              usual=("usual", "sum"), flagged=("prank", lambda s: int((s <= FLAG_N).sum()))).reset_index()
dmap = {int(r.did): dict(n=int(r.n), risk=round(float(r.risk)), leak=int(r.leak), lost=round(float(r.lost)),
                         usual=round(float(r.usual)), flagged=int(r.flagged)) for r in dt.itertuples()}
for d in districts: d.update(dmap.get(d["id"], dict(n=0, risk=0, leak=0, lost=0, usual=0, flagged=0)))

# ---------------- model + portfolio stats
D = json.loads((OUT / "dashboard_data.json").read_text())
S0 = json.loads((OUT / "story_data.json").read_text())
port = D["insight"]["portfolio"]; rate = D["insight"]["drift_rate"]
console = dict(
    w=Wd, h=round(Hd, 1), districts=districts, regions=regions, accts=accts, flagN=FLAG_N, sig=SIG,
    features=D["features"], labels=D["labels"],
    kpi=dict(n=len(today), risk=round(float(today.at_risk.sum())), flagged=FLAG_N, leak=int(today.drift.sum()), lost=round(float(today.lost.sum())),
             trans=D["meta"]["stage1"]["trans"], usual=round(float(today.usual.sum()))),
    trend=dict(m=[x["m"] for x in rate], rate=[round(x["rate"], 4) for x in rate]),
    event=D["insight"]["event"], curves=dict(steps=S0["steps"], model=S0["model"], rich=S0["rich"], rand=S0["rand"]),
    model=D["model"], fairness=D["governance"]["fairness"], psi=D["governance"]["monitor"][:6], score_psi=D["governance"]["score_psi"],
    meta=D["meta"])
(OUT / "console_data.json").write_text(json.dumps(console, separators=(",", ":")))
print("size", (OUT / "console_data.json").stat().st_size, "map", Wd, round(Hd), "accts", len(accts))
print(sorted(districts, key=lambda d: -d["risk"])[:5][0]["name"])
