"""Out of Phase: the battery optimiser behind the app.

For each city and battery size, this finds the most profitable way to run a
battery over one real day, then asks how much profit it gives up as it is made
to care more about the local street (the substation or city network).

The result is 11 plans per city and size, from "care" 0 (money only) to
care 1 (least possible overload). The app plays these plans back.

Run:
    pip install numpy scipy
    python optimise.py                 # writes frontier.json
    python optimise.py --check ../index.html   # compares with the live app
"""
import argparse
import json
import pathlib

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

HERE = pathlib.Path(__file__).parent
N, DT = 96, 0.25          # 96 intervals of 15 minutes
ETA = 0.9                 # round trip efficiency, applied when charging
HOURS = 4                 # energy = 4 hours of power
SIZES = (0.05, 0.10, 0.20)  # battery power as a share of the day's peak load
CARE_STEPS = 11
WEAR = 0.03               # wear cost per MWh moved, as a share of the median price
TIE_BREAK = 1e-3          # tiny cost on overload so equal profit plans pick the kinder one


def solve(load, price, line, size, cap=None):
    """Most profitable plan, optionally with overload energy (MWh) capped at `cap`.

    Variables per interval: charge c, discharge d, state of charge s, overload o.
    The battery starts and ends full.
    """
    L, pr = np.asarray(load), np.asarray(price)
    P = size * L.max()
    E = HOURS * P
    C, D, S, O = 0, N, 2 * N, 3 * N
    wear = WEAR * np.median(pr)

    cost = np.zeros(4 * N)
    cost[C:C + N] = pr * DT + wear * DT      # buying power to charge
    cost[D:D + N] = -pr * DT + wear * DT     # selling power when releasing
    cost[O:O + N] = TIE_BREAK * DT

    # state of charge: s[t] = s[t-1] + ETA*c[t]*DT - d[t]*DT, starting full
    A_eq, b_eq = lil_matrix((N, 4 * N)), np.zeros(N)
    for t in range(N):
        A_eq[t, S + t] = 1
        if t:
            A_eq[t, S + t - 1] = -1
        else:
            b_eq[t] = E
        A_eq[t, C + t] = -ETA * DT
        A_eq[t, D + t] = DT

    # overload: load + c - d - line <= o, and optionally total overload <= cap
    rows = N + (cap is not None)
    A_ub, b_ub = lil_matrix((rows, 4 * N)), []
    for t in range(N):
        A_ub[t, C + t], A_ub[t, D + t], A_ub[t, O + t] = 1, -1, -1
        b_ub.append(line - L[t])
    if cap is not None:
        for t in range(N):
            A_ub[N, O + t] = DT
        b_ub.append(cap)

    bounds = [(0, P)] * N + [(0, P)] * N + [(0, E)] * (N - 1) + [(E, E)] + [(0, None)] * N
    r = linprog(cost, A_ub=A_ub.tocsr(), b_ub=b_ub, A_eq=A_eq.tocsr(), b_eq=b_eq,
                bounds=bounds, method="highs")
    if r.status != 0:
        raise ValueError(r.message)

    c, d, s = r.x[C:C + N], r.x[D:D + N], r.x[S:S + N]
    net = d - c                     # positive = releasing to the grid
    street = L - net                # what the street carries with the battery
    return dict(
        net=net, soc=s / E, P=P, E=E,
        money=float((pr * net * DT).sum()),
        over=float(np.maximum(0, street - line).sum() * DT),
        hours=float((street > line + 1e-6).sum() * DT),
    )


def least_overload(load, price, line, size, hi):
    """Smallest overload energy the battery can reach (binary search on the cap)."""
    lo = 0.0
    for _ in range(40):
        mid = (lo + hi) / 2
        try:
            solve(load, price, line, size, mid)
            hi = mid
        except ValueError:
            lo = mid
    return hi


def frontier(day):
    L, pr, line = day["load"], day["price"], day["line"]
    base = np.asarray(L)
    out = dict(load=L, price=pr, line=line,
               noneHours=float((base > line).sum() * DT),
               noneOver=round(float(np.maximum(0, base - line).sum() * DT), 2),
               sizes={})
    for size in SIZES:
        money_first = solve(L, pr, line, size)
        floor = least_overload(L, pr, line, size, money_first["over"])
        pts = []
        for i in range(CARE_STEPS):
            care = i / (CARE_STEPS - 1)
            cap = money_first["over"] + care * (floor - money_first["over"])
            p = solve(L, pr, line, size, cap + 1e-9)
            pts.append(dict(care=round(care, 1),
                            net=[round(x, 2) for x in p["net"]],
                            soc=[round(x, 3) for x in p["soc"]],
                            money=round(p["money"]), hours=p["hours"],
                            over=round(p["over"], 2)))
        out["sizes"][str(size)] = dict(P=round(money_first["P"], 2),
                                       E=round(money_first["E"], 2), pts=pts)
    return out


def check(result, app_html):
    """Compare with the data embedded in the live app."""
    html = pathlib.Path(app_html).read_text()
    i = html.index("const DATA = ") + len("const DATA = ")
    live, _ = json.JSONDecoder().raw_decode(html[i:])
    worst_money = worst_over = 0.0
    for k in result:
        for s, block in result[k]["sizes"].items():
            for a, b in zip(block["pts"], live[k]["sizes"][s]["pts"]):
                worst_money = max(worst_money, abs(a["money"] - b["money"]) / abs(b["money"]))
                worst_over = max(worst_over, abs(a["over"] - b["over"]) / max(1, b["over"]))
    print(f"largest difference vs live app: money {worst_money:.3%}, overload {worst_over:.3%}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", metavar="APP_HTML", help="compare with the live app's data")
    args = ap.parse_args()
    days = json.loads((HERE / "day_inputs.json").read_text())
    result = {k: frontier(v) for k, v in days.items()}
    (HERE / "frontier.json").write_text(json.dumps(result, separators=(",", ":")))
    print("wrote frontier.json")
    if args.check:
        check(result, args.check)
