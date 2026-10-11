import json, pathlib
R = pathlib.Path(__file__).parent
t = (R/"template.html").read_text()
data = json.loads((R/"out/dashboard_data.json").read_text())
def rnd(o):
    if isinstance(o, float): return round(o, 5)
    if isinstance(o, list): return [rnd(v) for v in o]
    if isinstance(o, dict): return {k: (v if k == "x" else rnd(v)) for k, v in o.items()}
    return o
t = t.replace("/*__DATA__*/null", json.dumps(rnd(data), separators=(",", ":")))
t = t.replace("/*__MODEL__*/null", (R/"out/model_compact.json").read_text())
t = t.replace('/*__SQL__*/""', json.dumps((R/"sql/01_build_monthly_view.sql").read_text()).replace("</", "<\\/"))
(R/"quiet-exits.html").write_text(t)
print(len(t))
