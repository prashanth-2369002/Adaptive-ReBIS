"""
figures.py -- every figure for the report / review deck (results/figures/).
Called at the end of run_all.py with that script's results.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

import config as C
import grid_ieee as G

INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
SCOL = {"S0 Grid only": MUTED, "S1 PV + grid": YELLOW, "S2 Rule-based ReBIS": ORANGE,
        "S3 Adaptive-ReBIS (GA)": VIOLET, "S4 Adaptive-ReBIS (PSO)": BLUE,
        "S5 LP on forecast": AQUA, "S6 Perfect-foresight LP": GREEN,
        "Base feeder (no new sites)": INK}
SHORT = {"S0 Grid only": "Grid only", "S1 PV + grid": "PV + grid", "S2 Rule-based ReBIS": "Rule-based ReBIS",
         "S3 Adaptive-ReBIS (GA)": "Adaptive-ReBIS (GA)", "S4 Adaptive-ReBIS (PSO)": "Adaptive-ReBIS (PSO)",
         "S5 LP on forecast": "LP on forecast", "S6 Perfect-foresight LP": "Perfect foresight (bound)",
         "Base feeder (no new sites)": "Base feeder (no new sites)"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.edgecolor": MUTED, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "lines.linewidth": 2.0, "legend.frameon": False, "figure.dpi": 150, "savefig.dpi": 150,
    "savefig.bbox": "tight", "figure.facecolor": "white",
})


def save(fig, name):
    fig.savefig(C.FIG_DIR / name)
    plt.close(fig)
    print("  figure", name)


def shade_peaks(ax, hours=None):
    for a, b in ((6, 10), (18, 22)):
        ax.axvspan(a - 0.5, b - 0.5, color="#f0efec", zorder=0, lw=0)


# ---------------------------------------------------------------- 1 resource
def fig_resource(w):
    m = w.groupby("month")
    fig, axs = plt.subplots(1, 3, figsize=(13, 3.8))
    axs[0].bar(m.groups.keys(), m.pv_kw_per_kwp.sum(), color=BLUE, width=0.7)
    axs[0].set_title("PV yield, kWh per kWp per month")
    axs[1].plot(list(m.groups.keys()), m.temp_c.max(), color=RED, marker="o", ms=5, label="monthly max")
    axs[1].plot(list(m.groups.keys()), m.temp_c.mean(), color=ORANGE, marker="o", ms=5, label="monthly mean")
    axs[1].set_title("Air temperature, deg C")
    axs[1].legend(loc="lower center")
    axs[2].bar(m.groups.keys(), 100 * m.wind_kw_per_kw.mean(), color=AQUA, width=0.7)
    axs[2].set_title("Wind turbine capacity factor, %")
    for a in axs:
        a.set_xticks(range(1, 13)); a.set_xticklabels("JFMAMJJASOND")
    fig.suptitle(f"Real hourly resource data: PVGIS-ERA5 2020, {C.CITY}  "
                 f"(PV {w.pv_kw_per_kwp.sum():.0f} kWh/kWp/yr, wind CUF {100*w.wind_kw_per_kw.mean():.1f} %)",
                 x=0.01, ha="left", fontsize=12, color=INK2)
    fig.tight_layout()
    save(fig, "fig01_resource_data.png")


# ---------------------------------------------------------------- 2 load
def fig_load(L, w):
    wk = L[w["dow"] < 5].groupby(L[w["dow"] < 5].index.hour).mean()
    fig, ax = plt.subplots(figsize=(11, 4.6))
    shade_peaks(ax)
    cols = [("general", "General appliances", YELLOW), ("water_heater", "Water heaters", AQUA),
            ("hvac", "HVAC", ORANGE), ("ev", "EV charging hub", BLUE)]
    base = np.zeros(24)
    for key, lab, c in cols:
        ax.bar(range(24), wk[key], bottom=base, color=c, width=0.92, edgecolor="white", linewidth=1, label=lab)
        base += wk[key].to_numpy()
    ax.set_xticks(range(0, 24, 2)); ax.set_xlabel("Hour of day (IST)"); ax.set_ylabel("kW")
    ax.set_title(f"Average weekday site demand by load type  (annual {L['load'].sum()/1e3:.0f} MWh, "
                 f"peak {L['load'].max():.0f} kW)")
    h, l = ax.get_legend_handles_labels()
    ax.legend(h[::-1], l[::-1], loc="upper left")
    ax.text(7.5, base.max() * 1.02, "ToD peak", ha="center", color=INK2, fontsize=9)
    ax.text(19.5, base.max() * 1.02, "ToD peak", ha="center", color=INK2, fontsize=9)
    save(fig, "fig02_site_load_profile.png")


# ---------------------------------------------------------------- 3 forecast
def fig_forecast(fc, ftable, fbest):
    fig, axs = plt.subplots(1, 2, figsize=(14, 4.6), gridspec_kw=dict(width_ratios=[1.7, 1]))
    sl = slice(24 * 320, 24 * 330)
    t = np.arange(240) / 24
    axs[0].plot(t, fc["load_actual"].to_numpy()[sl], color=INK, lw=1.6, label="Actual")
    axs[0].plot(t, fc["fc_" + fbest].to_numpy()[sl], color=BLUE, label=f"ML forecast ({fbest})")
    axs[0].plot(t, fc["fc_Persistence (yesterday)"].to_numpy()[sl], color=ORANGE, lw=1.2, ls="--",
                label="Persistence (yesterday)")
    axs[0].set_xlabel("Day (16-25 Nov 2020, out-of-sample)"); axs[0].set_ylabel("Site load, kW")
    axs[0].set_title("Day-ahead hourly load forecast")
    axs[0].legend(loc="upper left", ncol=3, fontsize=9)
    tb = ftable.sort_values("MAPE_pct", ascending=False)
    colors = [BLUE if i == fbest else ("#b7d3f6" if "naive" not in i.lower() and "Persistence" not in i else GRID)
              for i in tb.index]
    axs[1].barh(range(len(tb)), tb["MAPE_pct"], color=colors, height=0.6)
    axs[1].set_yticks(range(len(tb))); axs[1].set_yticklabels(tb.index, fontsize=10)
    for i, (mape, r2) in enumerate(zip(tb["MAPE_pct"], tb["R2"])):
        axs[1].text(mape + 0.3, i, f"{mape:.1f} %  (R2 {r2:.2f})", va="center", fontsize=9, color=INK2)
    axs[1].set_xlim(0, tb["MAPE_pct"].max() * 1.45)
    axs[1].set_title("MAPE, 12-fold month-blocked CV\n(dark = model fed to the EMS: lowest RMSE)", fontsize=11)
    axs[1].grid(axis="y", visible=False)
    fig.tight_layout()
    save(fig, "fig03_load_forecast.png")


# ---------------------------------------------------------------- 4 sizing
def fig_sizing(size_hg, size_hp, size_sens, size_tab):
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.4))
    axs[0].plot(size_hg, color=VIOLET, label="Genetic Algorithm")
    axs[0].plot(size_hp, color=BLUE, ls="--", label="Particle Swarm")
    axs[0].set_xlabel("Generation / iteration"); axs[0].set_ylabel("Total annual cost, Rs lakh")
    axs[0].set_title("Sizing convergence (40 candidates per step)")
    axs[0].legend()
    g = size_tab[size_tab.algorithm == "PSO"].iloc[0]
    axs[0].text(len(size_hp) - 1, size_hp[-1] + 0.15,
                f"Both converge to: PV {g.pv_kWp:.0f} kWp, BESS {g.bess_kWh:.0f} kWh, wind {g.wind_kW:.0f} kW\n"
                f"total {size_hp[-1]:.2f} lakh/yr", ha="right", va="bottom", fontsize=10, color=INK2)
    s = size_sens
    axs[1].bar(range(len(s)), s.bess_kWh, color=BLUE, width=0.6)
    axs[1].set_xticks(range(len(s)))
    axs[1].set_xticklabels([f"Rs {p/1000:.0f}k" for p in s.bess_price_Rs_per_kWh])
    for i, v in enumerate(s.bess_kWh):
        axs[1].text(i, v + 2, f"{v:.0f}", ha="center", fontsize=10, color=INK2)
    axs[1].set_xlabel("Installed battery price per kWh"); axs[1].set_ylabel("Optimal battery, kWh")
    axs[1].set_title("Optimal battery size vs battery price (PSO)")
    axs[1].grid(axis="x", visible=False)
    fig.tight_layout()
    save(fig, "fig04_sizing_GA_PSO.png")


# ---------------------------------------------------------------- 5 dispatch day
def fig_dispatch_day(w, L, rec, site, day=135):
    sl = slice(24 * day, 24 * day + 24)
    h = np.arange(24)
    load = L["load"].to_numpy()[sl]
    pv = site.pv_kwp * w["pv_kw_per_kwp"].to_numpy()[sl]
    fig, axs = plt.subplots(3, 1, figsize=(11, 9.5), sharex=True,
                            gridspec_kw=dict(height_ratios=[1.4, 0.8, 1.1]))
    r = {k: v[sl] for k, v in rec["S4 Adaptive-ReBIS (PSO)"].items()}
    x = r["x"]
    shade_peaks(axs[0])
    axs[0].bar(h, np.minimum(pv, load), color=YELLOW, width=0.9, label="PV to load")
    axs[0].bar(h, np.maximum(x, 0), bottom=np.minimum(pv, load), color=AQUA, width=0.9, label="Battery discharge")
    axs[0].bar(h, r["imp"], bottom=np.minimum(pv, load) + np.maximum(x, 0), color=MUTED, width=0.9, label="Grid import")
    axs[0].bar(h, -np.maximum(-x, 0), color=BLUE, width=0.9, label="Battery charging (-)")
    axs[0].bar(h, -r["exp"], bottom=-np.maximum(-x, 0), color=ORANGE, width=0.9, label="Export (-)")
    axs[0].plot(h, load, color=INK, lw=1.8, marker="o", ms=3, label="Site load")
    axs[0].axhline(0, color=INK2, lw=0.8)
    axs[0].set_ylabel("kW")
    axs[0].set_title(f"Adaptive-ReBIS (PSO) power sharing, {w.index[24*day]:%d %b %Y} "
                     f"(PV {site.pv_kwp:.0f} kWp, BESS {site.bess_kwh:.0f} kWh)")
    axs[0].legend(ncol=3, fontsize=9, loc="upper left")
    shade_peaks(axs[1])
    for s in ("S2 Rule-based ReBIS", "S4 Adaptive-ReBIS (PSO)"):
        axs[1].plot(h, 100 * rec[s]["soc"][sl], color=SCOL[s], label=SHORT[s], marker="o", ms=3)
    axs[1].set_ylabel("Battery SOC, %"); axs[1].set_ylim(0, 110)
    axs[1].legend(fontsize=9, loc="upper left", ncol=2)
    shade_peaks(axs[2])
    for s in ("S0 Grid only", "S2 Rule-based ReBIS", "S4 Adaptive-ReBIS (PSO)"):
        axs[2].plot(h, rec[s]["imp"][sl], color=SCOL[s], label=f"{SHORT[s]} (peak {rec[s]['imp'][sl].max():.0f} kW)",
                    marker="o", ms=3)
    axs[2].set_ylabel("Grid import, kW"); axs[2].set_xlabel("Hour of day (IST); shaded = ToD peak tariff")
    axs[2].legend(fontsize=9, loc="upper left")
    axs[2].set_xticks(range(0, 24, 2))
    fig.tight_layout()
    save(fig, "fig05_dispatch_day.png")


# ---------------------------------------------------------------- 6 strategies
def fig_strategies(m, design_label, name):
    order = ["S0 Grid only", "S1 PV + grid", "S2 Rule-based ReBIS", "S3 Adaptive-ReBIS (GA)",
             "S4 Adaptive-ReBIS (PSO)", "S5 LP on forecast", "S6 Perfect-foresight LP"]
    m = m.loc[order]
    cols = [("net_operating_cost_Rs_lakh", "Net operating cost, Rs lakh/yr"),
            ("mean_daily_peak_kW", "Mean daily peak grid draw, kW"),
            ("peak_window_import_MWh", "Grid energy in ToD peak hours, MWh/yr"),
            ("CO2_tonnes", "Grid CO2, tonnes/yr")]
    fig, axs = plt.subplots(1, 4, figsize=(16, 4.6), sharey=True)
    for a, (c, t) in zip(axs, cols):
        v = m[c].to_numpy()
        a.barh(range(len(m)), v, color=[SCOL[s] for s in order], height=0.62)
        for i, val in enumerate(v):
            a.text(val + v.max() * 0.01, i, f"{val:.1f}", va="center", fontsize=9, color=INK2)
        a.set_title(t, fontsize=11)
        a.set_xlim(0, v.max() * 1.22)
        a.grid(axis="y", visible=False)
    axs[0].set_yticks(range(len(m))); axs[0].set_yticklabels([SHORT[s] for s in order])
    axs[0].invert_yaxis()
    fig.suptitle(f"Annual comparison of dispatch strategies, {design_label}", x=0.01, ha="left",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    save(fig, name)


# ---------------------------------------------------------------- 7 optimality
def fig_optimality(optim, conv):
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.2))
    bins = np.linspace(0, max(optim.gap_GA_pct.max(), optim.gap_PSO_pct.max()) + 0.25, 30)
    axs[0].hist(optim.gap_GA_pct, bins=bins, color=VIOLET, alpha=0.85, label=f"GA (mean {optim.gap_GA_pct.mean():.2f} %)")
    axs[0].hist(optim.gap_PSO_pct, bins=bins, color=BLUE, alpha=0.6, label=f"PSO (mean {optim.gap_PSO_pct.mean():.2f} %)")
    axs[0].set_xlabel("Gap to exact LP optimum, %"); axs[0].set_ylabel("Days")
    axs[0].set_title("Solution quality, 366 days"); axs[0].legend()
    impr = 100 * (1 - optim[["J_GA", "J_PSO", "J_LP"]].div(optim.J_none, axis=0))
    axs[1].boxplot([impr.J_GA, impr.J_PSO, impr.J_LP], tick_labels=["GA", "PSO", "LP (exact)"],
                   widths=0.5, medianprops=dict(color=INK), flierprops=dict(markersize=3))
    axs[1].set_ylabel("Objective improvement vs no battery, %")
    axs[1].set_title("Daily objective improvement")
    d = 135
    axs[2].plot(conv["GA"][d], color=VIOLET, label="GA best")
    axs[2].plot(conv["PSO"][d], color=BLUE, ls="--", label="PSO global best")
    axs[2].set_xlabel("Generation / iteration"); axs[2].set_ylabel("Objective J")
    axs[2].set_title("Convergence, 15 May (peak day)"); axs[2].legend()
    fig.tight_layout()
    save(fig, "fig07_GA_PSO_vs_LP.png")


# ---------------------------------------------------------------- 8/9 network
def fig_network(net_res, dispatch, L, w, design="B"):
    strats = ["Base feeder (no new sites)", "S0 Grid only", "S2 Rule-based ReBIS", "S4 Adaptive-ReBIS (PSO)"]
    rec = dispatch[design][0]
    load = L["load"].to_numpy()
    hours = w["hour"].to_numpy()
    fig, axs = plt.subplots(1, 2, figsize=(14, 4.6))
    for a, n in zip(axs, ("IEEE 33-bus", "IEEE 69-bus")):
        tab, ts = net_res[(design, n)]
        t_worst = int(np.argmin(ts["S0 Grid only"]["vmin"]))
        net, buses = G.get_net(n)
        for s in strats:
            site_net = None if s.startswith("Base") else (rec[s]["imp"] - rec[s]["exp"])[[t_worst]]
            P, Q = G.bus_injections(net, buses, site_net, load[[t_worst]], hours[[t_worst]])
            V, _, _ = G.bfs(net, P, Q)
            a.plot(np.arange(1, len(net.bus) + 1), np.abs(V[:, 0]), color=SCOL[s], label=SHORT[s],
                   lw=1.6 if s.startswith("Base") else 2.0, ls=":" if s.startswith("Base") else "-")
        a.axhline(C.VOLT_MIN_PU, color=RED, lw=1.2, ls="--")
        a.text(1.5, C.VOLT_MIN_PU + 0.002, "0.91 pu limit (-9 %)", color=RED, fontsize=9)
        for b in buses:
            a.axvline(b + 1, color=GRID, lw=1, zorder=0)
        a.set_xlabel("Bus number (grey lines = Adaptive-ReBIS sites)"); a.set_ylabel("Voltage, pu")
        a.set_title(f"{n}: voltage profile at the worst hour ({w.index[t_worst]:%d %b %H:00})", fontsize=11)
    axs[0].legend(fontsize=9, loc="lower left")
    fig.tight_layout()
    save(fig, f"fig08_network_voltage_profile_design{design}.png")

    fig, axs = plt.subplots(1, 2, figsize=(14, 4.4))
    for a, n in zip(axs, ("IEEE 33-bus", "IEEE 69-bus")):
        tab, ts = net_res[(design, n)]
        for s in strats:
            v = np.sort(ts[s]["vmin"])
            a.plot(np.arange(len(v)) / len(v) * 100, v, color=SCOL[s], label=SHORT[s],
                   ls=":" if s.startswith("Base") else "-")
        a.axhline(C.VOLT_MIN_PU, color=RED, lw=1.2, ls="--")
        a.set_xlim(0, 30)
        a.set_xlabel("% of hours in the year"); a.set_ylabel("Lowest bus voltage, pu")
        a.set_title(f"{n}: duration curve of the feeder's lowest voltage", fontsize=11)
    axs[0].legend(fontsize=9, loc="lower right")
    fig.tight_layout()
    save(fig, f"fig09_network_voltage_duration_design{design}.png")


# ---------------------------------------------------------------- 10 battery
def fig_battery(batt):
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.2))
    for s in ("S2 Rule-based ReBIS", "S4 Adaptive-ReBIS (PSO)"):
        d = batt[batt.strategy == s]
        axs[0].plot(d.bess_kWh, d.mean_daily_peak_kW, color=SCOL[s], marker="o", ms=6, label=SHORT[s])
        axs[1].plot(d.bess_kWh, d.net_operating_cost_Rs_lakh, color=SCOL[s], marker="o", ms=6, label=SHORT[s])
        axs[2].plot(d.bess_kWh, d.CO2_tonnes, color=SCOL[s], marker="o", ms=6, label=SHORT[s])
    axs[0].set_title("Mean daily peak grid draw, kW"); axs[1].set_title("Net operating cost, Rs lakh/yr")
    axs[2].set_title("Grid CO2, tonnes/yr")
    for a in axs:
        a.set_xlabel("Battery size, kWh")
    axs[0].legend()
    fig.tight_layout()
    save(fig, "fig10_battery_size_sensitivity.png")


# ---------------------------------------------------------------- 11 architecture
def fig_architecture():
    fig, ax = plt.subplots(figsize=(14, 6.2))
    ax.set_xlim(0, 14); ax.set_ylim(0, 6.2); ax.axis("off")

    def box(x, y, w, h, title, body, edge):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc="white", ec=edge, lw=2))
        ax.text(x + 0.15, y + h - 0.28, title, fontsize=11.5, fontweight="bold", color=INK, va="top")
        ax.text(x + 0.15, y + h - 0.68, body, fontsize=9.2, color=INK2, va="top", linespacing=1.35)

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.5))

    box(0.2, 3.5, 3.0, 2.4, "1  Data layer", "PVGIS-ERA5 2020 hourly PV,\ntemperature, wind (Hyderabad)\nTGERC ToD tariff\nCEA CO2 factor 0.716 kg/kWh\nEV / HVAC / geyser / general\nload model (8784 h)", MUTED)
    box(3.7, 3.5, 3.0, 2.4, "2  ML forecast", "Next-day hourly demand\nRidge / RF / GBM / MLP\nmonth-blocked CV\nPV: 3-day smart persistence", BLUE)
    box(7.2, 3.5, 3.2, 2.4, "3  Day-ahead optimiser", "Adaptive weights per hour\n(cost / peak / CO2)\nGA  and  PSO  -> 24 h battery\nschedule; LP = exact check\nGA/PSO also size PV/BESS/wind", VIOLET)
    box(10.9, 3.5, 2.9, 2.4, "4  Real-time control", "Follows plan; in ToD peak\nholds grid draw at plan;\nsoaks unforecast PV surplus;\npeak guard every hour", AQUA)
    box(3.7, 0.6, 4.4, 2.0, "5  Site (PCC)", "PV -> load first; battery charges\nfrom surplus, discharges by SOC;\ngrid covers deficit / takes export\nEV hub 8x7.4 kW AC + 2x30 kW DC", ORANGE)
    box(8.6, 0.6, 5.2, 2.0, "6  Network validation + KPIs", "IEEE 33-bus and 69-bus load flow\n(pandapower + own BFS, 5 sites)\nvoltage, losses, substation peak\ncost, peak demand, CO2, reliability", GREEN)
    arrow(3.2, 4.7, 3.7, 4.7); arrow(6.7, 4.7, 7.2, 4.7); arrow(10.4, 4.7, 10.9, 4.7)
    arrow(12.3, 3.5, 7.0, 2.6); arrow(8.1, 1.6, 8.6, 1.6)
    arrow(1.7, 3.5, 3.9, 2.6)
    ax.text(0.2, 0.1, "Repeated every day of the year; battery SOC carries over day to day.",
            fontsize=9, color=MUTED)
    save(fig, "fig00_system_architecture.png")


def make_all(g):
    fig_architecture()
    fig_resource(g["w"])
    fig_load(g["L"], g["w"])
    fig_forecast(g["fc"], g["ftable"], g["fbest"])
    fig_sizing(g["size_hg"], g["size_hp"], g["size_sens"], g["size_tab"])
    rec_b, conv_b, m_b = g["dispatch"]["B"]
    rec_a, conv_a, m_a = g["dispatch"]["A"]
    fig_dispatch_day(g["w"], g["L"], rec_b, g["DESIGNS"]["B"])
    sa, sb = g["DESIGNS"]["A"], g["DESIGNS"]["B"]
    fig_strategies(m_a, f"Design A (economic optimum: PV {sa.pv_kwp:.0f} kWp, BESS {sa.bess_kwh:.0f} kWh)",
                   "fig06a_strategy_comparison_designA.png")
    fig_strategies(m_b, f"Design B (grid support: PV {sb.pv_kwp:.0f} kWp, BESS {sb.bess_kwh:.0f} kWh)",
                   "fig06b_strategy_comparison_designB.png")
    fig_optimality(g["optim"], conv_b)
    for d in ("A", "B"):
        fig_network(g["net_res"], g["dispatch"], g["L"], g["w"], d)
    fig_battery(g["batt"])
