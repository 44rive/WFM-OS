"""Pure forecast helpers mirrored into the Python-in-Excel forecast sheet."""

from __future__ import annotations

import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing


def daily_ets_forecast(
    history: pd.DataFrame,
    periods: int = 28,
    seasonal_periods: int = 7,
) -> pd.DataFrame:
    """Return a dated ETS candidate forecast from Date/Volume history."""
    frame = history.loc[:, ["Date", "Volume"]].copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame = frame.dropna().sort_values("Date")

    if len(frame) < seasonal_periods * 2:
        raise ValueError("At least two full seasonal cycles are required.")

    fitted = ExponentialSmoothing(
        frame["Volume"].astype(float),
        trend="add",
        seasonal="mul",
        seasonal_periods=seasonal_periods,
    ).fit(optimized=True)

    dates = pd.date_range(
        frame["Date"].max() + pd.Timedelta(days=1),
        periods=periods,
        freq="D",
    )
    values = fitted.forecast(periods).clip(lower=0)
    return pd.DataFrame({"Date": dates, "ForecastVolume": values.round(0)})
