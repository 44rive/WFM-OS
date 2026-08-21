"""Deterministic planning transformations for WFM OS.

The module uses only the Python standard library and Decimal arithmetic. Inputs
are sequences of mappings so Excel wrappers remain thin and vendor-neutral.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
import re
from typing import Iterable, Mapping, Sequence


Record = Mapping[str, object]
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
INTERVAL_KEYS = tuple(f"I{index:02d}" for index in range(48))
PROFILE_TOLERANCE = Decimal("0.000000001")
WEEKDAYS = ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY")


def _date(value: object, field: str) -> date:
    if isinstance(value, datetime):
        raise ValueError(f"{field} must be a date, not a datetime")
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not ISO_DATE.fullmatch(value):
        raise ValueError(f"{field} must use strict YYYY-MM-DD format")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid date") from exc


def _decimal(value: object, field: str, *, minimum: Decimal | None = None) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric, not boolean")
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    if minimum is not None and result < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return result


def _approved(value: object, field: str = "ApprovedFlag") -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().upper() in {"TRUE", "FALSE"}:
        return value.strip().upper() == "TRUE"
    raise ValueError(f"{field} must be TRUE or FALSE")


def _text(row: Record, field: str) -> str:
    if field not in row:
        raise ValueError(f"Missing field: {field}")
    value = str(row[field]).strip()
    if not value:
        raise ValueError(f"{field} cannot be blank")
    return value


def _active(row: Record, as_of: date) -> bool:
    valid_from = _date(row.get("ValidFrom"), "ValidFrom")
    valid_to_value = row.get("ValidTo")
    valid_to = (
        _date(valid_to_value, "ValidTo")
        if valid_to_value is not None and str(valid_to_value).strip()
        else date.max
    )
    if valid_to < valid_from:
        raise ValueError("ValidTo cannot precede ValidFrom")
    return valid_from <= as_of <= valid_to


def _profile_for_date(
    approved_profiles: Sequence[Record], profile_key: str, forecast_date: date
) -> tuple[list[Record], str, str]:
    active = [row for row in approved_profiles if _text(row, "ProfileKey") == profile_key and _active(row, forecast_date)]
    weekday = WEEKDAYS[forecast_date.weekday()]
    exact = [row for row in active if _text(row, "DayType").upper() == weekday]
    selected = exact if exact else [row for row in active if _text(row, "DayType").upper() == "ALL"]
    selected_type = weekday if exact else "ALL"
    if not selected:
        raise ValueError(f"No active approved {weekday} or ALL profile for {profile_key} on {forecast_date}")
    by_interval: dict[str, Record] = {}
    for row in selected:
        interval_key = _text(row, "IntervalKey").upper()
        if interval_key not in INTERVAL_KEYS:
            raise ValueError(f"Invalid 30-minute IntervalKey: {interval_key}")
        if interval_key in by_interval:
            raise ValueError(f"Duplicate active profile interval {profile_key}/{selected_type}/{interval_key}")
        by_interval[interval_key] = row
    missing = sorted(set(INTERVAL_KEYS) - set(by_interval))
    if missing:
        raise ValueError(f"Profile {profile_key}/{selected_type} must contain all 48 intervals; missing {missing[0]}")
    ordered = [by_interval[key] for key in INTERVAL_KEYS]
    weights = [_decimal(row.get("VolumeWeight"), "VolumeWeight", minimum=Decimal(0)) for row in ordered]
    factors = [_decimal(row.get("AHTFactor"), "AHTFactor") for row in ordered]
    if any(factor <= 0 for factor in factors):
        raise ValueError("AHTFactor must be greater than zero")
    weight_sum = sum(weights, Decimal(0))
    if abs(weight_sum - Decimal(1)) > PROFILE_TOLERANCE:
        raise ValueError(f"VolumeWeight must sum to 1; received {weight_sum}")
    weighted_factor = sum((weight * factor for weight, factor in zip(weights, factors)), Decimal(0))
    if abs(weighted_factor - Decimal(1)) > PROFILE_TOLERANCE:
        raise ValueError(f"Volume-weighted AHTFactor must equal 1; received {weighted_factor}")
    valid_from_values = {_date(row.get("ValidFrom"), "ValidFrom").isoformat() for row in ordered}
    if len(valid_from_values) != 1:
        raise ValueError("Selected profile intervals must share one ValidFrom")
    return ordered, selected_type, next(iter(valid_from_values))


def intervalize_daily_candidates(
    candidate_rows: Iterable[Record], profile_rows: Iterable[Record]
) -> list[dict[str, object]]:
    """Allocate approved DAILY candidates to exact 30-minute interval profiles."""
    approved_candidates = []
    seen_candidates: set[tuple[date, str, str]] = set()
    for row in candidate_rows:
        if not _approved(row.get("ApprovedFlag")):
            continue
        if _text(row, "Grain").upper() != "DAILY":
            raise ValueError("Approved candidate Grain must be DAILY")
        forecast_date = _date(row.get("Date"), "Date")
        activity = _text(row, "ActivityKey")
        channel = _text(row, "ChannelKey")
        grain = (forecast_date, activity, channel)
        if grain in seen_candidates:
            raise ValueError(f"Duplicate approved DAILY candidate for {grain}")
        seen_candidates.add(grain)
        profile_key = _text(row, "IntradayProfileKey")
        approved_candidates.append((grain, profile_key, row))
    if not approved_candidates:
        raise ValueError("At least one approved DAILY candidate is required")
    approved_profiles = [row for row in profile_rows if _approved(row.get("ApprovedFlag"))]
    if not approved_profiles:
        raise ValueError("At least one approved intraday profile is required")

    output: list[dict[str, object]] = []
    for (forecast_date, activity, channel), profile_key, candidate in sorted(approved_candidates):
        daily_volume = _decimal(candidate.get("ForecastVolume"), "ForecastVolume", minimum=Decimal(0))
        daily_aht = _decimal(candidate.get("ForecastAHT"), "ForecastAHT", minimum=Decimal(0))
        if daily_volume > 0 and daily_aht <= 0:
            raise ValueError("ForecastAHT must be positive when ForecastVolume is positive")
        shrinkage = _decimal(candidate.get("Shrinkage"), "Shrinkage", minimum=Decimal(0))
        if shrinkage >= 1:
            raise ValueError("Shrinkage must be less than one")
        selected, day_type, profile_valid_from = _profile_for_date(approved_profiles, profile_key, forecast_date)
        raw_weights = [
            _decimal(profile.get("VolumeWeight"), "VolumeWeight", minimum=Decimal(0))
            for profile in selected
        ]
        weight_sum = sum(raw_weights, Decimal(0))
        allocated = Decimal(0)
        for index, (profile, raw_weight) in enumerate(zip(selected, raw_weights)):
            weight = raw_weight / weight_sum
            interval_volume = daily_volume - allocated if index == 47 else daily_volume * weight
            if index != 47:
                allocated += interval_volume
            if interval_volume < 0:
                raise ValueError("Normalized interval volume cannot be negative")
            factor = _decimal(profile.get("AHTFactor"), "AHTFactor")
            interval_start = datetime.combine(forecast_date, time()) + timedelta(minutes=30 * index)
            output.append(
                {
                    "Date": forecast_date.isoformat(),
                    "ActivityKey": activity,
                    "ChannelKey": channel,
                    "IntervalKey": INTERVAL_KEYS[index],
                    "IntervalStart": interval_start.isoformat(),
                    "ForecastVolume": interval_volume,
                    "ForecastAHT": daily_aht * factor,
                    "Shrinkage": shrinkage,
                    "IntradayProfileKey": profile_key,
                    "ProfileDayType": day_type,
                    "ProfileValidFrom": profile_valid_from,
                }
            )
    return output


def apply_approved_scenarios(
    base_rows: Iterable[Record], scenario_rows: Iterable[Record]
) -> list[dict[str, object]]:
    """Return complete BASE plus complete approved scenario interval outputs."""
    base: dict[tuple[date, str, str, str], Record] = {}
    for row in base_rows:
        forecast_date = _date(row.get("Date"), "Date")
        activity = _text(row, "ActivityKey")
        channel = _text(row, "ChannelKey")
        interval = _text(row, "IntervalKey").upper()
        if interval not in INTERVAL_KEYS:
            raise ValueError(f"Invalid IntervalKey: {interval}")
        grain = (forecast_date, activity, channel, interval)
        if grain in base:
            raise ValueError(f"Duplicate BASE interval grain: {grain}")
        base[grain] = row
    if not base:
        raise ValueError("BASE interval rows cannot be empty")

    scopes: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in scenario_rows:
        if not _approved(row.get("ApprovedFlag")):
            continue
        scenario = _text(row, "ScenarioKey")
        if scenario.upper() == "BASE":
            raise ValueError("ScenarioKey BASE is reserved")
        start = _date(row.get("StartDate"), "StartDate")
        end = _date(row.get("EndDate"), "EndDate")
        if end < start:
            raise ValueError("Scenario EndDate cannot precede StartDate")
        volume_change = _decimal(row.get("VolumeChangePct"), "VolumeChangePct")
        aht_change = _decimal(row.get("AHTChangePct"), "AHTChangePct")
        shrinkage_change = _decimal(row.get("ShrinkageChangePct"), "ShrinkageChangePct")
        scope = {
            "ActivityKey": _text(row, "ActivityKey"),
            "ChannelKey": _text(row, "ChannelKey"),
            "StartDate": start,
            "EndDate": end,
            "VolumeChangePct": volume_change,
            "AHTChangePct": aht_change,
            "ShrinkageChangePct": shrinkage_change,
        }
        scopes[scenario].append(scope)
    for scenario, rows in scopes.items():
        ordered = sorted(rows, key=lambda row: (row["ActivityKey"], row["ChannelKey"], row["StartDate"], row["EndDate"]))
        for prior, current in zip(ordered, ordered[1:]):
            same_grain = prior["ActivityKey"] == current["ActivityKey"] and prior["ChannelKey"] == current["ChannelKey"]
            if same_grain and current["StartDate"] <= prior["EndDate"]:
                raise ValueError(f"Duplicate or overlapping approved scope for scenario {scenario}")
        matched = False
        for scope in rows:
            if any(
                activity == scope["ActivityKey"] and channel == scope["ChannelKey"]
                and scope["StartDate"] <= forecast_date <= scope["EndDate"]
                for forecast_date, activity, channel, _ in base
            ):
                matched = True
            else:
                raise ValueError(f"Approved scenario {scenario} contains a scope matching no BASE row")
        if not matched:
            raise ValueError(f"Approved scenario {scenario} matches no BASE rows")

    output: list[dict[str, object]] = []
    for scenario in ["BASE", *sorted(scopes)]:
        for grain, source in sorted(base.items()):
            forecast_date, activity, channel, _ = grain
            matching = [] if scenario == "BASE" else [
                scope for scope in scopes[scenario]
                if scope["ActivityKey"] == activity and scope["ChannelKey"] == channel
                and scope["StartDate"] <= forecast_date <= scope["EndDate"]
            ]
            if len(matching) > 1:
                raise ValueError(f"More than one scenario scope matches {scenario}/{grain}")
            scope = matching[0] if matching else None
            volume_change = scope["VolumeChangePct"] if scope else Decimal(0)
            aht_change = scope["AHTChangePct"] if scope else Decimal(0)
            shrinkage_change = scope["ShrinkageChangePct"] if scope else Decimal(0)
            volume = _decimal(source.get("ForecastVolume"), "ForecastVolume", minimum=Decimal(0)) * (Decimal(1) + volume_change / 100)
            aht = _decimal(source.get("ForecastAHT"), "ForecastAHT", minimum=Decimal(0)) * (Decimal(1) + aht_change / 100)
            shrinkage = _decimal(source.get("Shrinkage"), "Shrinkage", minimum=Decimal(0)) * (Decimal(1) + shrinkage_change / 100)
            if volume < 0:
                raise ValueError(f"Scenario {scenario} produces negative volume")
            if volume > 0 and aht <= 0:
                raise ValueError(f"Scenario {scenario} must keep AHT positive when volume is positive")
            if shrinkage < 0 or shrinkage >= 1:
                raise ValueError(f"Scenario {scenario} produces invalid shrinkage")
            row = dict(source)
            row.update(
                {
                    "ScenarioKey": scenario,
                    "ForecastVolume": volume,
                    "ForecastAHT": aht,
                    "Shrinkage": shrinkage,
                    "VolumeChangePct": volume_change,
                    "AHTChangePct": aht_change,
                    "ShrinkageChangePct": shrinkage_change,
                }
            )
            output.append(row)
    return output


def aggregate_weekly_peak_capacity(capacity_rows: Iterable[Record]) -> list[dict[str, object]]:
    """Aggregate interval PaidFTE to Monday weeks using PEAK by scenario/activity."""
    seen: set[tuple[str, str, str, str, str]] = set()
    peaks: dict[tuple[date, str, str], Decimal] = {}
    activity_channels: dict[str, str] = {}
    for row in capacity_rows:
        raw_date = row.get("Date")
        if raw_date is None and row.get("IntervalStart") is not None:
            interval_text = str(row["IntervalStart"])
            raw_date = interval_text[:10]
        capacity_date = _date(raw_date, "Date")
        scenario = _text(row, "ScenarioKey")
        activity = _text(row, "ActivityKey")
        channel = _text(row, "ChannelKey")
        prior_channel = activity_channels.setdefault(activity, channel)
        if prior_channel != channel:
            raise ValueError(f"ActivityKey {activity} cannot span multiple ChannelKey values")
        interval = _text(row, "IntervalKey").upper()
        grain = (capacity_date.isoformat(), scenario, activity, channel, interval)
        if grain in seen:
            raise ValueError(f"Duplicate capacity candidate grain: {grain}")
        seen.add(grain)
        paid_fte = _decimal(row.get("PaidFTE"), "PaidFTE", minimum=Decimal(0))
        week_start = capacity_date - timedelta(days=capacity_date.weekday())
        key = (week_start, scenario, activity)
        peaks[key] = max(peaks.get(key, Decimal(0)), paid_fte)
    if not peaks:
        raise ValueError("Capacity candidates cannot be empty")
    return [
        {
            "PeriodStart": week.isoformat(),
            "ScenarioKey": scenario,
            "ActivityKey": activity,
            "AggregationMethod": "PEAK",
            "RequiredPaidFTE": paid_fte,
        }
        for (week, scenario, activity), paid_fte in sorted(peaks.items())
    ]
