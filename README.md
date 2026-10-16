# Adaptive-ReBIS — Adaptive Renewable-Integrated Energy Management System for EV charging and appliance loads

**Capstone batch 23CRT GET003 · Guide: Dr. G. Swapna · Coordinator: Dr. B. Jyothi**
**Students: Reddy Phaneendra (2300069007), Peela Sai Vivek (2300069015)**

A complete, reproducible simulation of the project described in the abstract, written in Python:

| Abstract says | Where it is done | How |
|---|---|---|
| Hourly solar/wind data (PVGIS) | `src/data_prep.py` | Real PVGIS-ERA5 2020 hourly PV, temperature, wind speed for Hyderabad (8784 h) |
| Load profiles (EV + HVAC + water heaters) | `src/loads.py` | Per-EV stochastic charging with a real charger queue, temperature-driven HVAC and geysers, general load |
| Indian tariffs, CO2 factors | `src/config.py` | TGERC ToD tariff (peak 06-10 & 18-22 h +Rs 1, off-peak 22-06 h -Rs 1), CEA 0.716 kg CO2/kWh |
| ML model forecasts next-day hourly demand | `src/forecast.py` | Ridge, Random Forest, Gradient Boosting, Neural Network (MLP) vs two naive baselines, 12-fold month-blocked CV |
| EMS with GA and PSO for power sharing | `src/ems.py` | Day-ahead GA / PSO battery schedule on the forecast + real-time correction; exact LP as the benchmark |
| ...and sizing | `src/sizing.py` | GA and PSO choose PV kWp, battery kWh and wind kW on a full-year simulation |
| Priority shifting in peak-tariff hours | `src/ems.py: hourly_weights` | Hour-dependent weights on cost / peak / CO2 |
| PV first, battery by SOC, grid covers deficit / absorbs export | `src/ems.py` | Exactly this power-flow rule, with SOC, power, export limits |
| Validated on IEEE 33-bus / 69-bus by load flow | `src/grid_ieee.py`, `src/ieee69.py` | pandapower (Newton-Raphson) + our own vectorised backward/forward sweep, both benchmarked against published base-case results, full 8784-hour annual study |
| Report cost, peak demand, CO2, reliability | `run_all.py` | Annual KPIs for 7 strategies, 2 designs; Monte-Carlo outage study |

## Run it

```bash
py -m pip install -r requirements.txt
py run_all.py                                   # ~45 min first time, cached afterwards
py -m streamlit run dashboard/app.py            # live interactive demo in the browser
```
Or double-click `RUN_DASHBOARD.bat`.

All results land in `results/` (CSV) and `results/figures/` (PNG). `results/summary.json` collects the headline
numbers used in the review deck.

## Strategies compared (every day of 2020, SOC carried day to day)

| | Strategy | What it is |
|---|---|---|
| S0 | Grid only | today's situation: no PV, no battery |
| S1 | PV + grid | renewables, no battery |
| S2 | Rule-based ReBIS | conventional: charge from any surplus, discharge on any deficit |
| S3 | **Adaptive-ReBIS (GA)** | ML forecast → GA day-ahead plan → real-time correction |
| S4 | **Adaptive-ReBIS (PSO)** | ML forecast → PSO day-ahead plan → real-time correction |
| S5 | LP on forecast | exact optimum of the same day-ahead problem (benchmark for GA / PSO) |
| S6 | Perfect-foresight LP | exact optimum if tomorrow were known exactly (upper bound, not achievable) |

## Honest notes (say these before the panel asks)

* **Real data:** PV/temperature/wind (PVGIS-ERA5), tariff (TGERC), CO2 factor (CEA), IEEE 33/69-bus data (Baran & Wu).
  **Modelled:** the site's load (EV sessions, HVAC, geysers, general). We had no metered load data, so the
  load model is synthetic but built on the real temperature series. All randomness is seeded, so every run is identical.
* **Assumptions** (all in `src/config.py`, marked `[ASSUMPTION]`): capital costs, battery wear cost,
  demand charge / contract demand, export price, feeder daily load shape, outage statistics.
* The **temperature forecast** used by the ML model is the real temperature plus a Gaussian error (σ = 1.5 °C)
  to mimic a day-ahead weather forecast.
* **Wind is not viable in Hyderabad** (capacity factor 3.4 % at 30 m), so both GA and PSO size wind at 0 kW.
* **At today's battery price the battery does not pay back on the electricity bill alone.** The economic
  optimum is a small battery; its value is peak-demand and feeder-voltage support. The battery-price
  sensitivity shows where it becomes economic.
* **The LP benchmark** exists because this particular day-ahead problem is linear. GA/PSO are still used
  because the formulation stays valid when non-linear parts are added (battery ageing curves, discrete EV
  charger control, non-linear converter efficiency); the LP proves how close to optimal they get.
