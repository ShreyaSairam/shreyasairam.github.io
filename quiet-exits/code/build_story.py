import json, pathlib
R = pathlib.Path(__file__).parent
t = (R/"story_template.html").read_text()
s = (R/"out/story_data.json").read_text()
ev = json.loads((R/"out/dashboard_data.json").read_text())["insight"]["event"]
t = t.replace("/*__STORY__*/null", s).replace("/*__EVENT__*/null", json.dumps(ev))
(R/"quiet-exits-story.html").write_text(t); print(len(t))
