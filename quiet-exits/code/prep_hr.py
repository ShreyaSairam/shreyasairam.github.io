"""Employee half: five models on the open IBM HR attrition data, plus an explainable live model for the browser."""
import json, pathlib, numpy as np, pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.cluster import KMeans
from sklearn.metrics import roc_auc_score

R = pathlib.Path(__file__).parent; OUT = R / "out"
df = pd.read_csv("/home/claude/hr_src/EmployeeAttrition/emp_attrition.csv", encoding="utf-8-sig")
y = (df.Attrition == "Yes").astype(int)
NUM = ["Age", "MonthlyIncome", "DistanceFromHome", "JobSatisfaction", "EnvironmentSatisfaction", "WorkLifeBalance",
       "JobInvolvement", "RelationshipSatisfaction", "YearsAtCompany", "YearsInCurrentRole", "YearsSinceLastPromotion",
       "YearsWithCurrManager", "TotalWorkingYears", "NumCompaniesWorked", "JobLevel", "StockOptionLevel",
       "TrainingTimesLastYear", "PercentSalaryHike", "Education"]
CAT = ["OverTime", "BusinessTravel", "MaritalStatus", "Department"]
X = pd.get_dummies(df[NUM + CAT], columns=CAT, drop_first=True).astype(float)
cols = list(X.columns)
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, stratify=y, random_state=7)
sc = StandardScaler().fit(Xtr); Ztr, Zte = sc.transform(Xtr), sc.transform(Xte)

def top20(p, yy):
    k = int(len(p) * 0.2); idx = np.argsort(-p)[:k]; return float(yy.values[idx].sum() / yy.sum())
models = {
    "Logistic regression": LogisticRegression(max_iter=3000, C=0.5, class_weight="balanced"),
    "Decision tree": DecisionTreeClassifier(max_depth=5, min_samples_leaf=20, class_weight="balanced", random_state=7),
    "Random forest": RandomForestClassifier(n_estimators=400, min_samples_leaf=5, class_weight="balanced", random_state=7),
    "Neural network": MLPClassifier(hidden_layer_sizes=(16,), alpha=1.0, max_iter=3000, random_state=7)}
results = []
for name, m in models.items():
    m.fit(Ztr, ytr); p = m.predict_proba(Zte)[:, 1]
    results.append(dict(model=name, auc=round(float(roc_auc_score(yte, p)), 3), top20=round(top20(p, yte), 3)))
    print(name, results[-1])

# clustering: who leaves, by segment
km = KMeans(n_clusters=4, n_init=20, random_state=7).fit(sc.transform(X))
df["seg"] = km.labels_
DESC = {"Age": "age", "MonthlyIncome": "pay", "YearsAtCompany": "years at company", "JobLevel": "job level",
        "TotalWorkingYears": "experience", "StockOptionLevel": "stock options", "JobSatisfaction": "job satisfaction",
        "YearsSinceLastPromotion": "years since promotion", "DistanceFromHome": "commute"}
segs = []
for s in range(4):
    g = df[df.seg == s]
    z = ((g[list(DESC)].mean() - df[list(DESC)].mean()) / df[list(DESC)].std()).sort_values(key=abs, ascending=False)
    traits = [("Higher " if v > 0 else "Lower ") + DESC[k] for k, v in z.head(2).items()]
    segs.append(dict(n=int(len(g)), rate=round(float((g.Attrition == "Yes").mean()), 3), traits=traits,
                     overtime=round(float((g.OverTime == "Yes").mean()), 2), age=round(float(g.Age.mean())), pay=round(float(g.MonthlyIncome.mean()))))
segs.sort(key=lambda s: -s["rate"])
print(segs)
results.insert(0, dict(model="Clustering (k-means)", auc=None, top20=None, note="Finds 4 groups; leaving rates range from "
                       f"{min(s['rate'] for s in segs)*100:.0f}% to {max(s['rate'] for s in segs)*100:.0f}%"))

# live model for the browser: the logistic regression (explainable)
lr = models["Logistic regression"]
live = dict(cols=cols, mean=sc.mean_.round(6).tolist(), std=sc.scale_.round(6).tolist(),
            coef=lr.coef_[0].round(6).tolist(), intercept=float(lr.intercept_[0]))
# class_weight=balanced shifts probabilities; recalibrate intercept so average predicted = base rate
p_all = lr.predict_proba(sc.transform(X))[:, 1]
from scipy.optimize import brentq
def avgp(b): return float((1 / (1 + np.exp(-(np.log(p_all / (1 - p_all)) - live["intercept"] + b)))).mean())
live["intercept_cal"] = float(brentq(lambda b: avgp(b) - y.mean(), -10, 10))

# presets: real employees
p_cal = 1 / (1 + np.exp(-(np.log(p_all / (1 - p_all)) - live["intercept"] + live["intercept_cal"])))
df["p"] = p_cal
pick = lambda cond, seed: df[cond].sample(1, random_state=seed).iloc[0]
pre = [("Settled senior", pick((df.Attrition == "No") & (df.p < 0.05) & (df.JobLevel >= 3), 1)),
       ("Overworked junior", pick((df.Attrition == "Yes") & (df.OverTime == "Yes") & (df.JobLevel == 1) & (df.p > 0.5), 2)),
       ("Stuck without promotion", pick((df.YearsSinceLastPromotion >= 5) & (df.p > 0.2), 3)),
       ("Long commute", pick((df.DistanceFromHome >= 20) & (df.p > 0.25), 4))]
presets = []
for name, r in pre:
    presets.append(dict(name=name, left=r.Attrition == "Yes", p=round(float(r.p), 4), role=r.JobRole, dept=r.Department,
                        raw={c: (r[c] if c in CAT else float(r[c])) for c in NUM + CAT}))
    print(name, r.JobRole, round(r.p, 3), r.Attrition)
data = dict(results=results, segs=segs, live=live, presets=presets, num=NUM, cat=CAT, base=round(float(y.mean()), 4),
            n=int(len(df)), n_test=int(len(yte)),
            ranges={c: [float(df[c].min()), float(df[c].max())] for c in NUM},
            levels={c: sorted(df[c].unique().tolist()) for c in CAT})
(OUT / "hr_data.json").write_text(json.dumps(data, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
print("ok")
