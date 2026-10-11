import pathlib
R = pathlib.Path(__file__).parent
t = (R/"town_template.html").read_text().replace("/*__TOWN__*/null", (R/"out/town_data.json").read_text())
(R/"quiet-exits-town.html").write_text(t); print(len(t))
