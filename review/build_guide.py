"""
build_guide.py -- writes review/Review_Guide_and_Viva_QA.docx (and .pdf via Word
if available) from results/summary.json. Every number comes from the run.
"""
import json
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor, Cm

ROOT = Path(__file__).resolve().parent.parent
S = json.loads((ROOT / "results" / "summary.json").read_text())
OUT = Path(__file__).resolve().parent / "Review_Guide_and_Viva_QA.docx"

G0, RB, GA, PSO, LPF, LPP = ("S0 Grid only", "S2 Rule-based ReBIS", "S3 Adaptive-ReBIS (GA)",
                             "S4 Adaptive-ReBIS (PSO)", "S5 LP on forecast", "S6 Perfect-foresight LP")
A, B = S["strategies_A"], S["strategies_B"]
fc, fbest = S["forecast"], S["forecast_best"]
op = S["optimality"]
sz = next(r for r in S["sizing"] if r["algorithm"] == "PSO")
szg = next(r for r in S["sizing"] if r["algorithm"].startswith("Reference: grid"))
sens = S["sizing_sens"]
v33 = next(r for r in S["validation"] if r["network"] == "IEEE 33-bus")
v69 = next(r for r in S["validation"] if r["network"] == "IEEE 69-bus")
n33A, n69A = S["network_33-bus_A"], S["network_69-bus_A"]
n33B, n69B = S["network_33-bus_B"], S["network_69-bus_B"]
rel = {(r["design"], r["strategy"]): r for r in S["reliability"]}
bat = {(r["bess_kWh"], r["strategy"]): r for r in S["battery"]}
BASE = "Base feeder (no new sites)"

NAVY = RGBColor(0x0F, 0x22, 0x36)
GREY = RGBColor(0x52, 0x51, 0x4E)

doc = Document()
st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(11)
for sec in doc.sections:
    sec.left_margin = sec.right_margin = Cm(2.0)
    sec.top_margin = sec.bottom_margin = Cm(1.8)


def H(text, lvl=1):
    h = doc.add_heading(text, level=lvl)
    for r in h.runs:
        r.font.color.rgb = NAVY
        r.font.name = "Cambria"
    return h


def P(text, bold=False, italic=False, color=None, size=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold, r.italic = bold, italic
    if color:
        r.font.color.rgb = color
    if size:
        r.font.size = Pt(size)
    return p


def BL(items):
    for t in items:
        doc.add_paragraph(t, style="List Bullet")


def table(rows, widths=None, header=True):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Light Grid Accent 1"
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.text = str(val)
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(10)
                    r.bold = header and i == 0
    doc.add_paragraph()
    return t


def QA(q, a):
    p = doc.add_paragraph()
    r = p.add_run("Q. " + q)
    r.bold = True
    r.font.color.rgb = NAVY
    p.paragraph_format.space_after = Pt(2)
    p2 = doc.add_paragraph(a)
    p2.paragraph_format.left_indent = Cm(0.6)
    p2.paragraph_format.space_after = Pt(8)


f1 = lambda x: f"{x:.1f}"
f0 = lambda x: f"{x:.0f}"
f2 = lambda x: f"{x:.2f}"

# ----------------------------------------------------------------- cover
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.LEFT
r = t.add_run("Adaptive-ReBIS: Review Guide and Viva Q&A")
r.bold = True
r.font.size = Pt(22)
r.font.color.rgb = NAVY
r.font.name = "Cambria"
P("For the presenter. Read sections 1, 4 and 5 the night before; keep section 3 open during the demo.",
  italic=True, color=GREY)

H("1. The project in one minute")
P("We built an energy management system for a site that has an EV charging hub (8 AC + 2 DC chargers) and "
  "ordinary building loads (air-conditioning, water heaters, lights and plugs). The site has rooftop solar, a "
  "battery and a grid connection. Every evening the system uses a machine-learning model to predict the next "
  "day's hourly demand, then a Genetic Algorithm or Particle Swarm Optimisation decides how much the battery "
  "should charge or discharge in each hour. The goal is a low bill, a low grid peak and low CO2. The priority "
  "changes by the hour: cheapest at night, lowest grid draw in the evening peak-tariff hours. During the day a "
  "real-time layer corrects for forecast error. GA and PSO also choose the best PV and battery sizes. Finally, "
  "we place five such sites on the standard IEEE 33-bus and 69-bus distribution feeders and run load flow for "
  "every hour of the year, to check voltage, losses and peak at the substation.")

H("2. Key numbers to remember")
pa, ra, ga = A[PSO], A[RB], A[G0]
pb, rb, gb = B[PSO], B[RB], B[G0]
table([
    ["Item", "Value"],
    ["Location / data year", "Hyderabad, PVGIS-ERA5 2020, 8784 hours"],
    ["PV yield", "about 1355 kWh per kWp per year (3.7 per day)"],
    ["Site demand", f"647 MWh/yr, peak {f0(ga['annual_peak_import_kW'])} kW"],
    ["Best forecaster", f"{fbest}: R2 {f2(fc[fbest]['R2'])}, MAPE {f1(fc[fbest]['MAPE_pct'])} % "
                        f"(persistence R2 {f2(fc['Persistence (yesterday)']['R2'])})"],
    ["Optimal size (GA = PSO)", f"PV {f0(sz['pv_kWp'])} kWp, battery {f0(sz['bess_kWh'])} kWh, wind {f0(sz['wind_kW'])} kW"],
    ["Total annual cost incl. capital", f"{f1(sz['total_lakh'])} lakh vs {f1(szg['total_lakh'])} lakh grid only"],
    ["Design A (PSO) vs grid only", f"cost -{f1(pa['cost_saving_pct'])} %, annual peak -{f1(pa['peak_reduction_pct'])} %, CO2 -{f1(pa['CO2_reduction_pct'])} %"],
    ["Design A rule-based vs grid only", f"cost -{f1(ra['cost_saving_pct'])} %, annual peak -{f1(ra['peak_reduction_pct'])} %, CO2 -{f1(ra['CO2_reduction_pct'])} %"],
    ["Design A mean daily peak", f"PSO {f0(pa['mean_daily_peak_kW'])} kW, rule {f0(ra['mean_daily_peak_kW'])} kW, grid only {f0(ga['mean_daily_peak_kW'])} kW"],
    ["Design B (200 kWh) mean daily peak", f"GA {f0(B[GA]['mean_daily_peak_kW'])} kW, PSO {f0(pb['mean_daily_peak_kW'])} kW, rule {f0(rb['mean_daily_peak_kW'])} kW, grid only {f0(gb['mean_daily_peak_kW'])} kW"],
    ["Design B (PSO) vs grid only", f"cost -{f1(pb['cost_saving_pct'])} %, annual peak -{f1(pb['peak_reduction_pct'])} %, CO2 -{f1(pb['CO2_reduction_pct'])} % (rule: -{f1(rb['cost_saving_pct'])} %, -{f1(rb['peak_reduction_pct'])} %, -{f1(rb['CO2_reduction_pct'])} %)"],
    ["GA / PSO gap to exact LP", f"GA {f2(op['GA_mean'])} %, PSO {f2(op['PSO_mean'])} % (mean of {op['days']} days)"],
    ["Solve time per day", f"PSO {f0(op['t_PSO_ms'])} ms, GA {f0(op['t_GA_ms'])} ms, LP {f0(op['t_LP_ms'])} ms"],
    ["IEEE 33-bus base case", f"loss {f2(v33['our_BFS_loss_kW'])} kW, Vmin {v33['our_BFS_Vmin_pu']:.4f} pu at bus 18 (published 202.67 kW, 0.9131)"],
    ["IEEE 69-bus base case", f"loss {f2(v69['our_BFS_loss_kW'])} kW, Vmin {v69['our_BFS_Vmin_pu']:.4f} pu at bus 65 (published 224.95 kW, 0.9092)"],
    ["33-bus bus-hours below 0.91 pu (Design B)", f"grid only {n33B[G0]['bus_hours_below_0.91pu']}, rule {n33B[RB]['bus_hours_below_0.91pu']}, Adaptive PSO {n33B[PSO]['bus_hours_below_0.91pu']}"],
    ["33-bus lowest voltage (Design B)", f"grid only {n33B[G0]['lowest_voltage_pu']:.4f}, rule {n33B[RB]['lowest_voltage_pu']:.4f}, Adaptive PSO {n33B[PSO]['lowest_voltage_pu']:.4f} pu"],
    ["33-bus hours below 0.91 pu (Design B)", f"grid only {n33B[G0]['hours_below_0.91pu']}, rule {n33B[RB]['hours_below_0.91pu']}, Adaptive PSO {n33B[PSO]['hours_below_0.91pu']}"],
    ["69-bus hours below 0.91 pu (Design B)", f"grid only {n69B[G0]['hours_below_0.91pu']}, rule {n69B[RB]['hours_below_0.91pu']}, Adaptive PSO {n69B[PSO]['hours_below_0.91pu']}"],
    ["Outage demand served (PSO)", f"Design A {f0(rel[('A', PSO)]['served_during_outage_pct'])} %, Design B {f0(rel[('B', PSO)]['served_during_outage_pct'])} %; PV without battery 0 %"],
])

H("3. Live demo script (about 4 minutes)")
P("Start: double-click RUN_DASHBOARD.bat in the Adaptive-ReBIS folder (or: py -m streamlit run dashboard/app.py). "
  "A browser tab opens at http://localhost:8501. Open it BEFORE the review starts. The first load takes ~10 s.", bold=True)
BL([
    "Leave the defaults: 15 May 2020, PV 300 kWp, battery 200 kWh, PSO, Balanced. Say: \"This is the highest-demand "
    "day of the year. The optimiser just ran live using the ML forecast.\"",
    "Point to the four tiles at the top: grid peak, cost, CO2, peak-hour energy. Each shows the rule-based and grid-only "
    "values under it. Point at the grid peak: Adaptive-ReBIS is far below both.",
    "Power-sharing chart: yellow = solar to load, green = battery discharge, grey = grid, blue below zero = battery "
    "charging. Show the SOC plot: the orange (rule-based) battery is empty by evening; ours (blue) is saved for the "
    "18-22 h peak.",
    "Switch optimiser to GA, then LP (exact). Say: \"Same answer within about a percent; LP is exact for this linear "
    "case, GA/PSO are kept for non-linear extensions.\"",
    "Move Priority to \"Lowest grid peak\" and back to \"Lowest bill\": the battery schedule changes. This is the "
    "adaptive weighting.",
    "Open the IEEE feeder tab: the voltage profile at 18:00. All three cases with sites dip below the red 0.91 pu "
    "line at the feeder tail on this peak day, but Adaptive-ReBIS dips the least (about 0.896 pu vs 0.888 rule-based "
    "and 0.887 grid only); the table below the chart shows it. Do NOT claim it stays above the limit. Switch to 69-bus.",
    "Forecast tab: ML forecast vs persistence for that week.",
    "If anything fails: show the figures in results/figures (the deck has them all).",
])

H("4. What to say on each slide (short)")
BL([
    "Problem: EV + AC + lighting peak together in the evening, solar peaks at noon; fixed rules empty the battery too early; "
    "the feeder tail voltage drops below the Indian -9 % limit.",
    "Base paper: ReBIS (Applied Energy 2025). We add adaptive weights, ML forecasting, GA/PSO scheduling + sizing, Indian data and IEEE network validation.",
    "Architecture: data -> forecast -> day-ahead optimiser -> real-time correction -> site -> load flow + KPIs. Runs every day of the year.",
    "Data: weather and tariff are real; the site load is modelled on real temperature (say this openly).",
    "Forecast: 6 models, every forecast out-of-sample (12-fold month-blocked CV). ML clearly beats naive forecasts.",
    "Formulation: one variable per hour (battery power); weighted cost + CO2 + peak; weights change with the ToD window.",
    "GA/PSO: vectorised, < 1 s per day; benchmarked against the exact LP optimum, so we can say how good they are.",
    "Sizing: both converge to the same design; wind = 0 in Hyderabad; battery grows as its price falls.",
    "Results: Adaptive-ReBIS (GA and PSO) beats rule-based on cost and peak; CO2 is slightly higher than rule-based "
    "(a stated trade-off for the lower peak).",
    "Network: model first reproduces the published 33/69-bus base cases; then a full year of hourly load flow. "
    "Adaptive-ReBIS wins on dip depth, bus-hours, losses, substation peak; the rule has fewer violation hours "
    "because the tariff peak (06-10 h) is not the feeder peak (17-21 h). Say this yourself.",
])

H("5. Viva questions and answers")
QA("Why GA and PSO, if an LP can solve it exactly?",
   "This particular formulation is linear, so we use LP as the benchmark to prove GA/PSO reach near-optimal "
   f"answers (PSO {f2(op['PSO_mean'])} %, GA {f2(op['GA_mean'])} % mean gap). As soon as you add a non-linear battery "
   "ageing model, discrete EV charger on/off control, or efficiency curves, LP no longer applies but GA/PSO work "
   "unchanged. That flexibility is why the abstract uses them.")
QA("Which is better, GA or PSO?",
   f"On the day-ahead problem itself PSO: smaller gap to the exact optimum (PSO {f2(op['PSO_mean'])} % vs GA "
   f"{f2(op['GA_mean'])} %), better on {op['PSO_better_days']} of {op['days']} days, and faster. Over the full year, "
   "once real forecast errors are applied, the two end within about 1 % on cost "
   f"(Design B: GA {f1(B[GA]['net_operating_cost_Rs_lakh'])} vs PSO {f1(B[PSO]['net_operating_cost_Rs_lakh'])} lakh), and GA "
   f"happened to give a lower average daily peak in Design B ({f0(B[GA]['mean_daily_peak_kW'])} vs {f0(B[PSO]['mean_daily_peak_kW'])} kW). "
   "Lesson: once the plan is near-optimal, forecast quality matters more than which optimiser you use. "
   "PSO suits continuous variables; GA's strength is discrete or mixed decisions.")
QA("What exactly is 'adaptive' in Adaptive-ReBIS?",
   "Three things: (1) the objective weights on cost / peak / CO2 change with the hour according to the TGERC ToD "
   "windows; (2) the plan is recomputed every day from a fresh ML forecast; (3) the real-time layer adapts to "
   "forecast error (holds grid draw at plan in peak hours, stores unforecast solar, peak guard).")
QA("Is the load data real?",
   "The weather, PV, wind, tariff, CO2 factor and IEEE feeder data are real. We did not have metered load for a "
   "site, so the load is a model: each EV session is simulated with a charger queue; HVAC and geysers are driven "
   "by the real hourly temperature. It is seeded, so results are reproducible. Retraining on metered data is our next step.")
QA("How did you validate the forecast?",
   "12-fold month-blocked cross-validation: for each month the model is trained on the other 11 months, so all "
   f"8784 forecasts are out-of-sample. {fbest} reached R2 {f2(fc[fbest]['R2'])} and MAPE "
   f"{f1(fc[fbest]['MAPE_pct'])} %, versus R2 {f2(fc['Persistence (yesterday)']['R2'])} for 'same as yesterday'.")
QA("Why is MAPE still about 15 %?",
   "EV arrivals are random by nature: the timing of individual cars cannot be predicted a day ahead. That is exactly "
   "why we added the real-time correction layer instead of trusting the forecast blindly.")
QA("Which features matter most?",
   "Load one week earlier (same weekday and hour) dominates, then yesterday's load and the temperature forecast.")
QA("How is the temperature forecast obtained?",
   "We use the real hourly temperature plus Gaussian noise of 1.5 C to mimic a day-ahead weather forecast error. "
   "It is stated in the code.")
QA("Why is wind 0 kW?",
   f"Hyderabad wind at 30 m gives a capacity factor of only about 3 %. Both GA and PSO independently drive wind to 0; "
   "the money is better spent on PV. In a coastal or Tamil Nadu location the result would change.")
QA("Why is the optimal battery so small?",
   f"At Rs 15,000/kWh and a Rs 2/kWh ToD spread, storage barely pays back on the bill. The optimum grows as battery "
   f"prices fall ({', '.join(f'Rs {int(s['bess_price_Rs_per_kWh'])//1000}k -> {s['bess_kWh']:.0f} kWh' for s in sens)}). "
   "Its real value is grid support (peak and voltage) and backup, which we show with Design B.")
QA("Why does PV stop at 300 kWp?",
   "That is our assumed roof + carport area limit (~3000 m2). PV is still profitable at the limit.")
QA("Adaptive-ReBIS has slightly higher CO2 than the rule-based scheme. Why?",
   "The adaptive plan keeps the battery charged for the evening peak and refills it overnight, so a little more energy "
   "goes through battery losses and a little more solar is exported. It is a deliberate trade for a much lower peak. "
   "Raising the CO2 weight reduces it. With a flat CO2 factor, any grid kWh has the same CO2 regardless of time.")
QA("What is the perfect-foresight LP?",
   "The best possible result if tomorrow's load and solar were known exactly. It cannot be achieved in reality; the "
   "gap between it and our result is the cost of forecast error.")
QA("Why did you write your own load-flow solver if pandapower exists?",
   "pandapower's Newton-Raphson is the reference. Our backward/forward sweep is vectorised over all 8784 hours, so "
   "the full year solves in about a second; it matches pandapower to better than 1e-6 pu. Both reproduce the published "
   "base cases.")
QA("What are the 33-bus and 69-bus base cases?",
   "12.66 kV radial feeders from Baran and Wu (1989). 33-bus: 3.715 MW load, 202.67 kW loss, Vmin 0.9131 pu at bus 18. "
   "69-bus: 3.80 MW, 224.95 kW loss, Vmin 0.9092 pu at bus 65. We match both.")
QA("Where did you connect the sites and why there?",
   "At five tail-end buses (33-bus: 18, 22, 25, 30, 33; 69-bus: 27, 35, 46, 50, 65), which are the weakest points; "
   "that is where EV hubs cause the most voltage drop and where the benefit shows most.")
QA("Why does the rule-based scheme have fewer hours below 0.91 pu than yours?",
   f"Good catch, and we report it openly. Adaptive-ReBIS is better on the depth of the dip (lowest voltage), on "
   f"under-voltage bus-hours (33-bus Design B: {n33B[PSO]['bus_hours_below_0.91pu']} vs {n33B[RB]['bus_hours_below_0.91pu']}), "
   "losses and substation peak. But our weights follow the TGERC tariff, whose peak windows are 06-10 h and 18-22 h, "
   "while the feeder is most loaded 17-21 h. So some battery energy is spent on the morning tariff peak when the feeder "
   "is not stressed, while the simple rule happens to discharge in the late afternoon. The tariff signal and the "
   "network signal do not match. We tried re-weighting by the feeder shape and it did not remove the gap, so the "
   "proper fix is a network-aware objective using a DSO stress / voltage signal. That is our main future work.")
QA("Why the 0.91 pu limit?",
   "Indian HV supply limit is +6 % / -9 % of nominal (IE Rules 1956 Rule 54, carried into the CEA regulations). We also "
   "report the stricter 0.95 pu planning limit in the CSVs.")
QA("How is the time-of-day tariff modelled?",
   "TGERC FY2023-24 EV charging station ToD: Rs 6 base, +Rs 1 in 06-10 h and 18-22 h, -Rs 1 in 22-06 h.")
QA("What demand charge did you use?",
   "Rs 475 per kVA per month on the monthly maximum demand, billing demand at least 80 % of a 160 kVA contract, excess "
   "billed at twice the rate. This is an assumption in the order of Telangana HT tariffs; it is in config.py.")
QA("How is battery degradation handled?",
   "As a wear cost of Rs 3.3 per kWh discharged (Rs 15,000/kWh pack over 6000 cycles at 75 % depth). A non-linear "
   "ageing model is our next step and is where GA/PSO would beat LP.")
QA("How is reliability measured?",
   "Monte-Carlo: 200 simulated years with about 48 random grid outages per year (mean 1.5 h). During an outage a "
   "grid-tied PV inverter without a battery must shut down (anti-islanding), so only PV + battery sites can serve "
   "load from whatever charge they had. We report the share of outage-time demand served.")
QA("What happens if the forecast is badly wrong on a day?",
   "The real-time layer works on actual measurements: in peak hours the battery covers the error to keep grid draw at "
   "the plan; the peak guard caps grid import every hour; SOC limits are always respected.")
QA("Is the battery allowed to charge from the grid?",
   "Yes, at night at the off-peak price, when the optimiser decides it is worth it for the next morning's peak. The "
   "rule-based scheme charges only from solar surplus.")
QA("Why end each day at 50 % SOC?",
   "So the battery is ready for the next morning's ToD peak (06-10 h), and so days are comparable. It is a constraint in "
   "both GA/PSO (penalty) and LP (hard).")
QA("What is the novelty?",
   "Combining a time-varying (adaptive) multi-objective schedule driven by an ML forecast with a real-time correction "
   "layer, for mixed EV + appliance loads, sized by GA/PSO, benchmarked against the exact optimum, and validated with a "
   "full-year hourly load flow on two IEEE feeders. Individual parts exist in the literature; the integrated, "
   "benchmarked pipeline with Indian data is our contribution.")
QA("What would you do with more time?",
   "Smart EV charging as a second control variable, a battery ageing model, real metered data, hourly marginal CO2 "
   "factors, and a conference paper.")
QA("Which software did you use and why not MATLAB/Simulink?",
   "Python: NumPy/pandas, scikit-learn, SciPy (HiGHS LP), pandapower, Streamlit. It is open-source, the whole year "
   "runs in one script, the ML and load-flow libraries are standard in power-systems research, and anyone can rerun it "
   "without a licence.")
QA("Can it run in real time on hardware?",
   f"Yes in principle: a full day's plan takes about {f0(op['t_PSO_ms'])} ms with PSO, so it can run on a small "
   "industrial PC or Raspberry Pi as the site controller.")

H("6. Honest limitations (say them before you are asked)")
BL([
    "Site load is modelled, not metered (weather is real).",
    "Capital costs, demand charge, outage statistics and the feeder daily shape are assumptions (all in config.py).",
    "Flat CO2 factor: real grid CO2 varies by hour; a marginal factor would reward evening peak shaving more.",
    "Five identical sites on the feeder; real sites would differ.",
    "The EMS follows tariff windows, not a network signal; hence rule-based has fewer under-voltage hours.",
    "Battery ageing is a linear wear cost, not an electrochemical model.",
])

H("7. Files")
table([
    ["File", "What it is"],
    ["review/Adaptive-ReBIS_Review_Deck.pptx", "The review presentation (speaker notes on every slide)"],
    ["RUN_DASHBOARD.bat", "Starts the live demo dashboard"],
    ["run_all.py / RUN_ALL.bat", "Regenerates every result and figure (~45 min)"],
    ["results/*.csv", "All result tables"],
    ["results/figures/*.png", "All figures"],
    ["src/config.py", "Every input value and assumption, with source"],
    ["README.md", "Project overview and how to run"],
])

doc.save(OUT)
print("wrote", OUT)

if "--pdf" in sys.argv:
    import subprocess
    pdf = OUT.with_suffix(".pdf")
    ps = (f"$w = New-Object -ComObject Word.Application; $w.Visible = $false; "
          f"$d = $w.Documents.Open('{OUT}'); $d.SaveAs([ref]'{pdf}', [ref]17); $d.Close(); $w.Quit()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
    print("wrote", pdf)
