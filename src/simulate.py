"""
simulate.py -- runs every dispatch strategy over the whole year (366 days),
day by day, carrying each strategy's battery SOC from one day to the next.

Strategies
  S0 Grid only             : no PV, no battery (today's situation)
  S1 PV + grid             : renewables, no battery
  S2 Rule-based ReBIS      : conventional rule (charge surplus / discharge deficit)
  S3 Adaptive-ReBIS (GA)   : ML forecast -> GA day-ahead plan -> real-time correction
  S4 Adaptive-ReBIS (PSO)  : ML forecast -> PSO day-ahead plan -> real-time correction
  S5 LP on forecast        : exact optimum of the same forecast problem (benchmark)
  S6 Perfect foresight LP  : exact optimum with tomorrow known exactly (upper bound,
                             not achievable in reality)
"""
import numpy as np
import pandas as pd

import config as C
import ems

STRATS = ["S0 Grid only", "S1 PV + grid", "S2 Rule-based ReBIS",
          "S3 Adaptive-ReBIS (GA)", "S4 Adaptive-ReBIS (PSO)",
          "S5 LP on forecast", "S6 Perfect-foresight LP"]


def simulate_year(w, L, fc, site, strategies=STRATS, verbose=True, ga_kw=None, pso_kw=None):
    rng = np.random.default_rng(C.SEED + 7)
    n_days = len(w) // 24
    ren_act = site.pv_kwp * w["pv_kw_per_kwp"].to_numpy() + site.wind_kw * w["wind_kw_per_kw"].to_numpy()
    ren_fc = site.pv_kwp * fc["pv_fc_per_kwp"].to_numpy() + site.wind_kw * w["wind_kw_per_kw"].shift(24).bfill().to_numpy()
    load = L["load"].to_numpy()
    load_fc = fc["load_fc"].to_numpy()
    tariff = w["tariff"].to_numpy()
    no_site = ems.Site(0, 0, 0)

    rec = {s: {k: np.zeros(len(w)) for k in ("x", "soc", "imp", "exp", "cur")} for s in strategies}
    soc = {s: C.BESS_SOC_INIT for s in strategies}
    conv = {"GA": [], "PSO": []}
    for d in range(n_days):
        sl = slice(24 * d, 24 * d + 24)
        net_a = load[sl] - ren_act[sl]
        net_f = load_fc[sl] - ren_fc[sl]
        tar = tariff[sl]
        plans = {}
        rb_f = ems.rule_based_request(net_f, site)
        seeds = [rb_f, np.zeros(24)]
        for s in strategies:
            if s == "S0 Grid only":
                out = ems.execute_plain(np.zeros(24), load[sl], 0.5, no_site)
            elif s == "S1 PV + grid":
                out = ems.execute_plain(np.zeros(24), net_a, 0.5, no_site)
            elif s == "S2 Rule-based ReBIS":
                out = ems.execute_plain(ems.rule_based_request(net_a, site), net_a, soc[s], site)
            elif s == "S3 Adaptive-ReBIS (GA)":
                plan, h = ems.ga(net_f, tar, soc[s], site, rng, seeds=seeds, **(ga_kw or {}))
                plans["GA"] = plan
                conv["GA"].append(h)
                out = ems.realtime_execute(plan, net_f, net_a, soc[s], site)
            elif s == "S4 Adaptive-ReBIS (PSO)":
                plan, h = ems.pso(net_f, tar, soc[s], site, rng, seeds=seeds, **(pso_kw or {}))
                plans["PSO"] = plan
                conv["PSO"].append(h)
                out = ems.realtime_execute(plan, net_f, net_a, soc[s], site)
            elif s == "S5 LP on forecast":
                plan, _ = ems.lp(net_f, tar, soc[s], site)
                plans["LP"] = plan
                out = ems.realtime_execute(plan, net_f, net_a, soc[s], site)
            elif s == "S6 Perfect-foresight LP":
                plan, _ = ems.lp(net_a, tar, soc[s], site)
                out = ems.execute_plain(plan, net_a, soc[s], site)
            for k in rec[s]:
                rec[s][k][sl] = out[k]
            soc[s] = out["soc"][-1] if site.bess_kwh > 0 else C.BESS_SOC_INIT
        if verbose and d % 60 == 0:
            print(f"  day {d+1}/{n_days}")
    return rec, conv


def optimality_study(w, L, fc, site, n_days=None, ga_kw=None, pso_kw=None):
    """Same forecast problem, same start SOC (50 %), solved by GA, PSO and the
    exact LP. Returns per-day objective values and solve times."""
    import time
    rng = np.random.default_rng(C.SEED + 11)
    ren_fc = site.pv_kwp * fc["pv_fc_per_kwp"].to_numpy()
    net_all = fc["load_fc"].to_numpy() - ren_fc
    tariff = w["tariff"].to_numpy()
    n_days = n_days or len(w) // 24
    rows = []
    for d in range(n_days):
        sl = slice(24 * d, 24 * d + 24)
        net, tar = net_all[sl], tariff[sl]
        norms = ems.day_norms(net, tar)
        seeds = [ems.rule_based_request(net, site), np.zeros(24)]
        t0 = time.perf_counter(); xl, _ = ems.lp(net, tar, C.BESS_SOC_INIT, site); tl = time.perf_counter() - t0
        t0 = time.perf_counter(); xg, _ = ems.ga(net, tar, C.BESS_SOC_INIT, site, rng, seeds=seeds, **(ga_kw or {})); tg = time.perf_counter() - t0
        t0 = time.perf_counter(); xp, _ = ems.pso(net, tar, C.BESS_SOC_INIT, site, rng, seeds=seeds, **(pso_kw or {})); tp = time.perf_counter() - t0
        J = {k: ems.objective(x[None], net, tar, C.BESS_SOC_INIT, site, norms)[0][0]
             for k, x in (("LP", xl), ("GA", xg), ("PSO", xp), ("none", np.zeros(24)))}
        rows.append(dict(day=d + 1, J_none=J["none"], J_LP=J["LP"], J_GA=J["GA"], J_PSO=J["PSO"],
                         t_LP=tl, t_GA=tg, t_PSO=tp))
    df = pd.DataFrame(rows)
    df["gap_GA_pct"] = 100 * (df.J_GA - df.J_LP) / df.J_LP
    df["gap_PSO_pct"] = 100 * (df.J_PSO - df.J_LP) / df.J_LP
    return df


def annual_metrics(rec, w, L, site):
    tariff = w["tariff"].to_numpy()
    month = w["month"].to_numpy()
    hour = w["hour"].to_numpy()
    peak_mask = np.isin(hour, C.PEAK_HOURS)
    load = L["load"].to_numpy()
    rows = []
    for s, r in rec.items():
        imp, exp, x, cur = r["imp"], r["exp"], r["x"], r["cur"]
        energy = np.sum(imp * tariff)
        export_rev = np.sum(exp) * C.EXPORT_PRICE
        deg = np.sum(np.maximum(x, 0)) * C.BESS_DEG_COST
        md = pd.Series(imp).groupby(month).max().to_numpy()
        demand = np.sum(md / C.POWER_FACTOR) * C.DEMAND_CHARGE
        daily_peak = imp.reshape(-1, 24).max(1)
        uses_ren = not s.startswith("S0")
        ren_gen = (site.pv_kwp * w["pv_kw_per_kwp"].to_numpy()
                   + site.wind_kw * w["wind_kw_per_kw"].to_numpy()) if uses_ren else np.zeros(len(w))
        ren_used = ren_gen - exp - cur
        rows.append({
            "strategy": s,
            "grid_import_MWh": imp.sum() / 1000,
            "energy_bill_Rs_lakh": energy / 1e5,
            "export_credit_Rs_lakh": export_rev / 1e5,
            "demand_charges_Rs_lakh": demand / 1e5,
            "battery_wear_Rs_lakh": deg / 1e5,
            "net_operating_cost_Rs_lakh": (energy - export_rev + demand + deg) / 1e5,
            "annual_peak_import_kW": imp.max(),
            "mean_daily_peak_kW": daily_peak.mean(),
            "peak_window_import_MWh": imp[peak_mask].sum() / 1000,
            "CO2_tonnes": imp.sum() * C.GRID_CO2 / 1000,
            "self_sufficiency_pct": 100 * (1 - imp.sum() / load.sum()),
            "renewable_self_consumption_pct": 100 * ren_used.sum() / max(ren_gen.sum(), 1e-9) if uses_ren else 0.0,
            "curtailed_MWh": cur.sum() / 1000,
            "battery_cycles": np.sum(np.maximum(x, 0)) / max(site.bess_kwh * (C.BESS_SOC_MAX - C.BESS_SOC_MIN), 1e-9),
        })
    df = pd.DataFrame(rows).set_index("strategy")
    base = df.loc["S0 Grid only"]
    df["cost_saving_pct"] = 100 * (1 - df["net_operating_cost_Rs_lakh"] / base["net_operating_cost_Rs_lakh"])
    df["peak_reduction_pct"] = 100 * (1 - df["annual_peak_import_kW"] / base["annual_peak_import_kW"])
    df["CO2_reduction_pct"] = 100 * (1 - df["CO2_tonnes"] / base["CO2_tonnes"])
    return df
