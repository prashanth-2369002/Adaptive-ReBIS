"""
config.py -- every number the simulation uses, in one place, with its source.

Change a value here and re-run `python run_all.py`; nothing else needs editing.
Values marked [REAL] come from a published source; [ASSUMPTION] values are
engineering estimates, stated openly so they can be defended or changed.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
FIG_DIR = RESULTS_DIR / "figures"
for _d in (DATA_DIR, RESULTS_DIR, FIG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

SEED = 2027

# ---------------------------------------------------------------- location
CITY = "Hyderabad, Telangana"
LAT, LON = 17.385, 78.4867
# [REAL] PVGIS v5.2 seriescalc, ERA5 meteo, year 2020, 1 kWp c-Si, 14 % loss.
# Hourly PV power, 2 m air temperature and 10 m wind speed for the whole year.
PVGIS_RAW = DATA_DIR / "pvgis_hyderabad_raw.json"

# ---------------------------------------------------------------- tariff
# [REAL] TGERC Retail Supply Tariff FY2023-24, HT/LT-IX "EV Charging Stations"
# with Time-of-Day: peak 06-10 h & 18-22 h = base + Rs 1; off-peak 22-06 h =
# base - Rs 1; normal 10-18 h = base. The whole site (EV hub + building loads)
# is modelled as one HT connection behind a single PCC meter on this tariff.
TARIFF_BASE = 6.00            # Rs/kWh
TARIFF_PEAK_ADDER = 1.00
TARIFF_OFFPEAK_ADDER = -1.00
PEAK_HOURS = [6, 7, 8, 9, 18, 19, 20, 21]
OFFPEAK_HOURS = [22, 23, 0, 1, 2, 3, 4, 5]
# [ASSUMPTION] value of exported (net-metered) energy, avoided-cost proxy.
EXPORT_PRICE = 3.00           # Rs/kWh
EXPORT_LIMIT_KW = 150.0       # [ASSUMPTION] sanctioned export limit at the PCC
# [ASSUMPTION] HT demand charge on the monthly maximum demand, order of the
# TG HT commercial demand charge; verify against the current tariff order.
DEMAND_CHARGE = 475.0         # Rs / kVA / month
POWER_FACTOR = 0.95
# [ASSUMPTION] contracted maximum demand (CMD). Common Indian HT billing rule:
# billing demand = max(recorded MD, 80 % of CMD); demand above CMD is billed
# at twice the normal demand charge.
CONTRACT_DEMAND_KVA = 160.0
ROOF_PV_LIMIT_KWP = 300.0     # [ASSUMPTION] ~3000 m2 rooftop + carport area

# ---------------------------------------------------------------- emissions
# [REAL] CEA CO2 Baseline Database v19, weighted all-India grid average.
GRID_CO2 = 0.716              # kg CO2 / kWh

# ---------------------------------------------------------------- battery (LFP)
BESS_ETA_CH = 0.95            # [ASSUMPTION] typical LFP + PCS one-way efficiency
BESS_ETA_DIS = 0.95
BESS_SOC_MIN = 0.20
BESS_SOC_MAX = 0.95
BESS_SOC_INIT = 0.50
BESS_C_RATE = 0.5             # kW per kWh of capacity
# [ASSUMPTION] degradation cost per kWh discharged:
# Rs 15,000/kWh pack / (6000 cycles x 0.75 usable DoD) ~= Rs 3.3/kWh
BESS_DEG_COST = 3.3

# ---------------------------------------------------------------- capital costs
# [ASSUMPTION] 2025-26 Indian market estimates, installed.
CAPEX_PV = 42_000             # Rs / kWp (commercial rooftop / carport)
CAPEX_BESS = 15_000           # Rs / kWh (LFP + PCS share)
CAPEX_WIND = 1_10_000         # Rs / kW (small turbine incl. tower)
LIFE_PV, LIFE_BESS, LIFE_WIND = 25, 10, 20
DISCOUNT = 0.08
OM_FRAC = 0.01                # annual O&M as fraction of capex

# ---------------------------------------------------------------- wind turbine
WIND_HUB_M = 30.0
WIND_SHEAR = 0.14             # power-law exponent, open terrain
WIND_CUT_IN, WIND_RATED, WIND_CUT_OUT = 3.0, 11.0, 25.0   # m/s

# ---------------------------------------------------------------- system size
# Default sizes used when the sizing optimiser is not run (overwritten by it).
PV_KWP = 200.0
BESS_KWH = 300.0
WIND_KW = 0.0

# ---------------------------------------------------------------- EMS weights
# Adaptive weighting: hour-dependent priority on (cost, peak, CO2).
W_PEAK_HOURS = (0.35, 0.50, 0.15)
W_NORMAL_HOURS = (0.50, 0.20, 0.30)
W_OFFPEAK_HOURS = (0.70, 0.15, 0.15)
# Extra weight on keeping charge for the evening when tomorrow is cloudy.
CLOUDY_DAY_PV_FRACTION = 0.6

# ---------------------------------------------------------------- network
# [REAL] Indian HV (11-33 kV) supply limit: -9 % / +6 % (IE Rules 1956 Rule 54,
# carried into the CEA safety regulations). 0.95 pu is also reported as the
# stricter planning limit used in most DG-planning papers.
VOLT_MIN_PU = 0.91
VOLT_PLAN_PU = 0.95
# Buses (1-based, as in the papers) where identical Adaptive-ReBIS sites connect
SITE_BUSES_33 = [18, 22, 25, 30, 33]
SITE_BUSES_69 = [27, 35, 46, 50, 65]
