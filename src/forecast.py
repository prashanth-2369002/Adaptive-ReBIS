"""
forecast.py -- machine-learning day-ahead (next-day, hourly) demand forecast.

Every hour of day D is predicted using only information available by the end
of day D-1: calendar, a weather forecast for D (real temperature + Gaussian
forecast error, sigma = 1.5 C, mimicking a day-ahead NWP error), and lagged
load (same hour yesterday, two days ago, last week; yesterday's mean/peak).

Models compared (all scikit-learn):
    Persistence (yesterday = today)        -- naive baseline
    Weekly naive (same day last week)      -- naive baseline
    Ridge linear regression
    Random Forest
    Gradient Boosting (HistGradientBoosting)
    Neural network (MLP, 2 hidden layers)

Validation: month-blocked cross-validation. For each of the 12 months the
model is trained on the other 11 months and forecasts the held-out month,
so every one of the 8784 forecasts is out-of-sample. These out-of-sample
forecasts are what the EMS optimiser then receives.

PV forecast: smart persistence (mean of the same hour over the previous
three days), its error is reported as well.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import config as C

TEMP_FC_SIGMA = 1.5


def make_features(w, L, rng):
    y = L["load"]
    X = pd.DataFrame(index=w.index)
    h = w["hour"].to_numpy()
    X["hour"] = h
    X["hour_sin"] = np.sin(2 * np.pi * h / 24)
    X["hour_cos"] = np.cos(2 * np.pi * h / 24)
    X["dow"] = w["dow"]
    X["weekend"] = (w["dow"] >= 5).astype(int)
    X["saturday"] = (w["dow"] == 5).astype(int)
    X["doy_sin"] = np.sin(2 * np.pi * w["doy"] / 366)
    X["doy_cos"] = np.cos(2 * np.pi * w["doy"] / 366)
    t_fc = w["temp_c"] + rng.normal(0, TEMP_FC_SIGMA, len(w))
    X["temp_fc"] = t_fc
    X["temp_fc_day_mean"] = t_fc.groupby(w.index.date).transform("mean").to_numpy()
    X["lag24"] = y.shift(24)
    X["lag48"] = y.shift(48)
    X["lag168"] = y.shift(168)
    daily = y.groupby(y.index.date)
    X["yday_mean"] = pd.Series(daily.transform("mean").to_numpy(), index=y.index).shift(24)
    X["yday_max"] = pd.Series(daily.transform("max").to_numpy(), index=y.index).shift(24)
    # first week has no history: fall back to the nearest available lag
    X["lag168"] = X["lag168"].fillna(X["lag24"])
    X = X.bfill()
    return X, y


MODELS = {
    "Ridge regression": lambda: make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "Random Forest": lambda: RandomForestRegressor(
        n_estimators=300, min_samples_leaf=3, n_jobs=-1, random_state=C.SEED),
    "Gradient Boosting": lambda: HistGradientBoostingRegressor(
        max_iter=400, learning_rate=0.05, max_leaf_nodes=31, random_state=C.SEED),
    "Neural network (MLP)": lambda: make_pipeline(StandardScaler(), MLPRegressor(
        hidden_layer_sizes=(64, 32), max_iter=600, early_stopping=True,
        random_state=C.SEED)),
}


def metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    err = p - y
    mae = np.mean(np.abs(err))
    rmse = np.sqrt(np.mean(err ** 2))
    mape = np.mean(np.abs(err) / np.maximum(y, 1.0)) * 100
    # daily peak error: what matters for peak-shaving
    yd, pd_ = y.reshape(-1, 24).max(1), p.reshape(-1, 24).max(1)
    peak_err = np.mean(np.abs(pd_ - yd) / yd) * 100
    r2 = 1 - np.sum(err ** 2) / np.sum((y - y.mean()) ** 2)
    return dict(MAE_kW=mae, RMSE_kW=rmse, MAPE_pct=mape, daily_peak_err_pct=peak_err, R2=r2)


def run_forecasts(w, L, verbose=True):
    rng = np.random.default_rng(C.SEED + 1)
    X, y = make_features(w, L, rng)
    month = w["month"].to_numpy()
    preds = {
        "Persistence (yesterday)": X["lag24"].to_numpy(),
        "Weekly naive (last week)": X["lag168"].to_numpy(),
    }
    for name, make in MODELS.items():
        p = np.zeros(len(y))
        for m in range(1, 13):
            tr, te = month != m, month == m
            mdl = make().fit(X[tr], y[tr])
            p[te] = mdl.predict(X[te])
        preds[name] = np.maximum(p, 0)
        if verbose:
            print(f"  trained {name}")
    rows = [dict(model=k, **metrics(y, v)) for k, v in preds.items()]
    table = pd.DataFrame(rows).set_index("model").round(3)
    best = table["RMSE_kW"].drop(["Persistence (yesterday)", "Weekly naive (last week)"]).idxmin()

    # feature importance of the Random Forest (fit on full year) for the report
    rf = MODELS["Random Forest"]().fit(X, y)
    imp = pd.Series(rf.feature_importances_, index=X.columns).sort_values(ascending=False)

    # PV smart persistence: mean of the same hour over the previous 3 days
    pv = w["pv_kw_per_kwp"]
    pv_fc = ((pv.shift(24) + pv.shift(48) + pv.shift(72)) / 3).bfill().to_numpy()
    pv_mae = np.mean(np.abs(pv_fc - pv.to_numpy())[pv.to_numpy() > 0])
    fc = pd.DataFrame({"load_actual": y, "load_fc": preds[best],
                       "pv_fc_per_kwp": pv_fc}, index=w.index)
    for k, v in preds.items():
        fc["fc_" + k] = v
    return table, best, fc, imp, pv_mae


if __name__ == "__main__":
    from data_prep import build_weather
    from loads import build_loads
    w = build_weather()
    L = build_loads(w)
    table, best, fc, imp, pv_mae = run_forecasts(w, L)
    print(table)
    print("best:", best)
    print(imp.head(8).round(3))
    print(f"PV persistence MAE (daylight) {pv_mae:.3f} kW/kWp")
