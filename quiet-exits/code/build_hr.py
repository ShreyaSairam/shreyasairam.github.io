import pathlib
R = pathlib.Path(__file__).parent
t = (R/"hr_template.html").read_text().replace("/*__HR__*/null", (R/"out/hr_data.json").read_text())
(R/"employees-tool.html").write_text(t); print(len(t))
