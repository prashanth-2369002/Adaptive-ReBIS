"""
make_summary.py -- collects the headline numbers from results/*.csv into
results/summary.json (used by the review deck and the explanation guide), so
no number in the slides is typed by hand.
"""
import json

import pandas as pd

import config as C

R = C.RESULTS_DIR


def main():
    s = {}
    f = pd.read_csv(R / "forecast_model_comparison.csv", index_col=0)
    s["forecast"] = f.round(3).to_dict(orient="index")
    ml = f.drop(["Persistence (yesterday)", "Weekly naive (last week)"])
    best = ml["RMSE_kW"].idxmin()
    s["forecast_best"] = best

    z = pd.read_csv(R / "sizing_optimum.csv")
    s["sizing"] = z.round(3).to_dict(orient="records")
    s["sizing_sens"] = pd.read_csv(R / "sizing_battery_price_sensitivity.csv").round(1).to_dict(orient="records")

    for d in ("A", "B"):
        m = pd.read_csv(R / f"strategy_comparison_design{d}.csv", index_col=0)
        s[f"strategies_{d}"] = m.round(3).to_dict(orient="index")
        for n in ("33-bus", "69-bus"):
            t = pd.read_csv(R / f"network_{n}_design{d}.csv", index_col=0)
            s[f"network_{n}_{d}"] = t.round(4).to_dict(orient="index")

    o = pd.read_csv(R / "optimality_GA_PSO_vs_LP.csv")
    s["optimality"] = dict(
        GA_mean=o.gap_GA_pct.mean(), GA_p95=o.gap_GA_pct.quantile(0.95), GA_max=o.gap_GA_pct.max(),
        PSO_mean=o.gap_PSO_pct.mean(), PSO_p95=o.gap_PSO_pct.quantile(0.95), PSO_max=o.gap_PSO_pct.max(),
        t_GA_ms=1000 * o.t_GA.mean(), t_PSO_ms=1000 * o.t_PSO.mean(), t_LP_ms=1000 * o.t_LP.mean(),
        PSO_better_days=int((o.J_PSO < o.J_GA).sum()), days=len(o))
    s["validation"] = pd.read_csv(R / "network_validation.csv").round(4).to_dict(orient="records")
    cc = pd.read_csv(R / "network_bfs_vs_pandapower.csv")
    s["bfs_vs_pp"] = dict(max_dV=float(cc.abs_dV_pu.max()), max_dloss=float(cc.abs_dloss_kW.max()))
    s["battery"] = pd.read_csv(R / "battery_size_sensitivity.csv").round(3).to_dict(orient="records")
    s["reliability"] = pd.read_csv(R / "reliability_outage_monte_carlo.csv").round(3).to_dict(orient="records")
    (R / "summary.json").write_text(json.dumps(s, indent=1, default=float))
    print("wrote", R / "summary.json")


if __name__ == "__main__":
    main()
