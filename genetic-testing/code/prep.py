"""Genetic testing tool: merge duplicate OMIM/Orphanet entries, export compact data, test the matcher on simulated
patients, and calibrate the confidence label on held out cases."""
import sys, json, random, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/portfolio/genomics_dsst")
from engine import load_data, symptom_weights, match_diseases, get_recommendation, overall_recommendation
terms, ds, dg = load_data()
# The same condition often appears twice (OMIM and Orphanet), splitting the evidence. Merge by name.
canon = ds.assign(k=ds.disease_name.str.lower()).groupby("k").disease_id.first()
ds["disease_id"] = ds.disease_name.str.lower().map(canon); ds = ds.drop_duplicates(["disease_id", "hpo_id"])
ds["disease_name"] = ds.groupby("disease_id").disease_name.transform("first")
dg = dg.assign(disease_id=dg.disease_name.str.lower().map(canon)).dropna(subset=["disease_id"])
dg["disease_name"] = dg.disease_id.map(ds.drop_duplicates("disease_id").set_index("disease_id").disease_name)
dg = dg.drop_duplicates(["disease_id", "gene_symbol"])
w = symptom_weights(ds)
tid = {h: i for i, h in enumerate(terms.hpo_id)}
dis = ds.groupby(["disease_id", "disease_name"])["hpo_id"].apply(lambda s: sorted({tid[h] for h in s})).reset_index()
genes = dg[~dg.gene_symbol.isin(["-", ""])].groupby("disease_id").gene_symbol.apply(lambda s: sorted(set(s))).to_dict()
data = dict(terms=terms.name.tolist(), hpo=terms.hpo_id.tolist(), w=[round(w[h], 5) for h in terms.hpo_id],
            dis=[dict(id=r.disease_id, n=r.disease_name, s=r.hpo_id, g=genes.get(r.disease_id, [])) for r in dis.itertuples()])
print("conditions", len(dis))
sym = ds.groupby("disease_id").hpo_id.apply(list).to_dict()
allids = list(tid)

def case(rng, d, k, noise):
    others = [h for h in allids if h not in set(sym[d])]
    return rng.sample(sym[d], k) + rng.sample(others, noise)

# 1) scenario tests
rng = random.Random(7); ev = {}
for k, noise in [(3, 0), (5, 0), (5, 1), (5, 2), (8, 1)]:
    rows = []
    for d in rng.sample(list(sym), 500):
        c = case(rng, d, k, noise)
        ranked, _ = get_recommendation(c, ds, dg, top_n=5, weights=w)
        _, _, gl = overall_recommendation(ranked)
        rows.append((ranked.disease_id.iloc[0] == d, d in set(ranked.disease_id), bool(set(genes.get(d, [])) & set(gl))))
    a = np.array(rows, dtype=float).mean(0)
    ev[f"{k}_{noise}"] = dict(top1=round(a[0], 3), top5=round(a[1], 3), gene=round(a[2], 3)); print(k, noise, ev[f"{k}_{noise}"])
data["eval"] = ev

# 2) confidence calibration: fit on one set of cases, report on another
def feats(seed):
    rng = random.Random(seed); out = []
    for d in rng.sample(list(sym), 500):
        k = rng.choice([3, 4, 5, 6, 8]); noise = rng.choice([0, 0, 1, 2])
        c = case(rng, d, k, noise); r = match_diseases(c, ds, top_n=3, weights=w)
        out.append(dict(n=len(c), noise=noise, score=r.score[0], m=r.matched_symptoms[0], gap=r.score[0] - (r.score[1] if len(r) > 1 else 0),
                        unexpl=len(c) - r.matched_symptoms[0], top1=r.disease_id[0] == d))
    return pd.DataFrame(out)
fit, chk = feats(11), feats(23)
print(fit.groupby(pd.cut(fit.gap, [-.01, .03, .06, .1, .15, 1])).top1.agg(["mean", "size"]))
print(fit.groupby("unexpl").top1.agg(["mean", "size"]))
old = lambda d: (d.score >= 0.55) & (d.m >= d.n.clip(upper=3))
new = lambda d: (d.gap >= 0.1) & (d.unexpl < 2)
for nm, d in [("fit", fit), ("check", chk)]:
    print(nm, "old", round(old(d).mean(), 3), round(d[old(d)].top1.mean(), 3), "new", round(new(d).mean(), 3), round(d[new(d)].top1.mean(), 3), round(d[~new(d)].top1.mean(), 3))
d = chk
data["calib"] = dict(n=len(d), old=dict(share=round(float(old(d).mean()), 3), acc=round(float(d[old(d)].top1.mean()), 3)),
                     new=dict(share=round(float(new(d).mean()), 3), acc=round(float(d[new(d)].top1.mean()), 3), unc_acc=round(float(d[~new(d)].top1.mean()), 3)))
json.dump(data, open("gx_data.json", "w"), separators=(",", ":"))
