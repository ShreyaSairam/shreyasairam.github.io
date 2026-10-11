"""Compact the LightGBM model for the browser: each tree becomes flat arrays."""
import json, pathlib
OUT = pathlib.Path(__file__).parent / "out"
m = json.loads((OUT / "model.json").read_text())
trees = []
for t in m["tree_info"]:
    feat, thr, left, right, val = [], [], [], [], []
    def walk(n):
        i = len(feat)
        if "leaf_value" in n:
            feat.append(-1); thr.append(0); left.append(-1); right.append(-1); val.append(n["leaf_value"])
            return i
        assert n["decision_type"] == "<="
        feat.append(n["split_feature"]); thr.append(n["threshold"]); left.append(0); right.append(0); val.append(0)
        left[i] = walk(n["left_child"]); right[i] = walk(n["right_child"])
        return i
    walk(t["tree_structure"])
    trees.append([feat, thr, left, right, val])
(OUT / "model_compact.json").write_text(json.dumps(trees, separators=(",", ":")))
print(len(trees), (OUT / "model_compact.json").stat().st_size)
