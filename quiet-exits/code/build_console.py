import pathlib
R = pathlib.Path(__file__).parent
t = (R/"console_template.html").read_text().replace("/*__CONSOLE__*/null", (R/"out/console_data.json").read_text()).replace("/*__MODEL__*/null", (R/"out/model_compact.json").read_text())
(R/"quiet-exits-console.html").write_text(t); print(len(t))
