"""
run_all.py -- regenerates EVERY number, table and figure of the project.

    py run_all.py            (about 25-30 min on a laptop; stages are cached)
    py run_all.py --fresh    (ignore the cache and recompute everything)

Stages
  1  data       real PVGIS year -> weather/resource table; one year of site load
  2  forecast   ML day-ahead load forecast, 6 models, month-blocked CV
  3  sizing     GA + PSO optimal PV/BESS/wind size, battery-price sensitivity
  4  dispatch   7 strategies x 366 days for Design A (economic) and B (grid support)
  5  optimality GA / PSO vs exact LP on the identical day-ahead problem, 366 days
  6  battery    Adaptive-ReBIS (PSO) vs rule-based for battery sizes 0-300 kWh
  7  network    IEEE 33-bus and 69-bus annual load flow, all strategies
  8  reliability Monte-Carlo grid outages, energy not served
  9  figures    results/figures/*.png
"""
import pickle
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
warnings.filterwarnings("ignore")

import config as C                      # noqa: E402
import ems                              # noqa: E402
import grid_ieee as G                   # noqa: E402
import simulate                         # noqa: E402
import sizing                           # noqa: E402
from data_prep import build_weather     # noqa: E402
from forecast import run_forecasts      # noqa: E402
from loads import build_loads           # noqa: E402

FRESH = "--fresh" in sys.argv
R = C.RESULTS_DIR
DESIGN_B_BESS = 200.0                   # grid-support battery for Design B (kWh)


def cached(name, fn):
    p = R / f"_stage_{name}.pkl"
    if p.exists() and not FRESH:
        return pickle.loads(p.read_bytes())
    t = time.time()
    out = fn()
    p.write_bytes(pickle.dumps(out))
    print(f"[{name}] done in {time.time() - t:.0f} s")
    return out


# ------------------------------------------------------------------ 1 data
def stage_data():
    w = build_weather()
    L = build_loads(w)
    ds = pd.concat([w, L], axis=1)
    ds.to_csv(C.DATA_DIR / "hourly_dataset_2020.csv", index_label="time_IST")
    return w, L


w, L = cached("data", stage_data)
load = L["load"].to_numpy()


# ------------------------------------------------------------------ 2 forecast
def stage_forecast():
    table, best, fc, imp, pv_mae = run_forecasts(w, L)
    table.to_csv(R / "forecast_model_comparison.csv")
    imp.to_csv(R / "forecast_feature_importance.csv", header=["importance"])
    return table, best, fc, imp, pv_mae


ftable, fbest, fc, fimp, pv_mae = cached("forecast", stage_forecast)


# ------------------------------------------------------------------ 3 sizing
def stage_sizing():
    rng = np.random.default_rng(C.SEED)
    xg, hg = sizing.ga_size(w, load, rng)
    xp, hp = sizing.pso_size(w, load, rng)
    rows = []
    for alg, x in (("GA", xg), ("PSO", xp)):
        tot, parts = sizing.annual_cost(x[None], w, load)
        rows.append(dict(algorithm=alg, pv_kWp=x[0], bess_kWh=x[1], wind_kW=x[2],
                         **{k: float(v[0]) for k, v in parts.items()}))
    for label, x in (("Reference: grid only", [0, 0, 0]), ("Reference: PV only (300 kWp)", [300, 0, 0])):
        tot, parts = sizing.annual_cost(np.array([x]), w, load)
        rows.append(dict(algorithm=label, pv_kWp=x[0], bess_kWh=x[1], wind_kW=x[2],
                         **{k: float(v[0]) for k, v in parts.items()}))
    tab = pd.DataFrame(rows)
    tab.to_csv(R / "sizing_optimum.csv", index=False)
    sens = []
    for cb in (15000, 12000, 9000, 6000, 4000):
        x, _ = sizing.pso_size(w, load, np.random.default_rng(C.SEED + 3), capex_bess=cb)
        sens.append(dict(bess_price_Rs_per_kWh=cb, pv_kWp=x[0], bess_kWh=x[1], wind_kW=x[2]))
    sens = pd.DataFrame(sens)
    sens.to_csv(R / "sizing_battery_price_sensitivity.csv", index=False)
    return tab, sens, hg, hp


size_tab, size_sens, size_hg, size_hp = cached("sizing", stage_sizing)
opt = size_tab[size_tab.algorithm == "PSO"].iloc[0]
DESIGNS = {
    "A": ems.Site(round(opt.pv_kWp), round(opt.bess_kWh), round(opt.wind_kW)),
    "B": ems.Site(round(opt.pv_kWp), DESIGN_B_BESS, round(opt.wind_kW)),
}


# ------------------------------------------------------------------ 4 dispatch
def stage_dispatch():
    out = {}
    for k, site in DESIGNS.items():
        print(f"  design {k}: PV {site.pv_kwp} kWp, BESS {site.bess_kwh} kWh, wind {site.wind_kw} kW")
        rec, conv = simulate.simulate_year(w, L, fc, site, verbose=True)
        m = simulate.annual_metrics(rec, w, L, site)
        m.to_csv(R / f"strategy_comparison_design{k}.csv")
        out[k] = (rec, conv, m)
    return out


dispatch = cached("dispatch", stage_dispatch)


# ------------------------------------------------------------------ 5 optimality
def stage_optimality():
    df = simulate.optimality_study(w, L, fc, DESIGNS["B"])
    df.to_csv(R / "optimality_GA_PSO_vs_LP.csv", index=False)
    return df


optim = cached("optimality", stage_optimality)


# ------------------------------------------------------------------ 6 battery size
def stage_battery():
    rows = []
    for E in (0, 50, 100, 150, 200, 300):
        site = ems.Site(DESIGNS["A"].pv_kwp, E, DESIGNS["A"].wind_kw)
        rec, _ = simulate.simulate_year(
            w, L, fc, site, strategies=["S0 Grid only", "S2 Rule-based ReBIS", "S4 Adaptive-ReBIS (PSO)"],
            verbose=False, pso_kw=dict(n=60, iters=250))
        m = simulate.annual_metrics(rec, w, L, site)
        for s in ("S2 Rule-based ReBIS", "S4 Adaptive-ReBIS (PSO)"):
            r = m.loc[s]
            rows.append(dict(bess_kWh=E, strategy=s, **r.to_dict()))
    df = pd.DataFrame(rows)
    df.to_csv(R / "battery_size_sensitivity.csv", index=False)
    return df


batt = cached("battery", stage_battery)


# ------------------------------------------------------------------ 7 network
NET_STRATS = ["S0 Grid only", "S1 PV + grid", "S2 Rule-based ReBIS",
              "S3 Adaptive-ReBIS (GA)", "S4 Adaptive-ReBIS (PSO)"]


def stage_network():
    val = pd.DataFrame([G.validate("IEEE 33-bus"), G.validate("IEEE 69-bus")])
    val.to_csv(R / "network_validation.csv", index=False)
    rec_b = dispatch["B"][0]
    sl = slice(24 * 135, 24 * 135 + 24)       # 15 May (a peak-demand day)
    site_net = rec_b["S4 Adaptive-ReBIS (PSO)"]["imp"][sl] - rec_b["S4 Adaptive-ReBIS (PSO)"]["exp"][sl]
    cc = pd.concat([G.cross_check(n, site_net, load[sl], w["hour"].to_numpy()[sl]).assign(network=n)
                    for n in ("IEEE 33-bus", "IEEE 69-bus")])
    cc.to_csv(R / "network_bfs_vs_pandapower.csv", index=False)
    out = {}
    for k in DESIGNS:
        rec = dispatch[k][0]
        for n in ("IEEE 33-bus", "IEEE 69-bus"):
            tab, ts = G.annual_network(n, rec, L, w, NET_STRATS)
            tab.to_csv(R / f"network_{n.split()[1]}_design{k}.csv")
            out[(k, n)] = (tab, ts)
    return val, cc, out


net_val, net_cc, net_res = cached("network", stage_network)


# ------------------------------------------------------------------ 8 reliability
def stage_reliability():
    """Monte-Carlo grid outages: [ASSUMPTION] 4 outages / month, start hour
    uniform, duration exponential with mean 1.5 h (rounded up to whole hours).
    During an outage a grid-tied PV inverter without a battery must shut down
    (anti-islanding), so only PV + BESS sites can serve load, from the SOC the
    EMS happened to have at that moment."""
    rng = np.random.default_rng(C.SEED + 21)
    pvp = w["pv_kw_per_kwp"].to_numpy()
    rows = []
    for k, site in DESIGNS.items():
        rec = dispatch[k][0]
        for trial in range(200):
            n_ev = rng.poisson(48)
            starts = rng.integers(0, len(load) - 8, n_ev)
            durs = np.ceil(rng.exponential(1.5, n_ev)).astype(int)
            for s in ("S0 Grid only", "S1 PV + grid", "S2 Rule-based ReBIS", "S4 Adaptive-ReBIS (PSO)"):
                ens = demand = 0.0
                for st, du in zip(starts, durs):
                    hrs = np.arange(st, min(st + du, len(load)))
                    dem = load[hrs].sum()
                    demand += dem
                    if site.bess_kwh <= 0 or s in ("S0 Grid only", "S1 PV + grid"):
                        ens += dem
                        continue
                    soc = rec[s]["soc"][st - 1] if st > 0 else C.BESS_SOC_INIT
                    e_avail = max(soc - C.BESS_SOC_MIN, 0) * site.bess_kwh * C.BESS_ETA_DIS
                    for h in hrs:
                        need = max(load[h] - site.pv_kwp * pvp[h], 0)
                        give = min(need, site.pmax, e_avail)
                        e_avail -= give
                        ens += need - give
                rows.append(dict(design=k, trial=trial, strategy=s, ENS_MWh=ens / 1e3,
                                 outage_demand_MWh=demand / 1e3))
    df = pd.DataFrame(rows)
    summ = (df.groupby(["design", "strategy"])
              .agg(ENS_MWh_per_yr=("ENS_MWh", "mean"), outage_demand_MWh=("outage_demand_MWh", "mean"))
              .reset_index())
    summ["served_during_outage_pct"] = 100 * (1 - summ.ENS_MWh_per_yr / summ.outage_demand_MWh)
    summ.to_csv(R / "reliability_outage_monte_carlo.csv", index=False)
    return summ


rel = cached("reliability", stage_reliability)


# ------------------------------------------------------------------ 9 figures
if __name__ == "__main__":
    import figures
    figures.make_all(globals())
    print("\nAll results in", R)
