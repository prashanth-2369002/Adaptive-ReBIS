"""
sizing.py -- optimal PV (kWp), battery (kWh) and wind (kW) sizing with GA and PSO.

For each candidate size the whole year (8784 h) is simulated with a fast,
population-vectorised dispatch (renewables first, battery charges from
surplus and discharges by SOC, battery discharge held back for the evening
ToD peak window from 16:00), and the candidate is scored on

    total annual cost = annualised capex (CRF) + O&M
                      + energy bill - export credit + demand charges + battery wear
                      + carbon cost of grid CO2

All candidates of one GA generation / PSO iteration are simulated together,
so one generation of 40 designs costs about the same as one design.
"""
import numpy as np
import pandas as pd

import config as C

LB = np.array([0.0, 0.0, 0.0])          # PV kWp, BESS kWh, wind kW
UB = np.array([C.ROOF_PV_LIMIT_KWP, 600.0, 100.0])
CARBON_PRICE = 1500.0                   # Rs/tCO2 [ASSUMPTION] shadow carbon price


def crf(r, n):
    return r * (1 + r) ** n / ((1 + r) ** n - 1)


def demand_charges(monthly_max_kw):
    """Monthly HT demand charges incl. 2x rate on demand above the contract."""
    kva = np.asarray(monthly_max_kw) / C.POWER_FACTOR
    cmd = C.CONTRACT_DEMAND_KVA
    return C.DEMAND_CHARGE * (np.maximum(kva, 0.8 * cmd) + np.maximum(kva - cmd, 0))


def annual_cost(designs, w, load, capex_bess=None):
    """designs: (P,3). Returns (P,) total annual cost in Rs lakh and a dict of parts."""
    designs = np.atleast_2d(designs)
    pv, E, wd = designs[:, 0], designs[:, 1], designs[:, 2]
    pvp = w["pv_kw_per_kwp"].to_numpy()
    wdp = w["wind_kw_per_kw"].to_numpy()
    tar = w["tariff"].to_numpy()
    hour = w["hour"].to_numpy()
    month = w["month"].to_numpy()
    pmax = C.BESS_C_RATE * E
    Es = np.maximum(E, 1e-9)
    soc = np.full(len(pv), C.BESS_SOC_INIT)
    P = len(pv)
    imp_cost = np.zeros(P); exp_cred = np.zeros(P); co2 = np.zeros(P); wear = np.zeros(P)
    mmax = np.zeros((P, 13))
    hold = (hour >= 10) & (hour < 18)   # keep stored solar for the evening peak
    for t in range(len(load)):
        net = load[t] - pv * pvp[t] - wd * wdp[t]
        req = np.where(net < 0, net, np.where(hold[t], 0.0, net))
        dis_max = np.minimum(pmax, np.maximum(soc - C.BESS_SOC_MIN, 0) * Es * C.BESS_ETA_DIS)
        ch_max = np.minimum(pmax, np.maximum(C.BESS_SOC_MAX - soc, 0) * Es / C.BESS_ETA_CH)
        x = np.clip(req, -ch_max, dis_max)
        soc = soc - (np.maximum(x, 0) / C.BESS_ETA_DIS - np.maximum(-x, 0) * C.BESS_ETA_CH) / Es
        g = net - x
        imp = np.maximum(g, 0)
        ex = np.minimum(np.maximum(-g, 0), C.EXPORT_LIMIT_KW)
        imp_cost += imp * tar[t]
        exp_cred += ex * C.EXPORT_PRICE
        co2 += imp * C.GRID_CO2
        wear += np.maximum(x, 0) * C.BESS_DEG_COST * (1.0 if capex_bess is None else capex_bess / C.CAPEX_BESS)
        mmax[:, month[t]] = np.maximum(mmax[:, month[t]], imp)
    demand = demand_charges(mmax[:, 1:]).sum(1)
    cb = C.CAPEX_BESS if capex_bess is None else capex_bess
    capex = pv * C.CAPEX_PV + E * cb + wd * C.CAPEX_WIND
    annuity = (pv * C.CAPEX_PV * crf(C.DISCOUNT, C.LIFE_PV)
               + E * cb * crf(C.DISCOUNT, C.LIFE_BESS)
               + wd * C.CAPEX_WIND * crf(C.DISCOUNT, C.LIFE_WIND))
    om = C.OM_FRAC * capex
    carbon = co2 / 1000 * CARBON_PRICE
    total = annuity + om + imp_cost - exp_cred + demand + wear + carbon
    parts = dict(capex_lakh=capex / 1e5, annuity_lakh=annuity / 1e5, om_lakh=om / 1e5,
                 energy_lakh=imp_cost / 1e5, export_lakh=exp_cred / 1e5,
                 demand_lakh=demand / 1e5, wear_lakh=wear / 1e5, carbon_lakh=carbon / 1e5,
                 co2_t=co2 / 1000, total_lakh=total / 1e5)
    return total / 1e5, parts


def ga_size(w, load, rng, pop=40, gens=40, capex_bess=None):
    X = rng.uniform(LB, UB, (pop, 3))
    X[0] = [0, 0, 0]
    f, _ = annual_cost(X, w, load, capex_bess)
    hist = [f.min()]
    for g in range(gens):
        idx = rng.integers(0, pop, (pop, 3))
        par = X[idx[np.arange(pop), np.argmin(f[idx], 1)]]
        a = rng.uniform(-0.25, 1.25, (pop // 2, 3))
        p1, p2 = par[0::2], par[1::2]
        kids = np.vstack([a * p1 + (1 - a) * p2, a * p2 + (1 - a) * p1])
        sig = (UB - LB) * (0.15 * (1 - g / gens) + 0.005)
        mut = rng.random(kids.shape) < 0.3
        kids = np.clip(kids + mut * rng.normal(0, 1, kids.shape) * sig, LB, UB)
        fk, _ = annual_cost(kids, w, load, capex_bess)
        elite = np.argsort(f)[:2]; worst = np.argsort(fk)[-2:]
        kids[worst], fk[worst] = X[elite], f[elite]
        X, f = kids, fk
        hist.append(f.min())
    return X[np.argmin(f)], np.array(hist)


def pso_size(w, load, rng, n=40, iters=40, capex_bess=None):
    X = rng.uniform(LB, UB, (n, 3))
    X[0] = [0, 0, 0]
    V = np.zeros_like(X)
    f, _ = annual_cost(X, w, load, capex_bess)
    pb, pbf = X.copy(), f.copy()
    gb = pb[np.argmin(pbf)].copy()
    hist = [pbf.min()]
    for k in range(iters):
        wi = 0.9 - 0.5 * k / iters
        V = wi * V + 1.7 * rng.random(X.shape) * (pb - X) + 1.7 * rng.random(X.shape) * (gb - X)
        V = np.clip(V, -0.2 * (UB - LB), 0.2 * (UB - LB))
        X = np.clip(X + V, LB, UB)
        f, _ = annual_cost(X, w, load, capex_bess)
        b = f < pbf
        pb[b], pbf[b] = X[b], f[b]
        gb = pb[np.argmin(pbf)].copy()
        hist.append(pbf.min())
    return gb, np.array(hist)


if __name__ == "__main__":
    import pickle, time
    w, L, fc = pickle.load(open(C.RESULTS_DIR / "_cache.pkl", "rb"))
    load = L["load"].to_numpy()
    grid = np.array([[pv, e, 0] for pv in (0, 200, 300) for e in (0, 100, 200, 300, 400)])
    t = time.time()
    tot, parts = annual_cost(grid, w, load)
    print("grid eval s", time.time() - t)
    df = pd.DataFrame(parts); df.insert(0, "pv", grid[:, 0]); df.insert(1, "bess", grid[:, 1])
    print(df.round(2).to_string())
    rng = np.random.default_rng(0)
    for cb in (15000, 12000, 9000, 6000):
        t = time.time()
        xg, hg = ga_size(w, load, rng, capex_bess=cb)
        xp, hp = pso_size(w, load, rng, capex_bess=cb)
        print(cb, "GA", xg.round(1), hg[-1].round(3), "PSO", xp.round(1), hp[-1].round(3), f"{time.time()-t:.1f}s")
