"""
loads.py -- one full year of hourly demand for the Adaptive-ReBIS site.

The site is a campus/community block behind one PCC meter:
  * EV charging hub   : 8 x 7.4 kW AC + 2 x 30 kW DC chargers, stochastic
                        arrivals/energy, simulated per EV at 15-min resolution
                        with a real charger queue (busy chargers make EVs wait)
  * HVAC              : office/academic block, driven by the REAL hourly
                        PVGIS/ERA5 temperature, occupancy schedule, COP that
                        falls as it gets hotter
  * Water heaters     : hostel geyser bank, morning/evening peaks, higher in
                        winter (driven by the real temperature)
  * General appliances: lighting, plug loads, pumps, with evening lighting peak

All randomness is seeded (config.SEED), so every run gives identical numbers.
"""
import numpy as np
import pandas as pd

import config as C

STEP = 0.25                      # h, EV simulation resolution
AC_KW, N_AC = 7.4, 8
DC_KW, N_DC = 30.0, 2


def ev_hub(index, rng):
    n_days = len(index) // 24
    steps_per_day = int(24 / STEP)
    load = np.zeros(n_days * steps_per_day + steps_per_day)  # spill-over day
    free_at = {"AC": np.zeros(N_AC), "DC": np.zeros(N_DC)}    # step when charger frees
    sessions = served = 0
    for d in range(n_days):
        dow = index[d * 24].dayofweek
        n = rng.poisson(34 if dow < 5 else 24)
        # arrival mixture: morning commute, midday, evening return
        comp = rng.choice(3, size=n, p=[0.30, 0.25, 0.45])
        mu = np.array([9.0, 13.5, 18.5])[comp]
        sd = np.array([1.2, 1.8, 1.8])[comp]
        arr = np.clip(rng.normal(mu, sd), 0, 23.75)
        for a in np.sort(arr):
            sessions += 1
            kind = "DC" if rng.random() < 0.30 else "AC"
            p = DC_KW if kind == "DC" else AC_KW
            e = rng.uniform(12, 35) if kind == "DC" else rng.uniform(6, 25)
            s_arr = d * steps_per_day + int(a / STEP)
            k = int(np.argmin(free_at[kind]))
            start = max(s_arr, int(free_at[kind][k]))
            if start - s_arr > 4:          # >1 h wait -> driver leaves (unserved)
                continue
            dur = e / p / STEP
            full, frac = int(dur), dur - int(dur)
            load[start:start + full] += p
            if start + full < len(load):
                load[start + full] += p * frac
            free_at[kind][k] = start + full + (1 if frac > 0 else 0)
            served += 1
    hourly = load[: n_days * steps_per_day].reshape(-1, 4).mean(axis=1)
    return hourly, sessions, served


def hvac(w, rng):
    T = w["temp_c"].to_numpy()
    # building thermal lag: exponential smoothing of outdoor temperature
    Tb = np.empty_like(T)
    Tb[0] = T[0]
    for i in range(1, len(T)):
        Tb[i] = 0.75 * Tb[i - 1] + 0.25 * T[i]
    hour, dow = w["hour"].to_numpy(), w["dow"].to_numpy()
    occ = ((dow < 5) & (hour >= 9) & (hour < 19)) | ((dow == 5) & (hour >= 9) & (hour < 14))
    precool = ((dow < 6) & (hour == 8))
    q_th = 14.0 * np.maximum(0, Tb - 24.0) + 60.0          # kW thermal (envelope + people)
    cop = np.clip(3.6 - 0.05 * (T - 30.0), 2.4, 4.0)
    p = np.where(occ, q_th / cop, 0.0)
    p = np.where(precool, 0.6 * q_th / cop, p)
    p = p * np.where(Tb > 21.0, 1.0, 0.25)                # little cooling in cool weather
    p += 3.0                                              # server room, always on
    return p * rng.normal(1.0, 0.05, len(p))


def water_heaters(w, rng):
    hour = w["hour"].to_numpy()
    T_day = w["temp_c"].rolling(24, min_periods=1).mean().to_numpy()
    shape = (np.exp(-0.5 * ((hour - 6.8) / 1.1) ** 2)
             + 0.55 * np.exp(-0.5 * ((hour - 19.0) / 1.5) ** 2))
    winter = np.clip(1.0 + (26.0 - T_day) / 8.0, 0.35, 2.0)  # colder -> more hot water
    p = 45.0 * shape * winter                                 # 40 geysers x 2 kW bank
    return np.clip(p * rng.normal(1.0, 0.08, len(p)), 0, 80.0)


def general(w, rng):
    hour, dow = w["hour"].to_numpy(), w["dow"].to_numpy()
    day = np.where((hour >= 8) & (hour < 18), 38.0, 18.0)
    eve = 22.0 * np.exp(-0.5 * ((hour - 20.0) / 1.6) ** 2)    # lighting peak
    wk = np.where(dow >= 5, 0.8, 1.0)
    # slow AR(1) wander so no two days look identical
    ar = np.zeros(len(hour))
    e = rng.normal(0, 0.03, len(hour))
    for i in range(1, len(ar)):
        ar[i] = 0.9 * ar[i - 1] + e[i]
    return (day + eve) * wk * (1.0 + ar)


def build_loads(w):
    rng = np.random.default_rng(C.SEED)
    ev, n_sess, n_served = ev_hub(w.index, rng)
    df = pd.DataFrame(index=w.index)
    df["ev"] = ev
    df["hvac"] = hvac(w, rng)
    df["water_heater"] = water_heaters(w, rng)
    df["general"] = general(w, rng)
    df["load"] = df[["ev", "hvac", "water_heater", "general"]].sum(axis=1)
    df.attrs["ev_sessions"] = n_sess
    df.attrs["ev_served"] = n_served
    return df


if __name__ == "__main__":
    from data_prep import build_weather
    w = build_weather()
    L = build_loads(w)
    print(L.describe().round(1))
    print("annual MWh:", (L.sum() / 1000).round(1).to_dict())
    print(f"EV sessions {L.attrs['ev_sessions']}, served {L.attrs['ev_served']}")
    print("peak hour total:", L.load.idxmax(), round(L.load.max(), 1))
    print(L.groupby(L.index.hour).mean().round(1))
