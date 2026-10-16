"""
ems.py -- the Adaptive-ReBIS energy management system.

Two layers, run every day of the year:

1. DAY-AHEAD SCHEDULER (forecast-driven). At the end of day D-1 it receives
   the ML load forecast, the PV/wind forecast, the ToD tariff and the CO2
   factor for day D, and chooses the battery power for each of the 24 hours.
   Objective (adaptive weighted sum, every term normalised by the no-battery
   case of the same day so the weights are comparable):

       J = sum_t wc(t) * cost_t / C0  +  sum_t we(t) * CO2_t / E0
           + Wp * max_t( phi(t) * import_t ) / P0

   wc, we, phi change with the hour (ToD peak / normal / off-peak), i.e. the
   priority shifts from "cheapest" at night to "lowest grid draw" in the
   evening peak.  The schedule must end the day at >= 50 % SOC.
   Solvers: Genetic Algorithm, Particle Swarm Optimisation (both written
   here in NumPy, population-vectorised) and, as a benchmark, the exact
   Linear-Programming optimum (SciPy HiGHS) of the very same problem.

2. REAL-TIME CORRECTION (adaptive). The forecast is never perfect. Each hour
   the controller sees the actual load and PV:
     * ToD peak hours  : battery absorbs the forecast error so the grid draw
                         stays at the planned value (as far as SOC allows)
     * other hours     : follow the plan, but soak up any unforecast solar
                         surplus instead of exporting it.
     * all hours       : peak guard -- grid import may not exceed the highest
                         import the plan expected for that day; the battery
                         charges less / discharges more to hold it.

Power flow rule (as in the abstract): PV/wind feed the load first, the battery
charges from surplus / discharges by SOC, and the grid covers any deficit or
absorbs the remaining export (up to the export limit, the rest is curtailed).
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

import config as C


@dataclass
class Site:
    pv_kwp: float = C.PV_KWP
    bess_kwh: float = C.BESS_KWH
    wind_kw: float = C.WIND_KW

    @property
    def pmax(self):
        return C.BESS_C_RATE * self.bess_kwh


# ------------------------------------------------------------------ weights
def hourly_weights(hours=np.arange(24)):
    wc, wp, we = np.zeros(24), np.zeros(24), np.zeros(24)
    for i, h in enumerate(hours):
        if h in C.PEAK_HOURS:
            wc[i], wp[i], we[i] = C.W_PEAK_HOURS
        elif h in C.OFFPEAK_HOURS:
            wc[i], wp[i], we[i] = C.W_OFFPEAK_HOURS
        else:
            wc[i], wp[i], we[i] = C.W_NORMAL_HOURS
    # an import peak inside the ToD peak window counts fully; outside it still
    # counts (>= 70 %) so the optimiser cannot simply move the peak elsewhere
    phi = 0.6 + 0.4 * wp / wp.max()
    Wp = wp.mean()                # overall weight of the peak term
    return wc, we, phi, Wp


WC, WE, PHI, WP = hourly_weights()


# ------------------------------------------------------------------ physics
def step_battery(x, soc, site):
    """Clip requested battery power x (kW, +discharge / -charge) to what SOC and
    the converter allow, return (actual x, new SOC). Works on arrays."""
    E = max(site.bess_kwh, 1e-9)
    dis_max = np.minimum(site.pmax, np.maximum(soc - C.BESS_SOC_MIN, 0) * E * C.BESS_ETA_DIS)
    ch_max = np.minimum(site.pmax, np.maximum(C.BESS_SOC_MAX - soc, 0) * E / C.BESS_ETA_CH)
    x = np.clip(x, -ch_max, dis_max)
    soc = soc - (np.maximum(x, 0) / C.BESS_ETA_DIS - np.maximum(-x, 0) * C.BESS_ETA_CH) / E
    return x, soc


def grid_split(g):
    imp = np.maximum(g, 0)
    surplus = np.maximum(-g, 0)
    exp = np.minimum(surplus, C.EXPORT_LIMIT_KW)
    return imp, exp, surplus - exp


def simulate_schedule(X, net, soc0, site):
    """Vectorised over a population. X: (P,24) requested battery kW. net: (24,)
    load - renewables. Returns dict of (P,24) arrays."""
    X = np.atleast_2d(X)
    P = X.shape[0]
    soc = np.full(P, soc0, float)
    xa = np.zeros_like(X)
    socs = np.zeros_like(X)
    for t in range(24):
        xa[:, t], soc = step_battery(X[:, t], soc, site)
        socs[:, t] = soc
    imp, exp, cur = grid_split(net[None, :] - xa)
    return dict(x=xa, soc=socs, imp=imp, exp=exp, cur=cur)


def day_norms(net, tariff):
    imp0, exp0, _ = grid_split(net)
    C0 = max(np.sum(imp0 * tariff) - np.sum(exp0) * C.EXPORT_PRICE, 1.0)
    C0 = max(C0, np.sum(imp0 * tariff) * 0.25, 1.0)
    E0 = max(np.sum(imp0) * C.GRID_CO2, 1.0)
    P0 = max(np.max(imp0 * PHI), 1.0)
    return C0, E0, P0


def objective(X, net, tariff, soc0, site, norms):
    s = simulate_schedule(X, net, soc0, site)
    C0, E0, P0 = norms
    cost = s["imp"] * tariff - s["exp"] * C.EXPORT_PRICE + np.maximum(s["x"], 0) * C.BESS_DEG_COST
    co2 = s["imp"] * C.GRID_CO2
    J = (cost * WC).sum(1) / C0 + (co2 * WE).sum(1) / E0 + WP * (s["imp"] * PHI).max(1) / P0
    short = np.maximum(C.BESS_SOC_INIT - s["soc"][:, -1], 0)   # end-of-day SOC target
    return J + 50.0 * short, s


# ------------------------------------------------------------------ rule based
def rule_based_request(net, site):
    """Conventional ReBIS rule: charge from any surplus, discharge to cover any
    deficit (limits applied later by step_battery)."""
    return np.clip(net, -site.pmax, site.pmax)


# ------------------------------------------------------------------ GA
def ga(net, tariff, soc0, site, rng, pop=150, gens=500, seeds=()):
    if site.bess_kwh <= 0:
        return np.zeros(24), np.zeros(1)
    norms = day_norms(net, tariff)
    pm = site.pmax
    P = rng.uniform(-pm, pm, (pop, 24))
    for i, s in enumerate(seeds):
        P[i] = s
    f, sim = objective(P, net, tariff, soc0, site, norms)
    P = sim["x"]          # repair: genome := the feasible schedule it produced
    hist = []
    for g in range(gens):
        # tournament selection (k=3)
        idx = rng.integers(0, pop, (pop, 3))
        winners = idx[np.arange(pop), np.argmin(f[idx], axis=1)]
        parents = P[winners]
        # blend (BLX-0.3) crossover
        a = rng.uniform(-0.3, 1.3, (pop // 2, 24))
        p1, p2 = parents[0::2], parents[1::2]
        c1 = a * p1 + (1 - a) * p2
        c2 = a * p2 + (1 - a) * p1
        kids = np.vstack([c1, c2])
        cx = rng.random(pop // 2) < 0.9
        kids[: pop // 2][~cx], kids[pop // 2:][~cx] = p1[~cx], p2[~cx]
        # gaussian mutation, step shrinks over generations
        sigma = pm * (0.25 * (1 - g / gens) + 0.01)
        mut = rng.random(kids.shape) < 0.15
        kids = np.clip(kids + mut * rng.normal(0, sigma, kids.shape), -pm, pm)
        fk, sim = objective(kids, net, tariff, soc0, site, norms)
        kids = sim["x"]   # Lamarckian repair (SOC / power limits)
        # elitism: keep the best 2 of the old generation
        elite = np.argsort(f)[:2]
        worst = np.argsort(fk)[-2:]
        kids[worst], fk[worst] = P[elite], f[elite]
        P, f = kids, fk
        hist.append(f.min())
    return P[np.argmin(f)], np.array(hist)


# ------------------------------------------------------------------ PSO
def pso(net, tariff, soc0, site, rng, n=100, iters=500, seeds=()):
    if site.bess_kwh <= 0:
        return np.zeros(24), np.zeros(1)
    norms = day_norms(net, tariff)
    pm = site.pmax
    X = rng.uniform(-pm, pm, (n, 24))
    for i, s in enumerate(seeds):
        X[i] = s
    V = rng.uniform(-0.1, 0.1, (n, 24)) * pm
    f, _ = objective(X, net, tariff, soc0, site, norms)
    pb, pbf = X.copy(), f.copy()
    gb = pb[np.argmin(pbf)].copy()
    hist = []
    for k in range(iters):
        w = 0.9 - 0.5 * k / iters
        r1, r2 = rng.random((n, 24)), rng.random((n, 24))
        V = w * V + 1.8 * r1 * (pb - X) + 1.8 * r2 * (gb - X)
        V = np.clip(V, -0.25 * pm, 0.25 * pm)
        X = np.clip(X + V, -pm, pm)
        f, _ = objective(X, net, tariff, soc0, site, norms)
        better = f < pbf
        pb[better], pbf[better] = X[better], f[better]
        gb = pb[np.argmin(pbf)].copy()
        hist.append(pbf.min())
    return gb, np.array(hist)


# ------------------------------------------------------------------ LP (exact)
def lp(net, tariff, soc0, site):
    """Exact optimum of the same day-ahead problem (end SOC >= target as a hard
    constraint). Variables per hour: ch, dis, imp, exp, cur, soc; plus z (peak)."""
    if site.bess_kwh <= 0:
        return np.zeros(24), None
    T, E, pm = 24, site.bess_kwh, site.pmax
    C0, E0, P0 = day_norms(net, tariff)
    nv = 6 * T + 1
    ich, idis, iimp, iexp, icur, isoc = (np.arange(T) + k * T for k in range(6))
    iz = 6 * T
    c = np.zeros(nv)
    c[iimp] = WC * tariff / C0 + WE * C.GRID_CO2 / E0
    c[iexp] = -WC * C.EXPORT_PRICE / C0
    c[idis] = WC * C.BESS_DEG_COST / C0
    c[iz] = WP / P0
    Aeq = lil_matrix((2 * T, nv))
    beq = np.zeros(2 * T)
    for t in range(T):
        # imp - exp - cur + dis - ch = net
        Aeq[t, iimp[t]], Aeq[t, iexp[t]], Aeq[t, icur[t]] = 1, -1, -1
        Aeq[t, idis[t]], Aeq[t, ich[t]] = 1, -1
        beq[t] = net[t]
        # E*soc_t - E*soc_{t-1} - eta_c*ch + dis/eta_d = 0
        r = T + t
        Aeq[r, isoc[t]] = E
        Aeq[r, ich[t]] = -C.BESS_ETA_CH
        Aeq[r, idis[t]] = 1 / C.BESS_ETA_DIS
        if t > 0:
            Aeq[r, isoc[t - 1]] = -E
        else:
            beq[r] = E * soc0
    Aub = lil_matrix((T, nv))
    for t in range(T):
        Aub[t, iimp[t]] = PHI[t]
        Aub[t, iz] = -1
    bounds = ([(0, pm)] * T + [(0, pm)] * T + [(0, None)] * T
              + [(0, C.EXPORT_LIMIT_KW)] * T + [(0, None)] * T
              + [(C.BESS_SOC_MIN, C.BESS_SOC_MAX)] * (T - 1)
              + [(max(C.BESS_SOC_INIT, C.BESS_SOC_MIN), C.BESS_SOC_MAX)]
              + [(0, None)])
    if soc0 < C.BESS_SOC_INIT:   # cannot always reach the target from a low start
        lo = min(C.BESS_SOC_INIT, soc0 + 24 * pm * C.BESS_ETA_CH / E)
        bounds[isoc[-1]] = (min(lo, C.BESS_SOC_MAX), C.BESS_SOC_MAX)
    res = linprog(c, A_ub=Aub.tocsr(), b_ub=np.zeros(T), A_eq=Aeq.tocsr(), b_eq=beq,
                  bounds=bounds, method="highs")
    if res.status != 0:
        return np.zeros(24), None
    x = res.x[idis] - res.x[ich]
    return x, res.fun


# ------------------------------------------------------------------ real time
def realtime_execute(plan, net_fc, net_act, soc0, site, hours=np.arange(24)):
    """Execute a day-ahead battery plan against the ACTUAL load/renewables."""
    soc = soc0
    out = {k: np.zeros(24) for k in ("x", "soc", "imp", "exp", "cur")}
    g_plan = net_fc - plan
    cap = max(np.max(g_plan), 0.0)
    for t in range(24):
        if hours[t] in C.PEAK_HOURS:
            req = net_act[t] - max(g_plan[t], 0.0)        # hold grid at plan
        else:
            req = plan[t]
            if net_act[t] - req < 0:                        # would export:
                req = min(req, net_act[t])                  # charge it instead
        if net_act[t] - req > cap:                          # peak guard
            req = net_act[t] - cap
        x, soc = step_battery(np.array(req), np.array(soc), site)
        x, soc = float(x), float(soc)
        imp, exp, cur = grid_split(np.array(net_act[t] - x))
        out["x"][t], out["soc"][t] = x, soc
        out["imp"][t], out["exp"][t], out["cur"][t] = float(imp), float(exp), float(cur)
    return out


def execute_plain(req, net_act, soc0, site):
    """Execute a request profile directly (rule-based / perfect-foresight)."""
    s = simulate_schedule(req[None, :], net_act, soc0, site)
    return {k: v[0] for k, v in s.items()}
