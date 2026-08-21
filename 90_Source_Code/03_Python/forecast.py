"""Deterministic, dependency-free forecasting helpers for WFM OS.

The functions operate on sequences of mappings so they can be tested without
Excel, pandas, or a vendor SDK. Python-in-Excel wrappers may convert worksheet
tables to and from these records, but the calculation contract stays here.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Iterable, Mapping, Sequence


Record = Mapping[str, object]
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _strict_date(value: object, field: str) -> date:
    """Accept a date or strict YYYY-MM-DD text; reject datetime grain."""
    if isinstance(value, datetime):
        raise ValueError(f"{field} must be a date, not a datetime")
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not ISO_DATE.fullmatch(value):
        raise ValueError(f"{field} must use strict YYYY-MM-DD format")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid calendar date: {value!r}") from exc


def _finite_number(value: object, field: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric, not boolean")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    if number < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return number


def _approved(value: object, field: str = "ApprovedFlag") -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().upper() in {"TRUE", "FALSE"}:
        return value.strip().upper() == "TRUE"
    raise ValueError(f"{field} must be TRUE or FALSE")


def _group_key(row: Record, group_fields: Sequence[str]) -> tuple[str, ...]:
    values: list[str] = []
    for field in group_fields:
        if field not in row:
            raise ValueError(f"Missing group field: {field}")
        value = str(row[field]).strip()
        if not value:
            raise ValueError(f"Group field {field} cannot be blank")
        values.append(value)
    return tuple(values)


def _validate_group_fields(group_fields: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(group_fields)
    if not normalized:
        raise ValueError("At least one group field is required")
    if len(normalized) != len(set(normalized)):
        raise ValueError("Group fields must be unique")
    return normalized


def seasonal_naive_forecast(
    history: Iterable[Record],
    *,
    periods: int,
    seasonal_periods: int,
    group_fields: Sequence[str] = ("ActivityKey", "ChannelKey"),
    date_field: str = "Date",
    value_field: str = "Volume",
) -> list[dict[str, object]]:
    """Forecast each strict daily group by repeating its latest season.

    Every group must contain unique, contiguous daily observations and at least
    one complete season. Forecasts beyond one season recursively repeat the
    generated seasonal pattern. Output ordering is stable by group then date.
    """
    groups = _validate_group_fields(group_fields)
    if isinstance(periods, bool) or not isinstance(periods, int) or periods <= 0:
        raise ValueError("periods must be a positive integer")
    if isinstance(seasonal_periods, bool) or not isinstance(seasonal_periods, int) or seasonal_periods <= 0:
        raise ValueError("seasonal_periods must be a positive integer")

    observations: dict[tuple[str, ...], dict[date, float]] = defaultdict(dict)
    for row_number, row in enumerate(history, start=1):
        key = _group_key(row, groups)
        if date_field not in row or value_field not in row:
            raise ValueError(f"History row {row_number} is missing {date_field} or {value_field}")
        observed_date = _strict_date(row[date_field], date_field)
        value = _finite_number(row[value_field], value_field)
        if observed_date in observations[key]:
            raise ValueError(f"Duplicate history grain for {key} on {observed_date.isoformat()}")
        observations[key][observed_date] = value
    if not observations:
        raise ValueError("History cannot be empty")

    output: list[dict[str, object]] = []
    for key in sorted(observations):
        known = observations[key]
        dates = sorted(known)
        if len(dates) < seasonal_periods:
            raise ValueError(f"Group {key} requires at least {seasonal_periods} observations")
        for prior, current in zip(dates, dates[1:]):
            if current - prior != timedelta(days=1):
                raise ValueError(f"Group {key} has a missing daily observation after {prior.isoformat()}")
        latest = dates[-1]
        for step in range(1, periods + 1):
            forecast_date = latest + timedelta(days=step)
            seasonal_date = forecast_date - timedelta(days=seasonal_periods)
            if seasonal_date not in known:
                raise ValueError(f"Group {key} has no seasonal source for {forecast_date.isoformat()}")
            forecast_value = known[seasonal_date]
            known[forecast_date] = forecast_value
            row = {field: key[index] for index, field in enumerate(groups)}
            row.update({"Date": forecast_date.isoformat(), "BaselineForecast": forecast_value})
            output.append(row)
    return output


def score_backtest(
    rows: Iterable[Record],
    *,
    group_fields: Sequence[str] = ("ActivityKey", "ChannelKey"),
    date_field: str = "Date",
    actual_field: str = "Actual",
    forecast_field: str = "Forecast",
) -> list[dict[str, object]]:
    """Score grouped backtests with explicit zero-actual behavior.

    Error and bias use ``forecast - actual``; positive signed bias therefore
    means over-forecast. WAPE and signed bias are returned in percentage points.
    When a group's total actual is zero, both percentage metrics are ``None``
    while MAE and RMSE remain defined.
    """
    groups = _validate_group_fields(group_fields)
    grouped: dict[tuple[str, ...], list[tuple[float, float]]] = defaultdict(list)
    seen: set[tuple[tuple[str, ...], date]] = set()
    for row_number, row in enumerate(rows, start=1):
        key = _group_key(row, groups)
        if date_field not in row or actual_field not in row or forecast_field not in row:
            raise ValueError(f"Backtest row {row_number} is missing a required field")
        observed_date = _strict_date(row[date_field], date_field)
        grain = (key, observed_date)
        if grain in seen:
            raise ValueError(f"Duplicate backtest grain for {key} on {observed_date.isoformat()}")
        seen.add(grain)
        actual = _finite_number(row[actual_field], actual_field)
        forecast = _finite_number(row[forecast_field], forecast_field)
        grouped[key].append((actual, forecast))
    if not grouped:
        raise ValueError("Backtest rows cannot be empty")

    output: list[dict[str, object]] = []
    for key in sorted(grouped):
        pairs = grouped[key]
        actual_total = sum(actual for actual, _ in pairs)
        forecast_total = sum(forecast for _, forecast in pairs)
        errors = [forecast - actual for actual, forecast in pairs]
        absolute_error = sum(abs(error) for error in errors)
        squared_error = sum(error * error for error in errors)
        denominator_defined = actual_total != 0
        row = {field: key[index] for index, field in enumerate(groups)}
        row.update(
            {
                "ObservationCount": len(pairs),
                "ActualTotal": actual_total,
                "ForecastTotal": forecast_total,
                "WAPEPercent": (absolute_error / actual_total * 100.0) if denominator_defined else None,
                "SignedBiasPercent": (sum(errors) / actual_total * 100.0) if denominator_defined else None,
                "MAE": absolute_error / len(pairs),
                "RMSE": math.sqrt(squared_error / len(pairs)),
                "ZeroActualPolicy": "DEFINED" if denominator_defined else "UNDEFINED_DENOMINATOR",
            }
        )
        output.append(row)
    return output


def apply_approved_adjustments(
    forecast_rows: Iterable[Record],
    calendar_impacts: Iterable[Record],
    overrides: Iterable[Record],
    *,
    group_fields: Sequence[str] = ("ActivityKey", "ChannelKey"),
) -> list[dict[str, object]]:
    """Apply approved additive calendar percentages, then absolute overrides.

    Percentage impacts that overlap the same forecast grain are summed and
    applied once to baseline. At most one approved absolute override may exist
    for a grain/date; it replaces the post-calendar value and therefore has
    final precedence. Approved adjustments that match no forecast row fail.
    """
    groups = _validate_group_fields(group_fields)
    base: dict[tuple[tuple[str, ...], date], float] = {}
    for row_number, row in enumerate(forecast_rows, start=1):
        key = _group_key(row, groups)
        if "Date" not in row or "BaselineForecast" not in row:
            raise ValueError(f"Forecast row {row_number} is missing Date or BaselineForecast")
        forecast_date = _strict_date(row["Date"], "Date")
        grain = (key, forecast_date)
        if grain in base:
            raise ValueError(f"Duplicate forecast grain for {key} on {forecast_date.isoformat()}")
        base[grain] = _finite_number(row["BaselineForecast"], "BaselineForecast")
    if not base:
        raise ValueError("Forecast rows cannot be empty")

    impact_percent: dict[tuple[tuple[str, ...], date], float] = defaultdict(float)
    impact_keys: dict[tuple[tuple[str, ...], date], list[str]] = defaultdict(list)
    for row_number, impact in enumerate(calendar_impacts, start=1):
        if not _approved(impact.get("ApprovedFlag"), "ApprovedFlag"):
            continue
        key = _group_key(impact, groups)
        start = _strict_date(impact.get("StartDate"), "StartDate")
        end = _strict_date(impact.get("EndDate"), "EndDate")
        if end < start:
            raise ValueError(f"Calendar impact row {row_number} ends before it starts")
        percent = _finite_number(impact.get("ImpactPercent"), "ImpactPercent", minimum=-100.0)
        event_key = str(impact.get("EventKey", "")).strip()
        if not event_key:
            raise ValueError("Approved calendar impact requires EventKey")
        matched = False
        current = start
        while current <= end:
            grain = (key, current)
            if grain in base:
                impact_percent[grain] += percent
                impact_keys[grain].append(event_key)
                matched = True
            current += timedelta(days=1)
        if not matched:
            raise ValueError(f"Approved calendar impact {event_key} matches no forecast grain")
    for grain, total_percent in impact_percent.items():
        if total_percent < -100.0:
            key, impacted_date = grain
            raise ValueError(
                f"Combined calendar impact is below -100 for {key} on {impacted_date.isoformat()}"
            )

    absolute: dict[tuple[tuple[str, ...], date], tuple[str, float]] = {}
    for row_number, override in enumerate(overrides, start=1):
        if not _approved(override.get("ApprovedFlag"), "ApprovedFlag"):
            continue
        key = _group_key(override, groups)
        override_date = _strict_date(override.get("Date"), "Date")
        grain = (key, override_date)
        if grain not in base:
            raise ValueError(f"Approved override row {row_number} matches no forecast grain")
        if grain in absolute:
            raise ValueError(f"More than one approved absolute override exists for {key} on {override_date}")
        override_key = str(override.get("OverrideKey", "")).strip()
        if not override_key:
            raise ValueError("Approved absolute override requires OverrideKey")
        absolute[grain] = (override_key, _finite_number(override.get("OverrideValue"), "OverrideValue"))

    output: list[dict[str, object]] = []
    for (key, forecast_date), baseline in sorted(base.items()):
        percent = impact_percent[(key, forecast_date)]
        post_calendar = baseline * (1.0 + percent / 100.0)
        override = absolute.get((key, forecast_date))
        final = override[1] if override else post_calendar
        source = "ABSOLUTE_OVERRIDE" if override else "CALENDAR" if percent else "BASELINE"
        row = {field: key[index] for index, field in enumerate(groups)}
        row.update(
            {
                "Date": forecast_date.isoformat(),
                "BaselineForecast": baseline,
                "CalendarImpactPercent": percent,
                "AppliedEventKeys": "|".join(sorted(impact_keys[(key, forecast_date)])),
                "PostCalendarForecast": post_calendar,
                "AbsoluteOverride": override[1] if override else None,
                "OverrideKey": override[0] if override else "",
                "FinalForecast": final,
                "AdjustmentSource": source,
            }
        )
        output.append(row)
    return output
