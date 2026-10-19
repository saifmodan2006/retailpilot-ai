from datetime import timedelta

import numpy as np
import pandas as pd
from fastapi import HTTPException

from .analytics import frames

METHODS = ["Naive", "Seasonal naive", "Moving average", "EWMA"]


def predict(values, method, horizon):
    y = np.asarray(values, dtype=float)
    if method == "Naive":
        return np.repeat(y[-1], horizon)
    if method == "Seasonal naive":
        return np.resize(y[-7:], horizon)
    if method == "Moving average":
        return np.repeat(y[-28:].mean(), horizon)
    return np.repeat(pd.Series(y).ewm(span=14, adjust=False).mean().iloc[-1], horizon)


def evaluate_series(series, horizon):
    y = np.asarray(series, dtype=float)
    if len(y) < 42:
        raise HTTPException(
            422, "At least 42 daily observations are required for rolling validation"
        )
    # Each origin only sees earlier observations. Three seven-day holdouts.
    scores = []
    for method in METHODS:
        errors, actuals = [], []
        for origin in [len(y) - 21, len(y) - 14, len(y) - 7]:
            actual = y[origin : origin + 7]
            forecast = predict(y[:origin], method, len(actual))
            errors.extend(np.abs(actual - forecast).tolist())
            actuals.extend(actual.tolist())
        scores.append(
            {
                "model": method,
                "mae": round(float(np.mean(errors)), 3),
                "wape": round(float(sum(errors) / sum(actuals) * 100), 2) if sum(actuals) else None,
            }
        )
    best = min(scores, key=lambda s: s["mae"])["model"]
    final = predict(y, best, horizon)
    baseline = predict(y, "Naive", horizon)
    # Display empirical error, not an unsupported probability interval.
    mae = next(s["mae"] for s in scores if s["model"] == best)
    return best, final, baseline, scores, mae


def forecast(db, org, filters, horizon):
    sales, _ = frames(db, org, filters)
    if sales.empty:
        raise HTTPException(422, "No sales data for this selection")
    # Full daily grid includes zero-sale days; returns do not become negative demand.
    start = max(sales.date.min(), filters.start)
    grid = pd.date_range(start, filters.end)
    grouped = sales.assign(demand=sales.quantity.clip(lower=0)).groupby("date").demand.sum()
    grouped.index = pd.to_datetime(grouped.index)
    series = grouped.reindex(grid, fill_value=0)
    best, final, baseline, scores, mae = evaluate_series(series.values, horizon)
    return {
        "model": best,
        "baseline": "Naive",
        "version": "baselines-v1",
        "horizon": horizon,
        "forecast_total": round(float(sum(final)), 1),
        "backtests": scores,
        "history": [
            {"date": str(d.date()), "actual": int(v)} for d, v in series.iloc[-60:].items()
        ],
        "forecast": [
            {
                "date": str(filters.end + timedelta(days=i + 1)),
                "selected": round(float(v), 2),
                "baseline": round(float(baseline[i]), 2),
            }
            for i, v in enumerate(final)
        ],
        "validation": "Three rolling 7-day holdouts; chronological training only.",
        "uncertainty": f"Validation MAE: {mae:.2f} units/day. This is an error estimate, not a confidence interval.",
        "explanation": "Demand counts positive unit sales, with zero-sale days retained. Weekly seasonal naive uses a seven-day cycle. No trained ML superiority is claimed.",
        "filters": filters.model_dump(mode="json"),
    }
