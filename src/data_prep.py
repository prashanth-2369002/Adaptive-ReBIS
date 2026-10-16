"""
data_prep.py -- turns the real PVGIS year into an hourly IST weather/resource
table and builds the tariff and CO2 series.

Output columns (8784 rows, 2020 is a leap year):
    time, hour, dow, doy, month, pv_kw_per_kwp, temp_c, wind_ms,
    wind_kw_per_kw, tariff, co2
"""
import json
import numpy as np
import pandas as pd

import config as C


def load_pvgis():
    raw = json.loads(C.PVGIS_RAW.read_text())
    df = pd.DataFrame(raw["outputs"]["hourly"])
    # PVGIS stamps are UTC at hh:30 (mid-hour); IST = UTC + 5 h 30 min, so each
    # sample lands exactly on an IST clock hour.
    t_utc = pd.to_datetime(df["time"], format="%Y%m%d:%H%M")
    t_ist = t_utc + pd.Timedelta(hours=5, minutes=30)
    out = pd.DataFrame({
        "pv_kw_per_kwp": df["P"].to_numpy() / 1000.0,   # W per kWp -> kW per kWp
        "temp_c": df["T2m"].to_numpy(),
        "wind_ms": df["WS10m"].to_numpy(),
    }, index=t_ist)
    # Shift into a clean IST calendar year: the 6 h that spill into 2021 wrap to
    # the start of 2020 (same season, a standard TMY-style treatment).
    n = len(out)
    shift = int((t_ist.iloc[0] - pd.Timestamp("2020-01-01 00:00")) / pd.Timedelta(hours=1))
    vals = np.roll(out.to_numpy(), shift, axis=0)
    idx = pd.date_range("2020-01-01 00:00", periods=n, freq="h")
    return pd.DataFrame(vals, index=idx, columns=out.columns)


def wind_power_per_kw(ws10):
    """Small-turbine power curve (cubic between cut-in and rated), per kW rated."""
    v = ws10 * (C.WIND_HUB_M / 10.0) ** C.WIND_SHEAR
    p = np.where(v < C.WIND_CUT_IN, 0.0,
        np.where(v < C.WIND_RATED,
                 (v**3 - C.WIND_CUT_IN**3) / (C.WIND_RATED**3 - C.WIND_CUT_IN**3),
        np.where(v < C.WIND_CUT_OUT, 1.0, 0.0)))
    return p


def tariff_for_hours(hours):
    hours = np.asarray(hours)
    t = np.full(hours.shape, C.TARIFF_BASE, dtype=float)
    t[np.isin(hours, C.PEAK_HOURS)] += C.TARIFF_PEAK_ADDER
    t[np.isin(hours, C.OFFPEAK_HOURS)] += C.TARIFF_OFFPEAK_ADDER
    return t


def build_weather():
    df = load_pvgis()
    df["hour"] = df.index.hour
    df["dow"] = df.index.dayofweek
    df["doy"] = df.index.dayofyear
    df["month"] = df.index.month
    df["wind_kw_per_kw"] = wind_power_per_kw(df["wind_ms"].to_numpy())
    df["tariff"] = tariff_for_hours(df["hour"].to_numpy())
    df["co2"] = C.GRID_CO2
    return df


if __name__ == "__main__":
    w = build_weather()
    print(w.head(8))
    print(f"PV yield      : {w.pv_kw_per_kwp.sum():.0f} kWh/kWp/yr "
          f"({w.pv_kw_per_kwp.sum()/366:.2f} per day, CUF {w.pv_kw_per_kwp.mean()*100:.1f} %)")
    print(f"Wind @{C.WIND_HUB_M:.0f} m  : CUF {w.wind_kw_per_kw.mean()*100:.1f} %, "
          f"mean 10 m speed {w.wind_ms.mean():.2f} m/s")
    print(f"Temperature   : {w.temp_c.min():.1f} .. {w.temp_c.max():.1f} C")
    print("PV peak hour (IST) by mean:", w.groupby("hour").pv_kw_per_kwp.mean().idxmax())
