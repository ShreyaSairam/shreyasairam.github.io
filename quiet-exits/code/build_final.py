import pathlib
R = pathlib.Path(__file__).parent
t = (R/"final_template.html").read_text().replace("/*__FINAL__*/null", (R/"out/final_data.json").read_text())
(R/"quiet-exits-final.html").write_text(t); print(len(t))
