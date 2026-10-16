"""
grid_ieee.py -- validates the EMS schedules on the IEEE 33-bus and 69-bus
radial distribution feeders by load flow.

Two independent solvers are used:
  * pandapower (Newton-Raphson, open-source, MATPOWER-validated) -- reference
  * our own Backward/Forward Sweep (BFS), vectorised over all 8784 hours, so
    the full year is solved in seconds. It is cross-checked against
    pandapower hour by hour (results/network_bfs_vs_pandapower.csv).

Study set-up
  * Base feeder loads follow a daily feeder shape (peak = the published
    IEEE bus load at 20:00).
  * Identical Adaptive-ReBIS sites (EV hub + HVAC + water heaters + general
    load, with PV + BESS) are connected at 5 tail-end buses
    (33-bus: 18, 22, 25, 30, 33; 69-bus: 27, 35, 46, 50, 65).
  * Each site's net exchange with the grid (import - export) comes from the
    annual EMS simulation of each strategy, at unity power factor (PV/BESS
    inverters) plus the 0.95 pf of the load portion.
"""
import warnings

import numpy as np
import pandas as pd
import pandapower as pp
import pandapower.networks as pn

import config as C
from ieee69 import case69

warnings.filterwarnings("ignore")

# [ASSUMPTION] normalised hourly shape of the existing (residential + commercial)
# feeder load, 1.0 = published IEEE peak bus load, evening peak at 19-21 h.
FEEDER_SHAPE = np.array([0.55, 0.50, 0.48, 0.47, 0.48, 0.55, 0.68, 0.78, 0.82, 0.80,
                         0.78, 0.77, 0.76, 0.75, 0.74, 0.76, 0.80, 0.88, 0.96, 1.00,
                         1.00, 0.93, 0.80, 0.65])
SITE_PF = 0.95


def get_net(name):
    if name == "IEEE 33-bus":
        net = pn.case33bw()
        buses = [b - 1 for b in C.SITE_BUSES_33]
    else:
        net = case69()
        buses = [b - 1 for b in C.SITE_BUSES_69]
    return net, buses


def radial_data(net):
    """Branch list in BFS order (parent before child), impedances in ohm."""
    lines = net.line[net.line.in_service]
    nb = len(net.bus)
    parent = -np.ones(nb, int)
    z = np.zeros(nb, complex)
    adj = {i: [] for i in range(nb)}
    for _, r in lines.iterrows():
        f, t = int(r.from_bus), int(r.to_bus)
        zz = (r.r_ohm_per_km + 1j * r.x_ohm_per_km) * r.length_km
        adj[f].append((t, zz)); adj[t].append((f, zz))
    slack = int(net.ext_grid.bus.iloc[0])
    order, seen, stack = [], {slack}, [slack]
    while stack:
        b = stack.pop(0)
        order.append(b)
        for nbh, zz in adj[b]:
            if nbh not in seen:
                seen.add(nbh); parent[nbh] = b; z[nbh] = zz; stack.append(nbh)
    return np.array(order), parent, z, slack


def bfs(net, P_kw, Q_kvar, tol=1e-8, it=50):
    """Backward/forward sweep. P_kw, Q_kvar: (n_bus, T). Returns V (pu, complex),
    losses (kW, T), branch current magnitude (A, n_bus x T, row = 'to' bus)."""
    order, parent, z, slack = radial_data(net)
    vn = net.bus.vn_kv.iloc[0] * 1e3
    Vph = vn / np.sqrt(3)
    S = (P_kw + 1j * Q_kvar) * 1e3 / 3                # per-phase VA
    V = np.full(S.shape, Vph, complex)
    for _ in range(it):
        I_load = np.conj(S / V)
        I_br = I_load.copy()
        for b in order[::-1]:                          # backward: sum currents
            if parent[b] >= 0:
                I_br[parent[b]] += I_br[b]
        V_new = V.copy()
        V_new[slack] = Vph
        for b in order:                                # forward: voltage drops
            if parent[b] >= 0:
                V_new[b] = V_new[parent[b]] - z[b] * I_br[b]
        if np.max(np.abs(V_new - V)) / Vph < tol:
            V = V_new
            break
        V = V_new
    I_load = np.conj(S / V)
    I_br = I_load.copy()
    for b in order[::-1]:
        if parent[b] >= 0:
            I_br[parent[b]] += I_br[b]
    I_br[slack] = 0
    loss = 3 * np.sum(np.abs(I_br) ** 2 * np.real(z)[:, None], axis=0) / 1e3
    return V / Vph, loss, np.abs(I_br)


def bus_injections(net, site_buses, site_net_kw, site_load_kw, hours):
    """Bus P/Q (kW/kVAr, n_bus x T) = scaled base loads + site net exchange."""
    nb = len(net.bus)
    T = len(hours)
    P = np.zeros((nb, T)); Q = np.zeros((nb, T))
    shape = FEEDER_SHAPE[hours]
    for _, r in net.load.iterrows():
        P[int(r.bus)] += r.p_mw * 1e3 * shape
        Q[int(r.bus)] += r.q_mvar * 1e3 * shape
    if site_net_kw is not None:
        q_site = site_load_kw * np.tan(np.arccos(SITE_PF))  # reactive part of loads
        for b in site_buses:
            P[b] += site_net_kw
            Q[b] += q_site
    return P, Q


def validate(name):
    """Base case at published peak load vs the published benchmark values."""
    net, _ = get_net(name)
    pp.runpp(net, numba=False)
    nb = len(net.bus)
    P = np.zeros((nb, 1)); Q = np.zeros((nb, 1))
    for _, r in net.load.iterrows():
        P[int(r.bus), 0] += r.p_mw * 1e3; Q[int(r.bus), 0] += r.q_mvar * 1e3
    V, loss, _ = bfs(net, P, Q)
    bench = {"IEEE 33-bus": (202.67, 0.9131, 18), "IEEE 69-bus": (224.95, 0.9092, 65)}[name]
    return dict(network=name,
                published_loss_kW=bench[0], pandapower_loss_kW=net.res_line.pl_mw.sum() * 1e3,
                our_BFS_loss_kW=loss[0],
                published_Vmin_pu=bench[1], pandapower_Vmin_pu=net.res_bus.vm_pu.min(),
                our_BFS_Vmin_pu=np.abs(V[:, 0]).min(),
                Vmin_bus=int(np.argmin(np.abs(V[:, 0]))) + 1)


def cross_check(name, site_net_kw, site_load_kw, hours, n=24):
    """Hour-by-hour pandapower vs BFS comparison on n snapshots."""
    net, buses = get_net(name)
    P, Q = bus_injections(net, buses, site_net_kw[:n], site_load_kw[:n], hours[:n])
    V, loss, _ = bfs(net, P, Q)
    rows = []
    for t in range(n):
        net2, _ = get_net(name)
        net2.load.drop(net2.load.index, inplace=True)
        for b in range(len(net2.bus)):
            if P[b, t] or Q[b, t]:
                pp.create_load(net2, b, p_mw=P[b, t] / 1e3, q_mvar=Q[b, t] / 1e3)
        pp.runpp(net2, numba=False)
        rows.append(dict(hour=t, pp_Vmin=net2.res_bus.vm_pu.min(), bfs_Vmin=np.abs(V[:, t]).min(),
                         pp_loss_kW=net2.res_line.pl_mw.sum() * 1e3, bfs_loss_kW=loss[t]))
    df = pd.DataFrame(rows)
    df["abs_dV_pu"] = (df.pp_Vmin - df.bfs_Vmin).abs()
    df["abs_dloss_kW"] = (df.pp_loss_kW - df.bfs_loss_kW).abs()
    return df


def annual_network(name, rec, L, w, strategies):
    """Run the whole year for each strategy. Returns summary table and
    per-strategy hourly min-voltage / losses."""
    net, buses = get_net(name)
    hours = w["hour"].to_numpy()
    load = L["load"].to_numpy()
    out, ts = [], {}
    cases = [("Base feeder (no new sites)", None)] + [(s, rec[s]) for s in strategies]
    for label, r in cases:
        site_net = None if r is None else (r["imp"] - r["exp"])
        P, Q = bus_injections(net, buses, site_net, load, hours)
        V, loss, Ibr = bfs(net, P, Q)
        vm = np.abs(V)
        vmin_t = vm.min(axis=0)
        sub_kw = P.sum(axis=0) + loss
        ts[label] = dict(vmin=vmin_t, loss=loss, sub_kw=sub_kw, v_at_peak=vm[:, np.argmin(vmin_t)])
        out.append({
            "case": label,
            "lowest_voltage_pu": vmin_t.min(),
            "hours_below_0.91pu": int(np.sum(vmin_t < C.VOLT_MIN_PU)),
            "bus_hours_below_0.91pu": int(np.sum(vm < C.VOLT_MIN_PU)),
            "bus_hours_below_0.95pu": int(np.sum(vm < C.VOLT_PLAN_PU)),
            "annual_losses_MWh": loss.sum() / 1e3,
            "peak_losses_kW": loss.max(),
            "substation_peak_kW": sub_kw.max(),
            "max_branch_current_A": Ibr.max(),
        })
    return pd.DataFrame(out).set_index("case"), ts
