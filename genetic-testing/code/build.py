import pathlib
R = pathlib.Path(__file__).parent
t = (R/"gx_template.html").read_text().replace("/*__GX__*/null", (R/"gx_data.json").read_text())
(R/"gx-tool.html").write_text(t); print(len(t))
