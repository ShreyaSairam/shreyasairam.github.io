import pathlib
R = pathlib.Path(__file__).parent
eng = (R/"tool_engine.js").read_text().replace('if (typeof module !== "undefined") module.exports = Engine;', '')
t = (R/"tool_template.html").read_text().replace("/*__ENGINE__*/", eng).replace("/*__TOOL__*/null", (R/"out/tool_data.json").read_text())
(R/"quiet-exits-tool.html").write_text(t); print(len(t))
