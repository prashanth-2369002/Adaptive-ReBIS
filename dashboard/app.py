"""
Adaptive-ReBIS live dashboard.   Run:  py -m streamlit run dashboard/app.py

Pick any day of 2020, any PV / battery size and an optimiser; the EMS runs
live (ML forecast -> GA / PSO / LP day-ahead plan -> real-time correction
against the actual day) and the result is load-flowed on the IEEE 33/69-bus
feeder. Needs results/_stage_data.pkl and _stage_forecast.pkl (run_all.py).
"""
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import config as C          # noqa: E402
import ems                  # noqa: E402
import grid_ieee as G       # noqa: E402

BLUE, ORANGE, AQUA, YELLOW, VIOLET, RED, MUTED, INK = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#4a3aa7", "#e34948", "#8a8984", "#0b0b0b")

st.set_page_config(page_title="Adaptive-ReBIS EMS", layout="wide")


@st.cache_data
def load_data():
    w, L = pickle.loads((C.RESULTS_DIR / "_stage_data.pkl").read_bytes())
    _, best, fc, _, _ = pickle.loads((C.RESULTS_DIR / "_stage_forecast.pkl").read_bytes())
    return w, L, fc, best


w, L, fc, fbest = load_data()

# ------------------------------------------------------------------ sidebar
st.sidebar.title("Adaptive-ReBIS")
st.sidebar.caption("Renewable + Battery Integrated EMS for EV charging and appliance loads")
date = st.sidebar.date_input("Day to simulate (2020)", value=pd.Timestamp("2020-05-15"),
                             min_value=pd.Timestamp("2020-01-02"), max_value=pd.Timestamp("2020-12-31"))
day = int(pd.Timestamp(date).dayofyear) - 1
pv_kwp = st.sidebar.slider("PV size (kWp)", 0, 400, 300, 10)
bess = st.sidebar.slider("Battery size (kWh)", 0, 400, 200, 10)
wind = st.sidebar.slider("Wind turbine (kW)", 0, 100, 0, 5)
alg = st.sidebar.radio("Day-ahead optimiser", ["PSO", "GA", "LP (exact)", "Rule-based only"], index=0)
focus = st.sidebar.select_slider("Priority", ["Lowest bill", "Balanced (adaptive)", "Lowest grid peak"],
                                 value="Balanced (adaptive)")
soc0 = st.sidebar.slider("Battery SOC at midnight (%)", 20, 95, 50) / 100
use_forecast = st.sidebar.toggle("Plan on ML forecast (off = perfect foresight)", value=True)

# priority preset -> adaptive hourly weights (cost, peak, CO2)
presets = {
    "Lowest bill": ((0.7, 0.2, 0.1), (0.8, 0.05, 0.15), (0.85, 0.05, 0.1)),
    "Balanced (adaptive)": (C.W_PEAK_HOURS, C.W_NORMAL_HOURS, C.W_OFFPEAK_HOURS),
    "Lowest grid peak": ((0.15, 0.8, 0.05), (0.3, 0.55, 0.15), (0.5, 0.4, 0.1)),
}
C.W_PEAK_HOURS, C.W_NORMAL_HOURS, C.W_OFFPEAK_HOURS = presets[focus]
ems.WC, ems.WE, ems.PHI, ems.WP = ems.hourly_weights()

# ------------------------------------------------------------------ simulate the day
site = ems.Site(pv_kwp, bess, wind)
sl = slice(24 * day, 24 * day + 24)
load = L["load"].to_numpy()[sl]
ren = pv_kwp * w["pv_kw_per_kwp"].to_numpy()[sl] + wind * w["wind_kw_per_kw"].to_numpy()[sl]
ren_fc = pv_kwp * fc["pv_fc_per_kwp"].to_numpy()[sl] + wind * w["wind_kw_per_kw"].to_numpy()[sl.start - 24:sl.stop - 24]
load_fc = fc["load_fc"].to_numpy()[sl]
net_a = load - ren
net_f = (load_fc - ren_fc) if use_forecast else net_a
tar = w["tariff"].to_numpy()[sl]
rng = np.random.default_rng(1)

t0 = time.perf_counter()
seeds = [ems.rule_based_request(net_f, site), np.zeros(24)]
if alg == "PSO":
    plan, hist = ems.pso(net_f, tar, soc0, site, rng, seeds=seeds)
elif alg == "GA":
    plan, hist = ems.ga(net_f, tar, soc0, site, rng, seeds=seeds)
elif alg == "LP (exact)":
    plan, _ = ems.lp(net_f, tar, soc0, site)
    hist = None
else:
    plan, hist = None, None
solve_ms = (time.perf_counter() - t0) * 1000

if plan is None:
    run = ems.execute_plain(ems.rule_based_request(net_a, site), net_a, soc0, site)
else:
    run = ems.realtime_execute(plan, net_f, net_a, soc0, site) if use_forecast \
        else ems.execute_plain(plan, net_a, soc0, site)
rule = ems.execute_plain(ems.rule_based_request(net_a, site), net_a, soc0, site)
grid_only = ems.execute_plain(np.zeros(24), load, 0.5, ems.Site(0, 0, 0))


def kpis(r):
    cost = np.sum(r["imp"] * tar) - np.sum(r["exp"]) * C.EXPORT_PRICE + np.sum(np.maximum(r["x"], 0)) * C.BESS_DEG_COST
    return cost, r["imp"].max(), r["imp"].sum() * C.GRID_CO2, r["imp"][np.isin(np.arange(24), C.PEAK_HOURS)].sum()


k_run, k_rule, k_grid = kpis(run), kpis(rule), kpis(grid_only)

st.title(f"Adaptive-ReBIS: {pd.Timestamp(date):%A %d %B %Y}")
st.caption(f"{C.CITY}  |  real PVGIS weather  |  TGERC ToD tariff  |  CEA CO2 {C.GRID_CO2} kg/kWh  |  "
           f"forecast model: {fbest}  |  optimiser time {solve_ms:.0f} ms")

c = st.columns(4)
names = ["Day energy cost (Rs)", "Peak grid draw (kW)", "Grid CO2 (kg)", "Grid energy in ToD peak (kWh)"]
for i, col in enumerate(c):
    col.metric(names[i], f"{k_run[i]:,.0f}",
               f"{100*(k_run[i]/k_grid[i]-1):+.1f} % vs grid only" if k_grid[i] else None, delta_color="inverse")
    col.caption(f"Rule-based ReBIS: {k_rule[i]:,.0f}  |  Grid only: {k_grid[i]:,.0f}")

st.info(f"End-of-day battery SOC: Adaptive-ReBIS {100*run['soc'][-1]:.0f} %, rule-based {100*rule['soc'][-1]:.0f} %. "
        "Adaptive-ReBIS always refills to at least 50 % for tomorrow's morning peak, so compare costs over the "
        "year (Annual results tab), not one day.")

tab1, tab2, tab3, tab4 = st.tabs(["Power sharing", "IEEE feeder", "Forecast", "Annual results"])

with tab1:
    h = np.arange(24)
    x = run["x"]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.5, 0.22, 0.28], vertical_spacing=0.05,
                        subplot_titles=("Power sharing (kW)", "Battery SOC (%)", "Grid import (kW)"))
    fig.add_bar(x=h, y=np.minimum(ren, load), name="Renewables to load", marker_color=YELLOW, row=1, col=1)
    fig.add_bar(x=h, y=np.maximum(x, 0), name="Battery discharge", marker_color=AQUA, row=1, col=1)
    fig.add_bar(x=h, y=run["imp"], name="Grid import", marker_color=MUTED, row=1, col=1)
    fig.add_bar(x=h, y=-np.maximum(-x, 0), name="Battery charging", marker_color=BLUE, row=1, col=1)
    fig.add_bar(x=h, y=-run["exp"], name="Export", marker_color=ORANGE, row=1, col=1)
    fig.add_scatter(x=h, y=load, name="Actual load", line=dict(color=INK, width=2), row=1, col=1)
    fig.add_scatter(x=h, y=load_fc, name="Forecast load", line=dict(color=INK, width=1.5, dash="dot"), row=1, col=1)
    fig.add_scatter(x=h, y=100 * run["soc"], name=f"SOC ({alg})", line=dict(color=BLUE, width=2), row=2, col=1)
    fig.add_scatter(x=h, y=100 * rule["soc"], name="SOC (rule-based)", line=dict(color=ORANGE, width=2), row=2, col=1)
    fig.add_scatter(x=h, y=grid_only["imp"], name="Grid only", line=dict(color=MUTED, width=2), row=3, col=1)
    fig.add_scatter(x=h, y=rule["imp"], name="Rule-based ReBIS", line=dict(color=ORANGE, width=2), row=3, col=1)
    fig.add_scatter(x=h, y=run["imp"], name=f"Adaptive-ReBIS ({alg})", line=dict(color=BLUE, width=2.5), row=3, col=1)
    for a, b in ((6, 10), (18, 22)):
        for r in (1, 2, 3):
            fig.add_vrect(x0=a - 0.5, x1=b - 0.5, fillcolor="#f0efec", line_width=0, layer="below", row=r, col=1)
    fig.update_layout(barmode="relative", height=760, hovermode="x unified", template="plotly_white",
                      legend=dict(orientation="h", y=-0.08), margin=dict(t=40, b=10))
    fig.update_xaxes(title_text="Hour of day (shaded = ToD peak tariff)", row=3, col=1, dtick=2)
    st.plotly_chart(fig, use_container_width=True)
    if hist is not None and len(hist) > 1:
        st.caption(f"{alg} convergence")
        st.line_chart(pd.Series(hist, name="best objective"), height=180)

with tab2:
    netname = st.radio("Feeder", ["IEEE 33-bus", "IEEE 69-bus"], horizontal=True)
    net, buses = G.get_net(netname)
    hours = w["hour"].to_numpy()[sl]
    res = {}
    for lab, r in (("Base feeder", None), ("Grid only", grid_only), ("Rule-based ReBIS", rule),
                   (f"Adaptive-ReBIS ({alg})", run)):
        P, Q = G.bus_injections(net, buses, None if r is None else r["imp"] - r["exp"], load, hours)
        V, loss, _ = G.bfs(net, P, Q)
        res[lab] = (np.abs(V), loss)
    tw = int(np.argmin(res["Grid only"][0].min(axis=0)))
    cols = {"Base feeder": INK, "Grid only": MUTED, "Rule-based ReBIS": ORANGE, f"Adaptive-ReBIS ({alg})": BLUE}
    f1 = go.Figure()
    for lab, (V, loss) in res.items():
        f1.add_scatter(x=np.arange(1, V.shape[0] + 1), y=V[:, tw], name=lab, line=dict(color=cols[lab], width=2))
    f1.add_hline(y=C.VOLT_MIN_PU, line=dict(color=RED, dash="dash"), annotation_text="0.91 pu (-9 % limit)")
    f1.update_layout(title=f"Bus voltages at {tw}:00 (worst hour of the day), sites at buses "
                           f"{', '.join(str(b + 1) for b in buses)}",
                     xaxis_title="Bus", yaxis_title="Voltage (pu)", template="plotly_white", height=420)
    st.plotly_chart(f1, use_container_width=True)
    f2 = go.Figure()
    for lab, (V, loss) in res.items():
        f2.add_scatter(x=np.arange(24), y=V.min(axis=0), name=lab, line=dict(color=cols[lab], width=2))
    f2.add_hline(y=C.VOLT_MIN_PU, line=dict(color=RED, dash="dash"))
    f2.update_layout(title="Lowest feeder voltage, hour by hour", xaxis_title="Hour", yaxis_title="pu",
                     template="plotly_white", height=340)
    st.plotly_chart(f2, use_container_width=True)
    st.dataframe(pd.DataFrame({lab: {"lowest voltage (pu)": V.min(), "hours below 0.91 pu": int((V.min(0) < 0.91).sum()),
                                     "feeder losses (kWh/day)": loss.sum()} for lab, (V, loss) in res.items()}).T.round(4))

with tab3:
    sl2 = slice(max(0, 24 * (day - 3)), 24 * (day + 4))
    f3 = go.Figure()
    f3.add_scatter(x=fc.index[sl2], y=fc["load_actual"].to_numpy()[sl2], name="Actual", line=dict(color=INK))
    f3.add_scatter(x=fc.index[sl2], y=fc["load_fc"].to_numpy()[sl2], name=f"ML forecast ({fbest})", line=dict(color=BLUE))
    f3.add_scatter(x=fc.index[sl2], y=fc["fc_Persistence (yesterday)"].to_numpy()[sl2], name="Persistence",
                   line=dict(color=ORANGE, dash="dash"))
    f3.update_layout(template="plotly_white", height=380, yaxis_title="kW", title="Day-ahead forecast, one week around the chosen day")
    st.plotly_chart(f3, use_container_width=True)
    p = C.RESULTS_DIR / "forecast_model_comparison.csv"
    if p.exists():
        st.dataframe(pd.read_csv(p).round(3))

with tab4:
    for f in ("strategy_comparison_designA.csv", "strategy_comparison_designB.csv", "sizing_optimum.csv",
              "network_33-bus_designB.csv", "network_69-bus_designB.csv", "reliability_outage_monte_carlo.csv"):
        p = C.RESULTS_DIR / f
        if p.exists():
            st.subheader(f)
            st.dataframe(pd.read_csv(p).round(2))
