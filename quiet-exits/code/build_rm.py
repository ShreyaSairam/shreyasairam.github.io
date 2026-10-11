import json, pathlib
R = pathlib.Path(__file__).parent
t = (R/"rm_template.html").read_text()
rm = json.loads((R/"out/rm_data.json").read_text())
d = json.loads((R/"out/dashboard_data.json").read_text())
meta = dict(trans=d["meta"]["stage1"]["trans"], recall=d["model"]["test"]["recall_top10"])
t = t.replace("/*__RM__*/null", json.dumps(rm, separators=(",", ":"))).replace("/*__META__*/null", json.dumps(meta))
(R/"quiet-exits-game.html").write_text(t); print(len(t))
