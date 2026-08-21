"""Thin Python-in-Excel adapters around the governed planning calculation core.

This module intentionally contains table-shaping code only. It expects
``forecast.py`` and ``capacity.py`` to have been evaluated in earlier Python
cells, following the workbook Python manifest and row-major calculation order.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime


def _is_missing(value: object) -> bool:
    """Recognize Excel/pandas empty values without importing pandas."""
    if value is None:
        return True
    if type(value).__name__ in {"NAType", "NaTType"}:
        return True
    if isinstance(value, str):
        return value.strip() == "" or value.strip().upper() in {"NAN", "NAT"}
    try:
        return bool(value != value)
    except (TypeError, ValueError):
        return False


def _records(frame: object) -> list[dict[str, object]]:
    if not hasattr(frame, "to_dict"):
        raise ValueError("Python-in-Excel input must be a DataFrame-like object")
    output: list[dict[str, object]] = []
    for source in frame.to_dict("records"):
        row: dict[str, object] = {}
        for key, value in source.items():
            if _is_missing(value):
                row[str(key)] = None
            else:
                row[str(key)] = value
        output.append(row)
    return output


def _date_text(value: object, field: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "to_pydatetime"):
        converted = value.to_pydatetime()
        return converted.date().isoformat()
    text = str(value).strip()
    if len(text) >= 10:
        return text[:10]
    raise ValueError(f"{field} is not a usable date")


def _datetime_text(value: object, field: str) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime().isoformat()
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _truth(value: object, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().upper() in {"TRUE", "FALSE"}:
        return value.strip().upper() == "TRUE"
    raise ValueError(f"{field} must be TRUE or FALSE")


def parameter_value_excel(parameter_frame: object, parameter_name: str) -> object:
    """Return one nonblank governed value from ``tblParameters``."""
    matches = [
        row.get("Value")
        for row in _records(parameter_frame)
        if str(row.get("Parameter", "")).strip() == parameter_name
    ]
    if len(matches) != 1 or _is_missing(matches[0]):
        raise ValueError(f"Expected one nonblank tblParameters value for {parameter_name}")
    return matches[0]


def _active_policy(
    rows: list[dict[str, object]],
    *,
    profile: str,
    activity: str,
    channel: str,
    as_of_date: str,
) -> dict[str, object]:
    matches: list[dict[str, object]] = []
    for row in rows:
        if str(row.get("Profile", "")).strip() != profile:
            continue
        if str(row.get("ActivityKey", "")).strip() != activity:
            continue
        if str(row.get("ChannelKey", "")).strip() != channel:
            continue
        if not _truth(row.get("Approved"), "Approved"):
            continue
        valid_from = _date_text(row.get("ValidFrom"), "ValidFrom")
        valid_to_value = row.get("ValidTo")
        valid_to = _date_text(valid_to_value, "ValidTo") if not _is_missing(valid_to_value) else None
        if valid_from <= as_of_date and (valid_to is None or valid_to >= as_of_date):
            matches.append(row)
    if len(matches) != 1:
        raise ValueError(
            f"Expected one active approved policy for {profile}|{activity}|{channel}; found {len(matches)}"
        )
    return matches[0]


def _approved_adjustment_rows(
    event_rows: list[dict[str, object]],
    override_rows: list[dict[str, object]],
    *,
    profile: str,
    impact_type: str,
    override_value_field: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    impacts: list[dict[str, object]] = []
    for row in event_rows:
        if str(row.get("Profile", "")).strip() != profile:
            continue
        if str(row.get("ImpactType", "")).strip().upper() != impact_type:
            continue
        impacts.append(
            {
                "EventKey": row.get("EventKey"),
                "ActivityKey": row.get("ActivityKey"),
                "ChannelKey": row.get("ChannelKey"),
                "StartDate": _date_text(row.get("StartAt"), "StartAt"),
                "EndDate": _date_text(row.get("EndAt"), "EndAt"),
                "ImpactPercent": row.get("ImpactValue"),
                "ApprovedFlag": row.get("Approved"),
            }
        )
    overrides: list[dict[str, object]] = []
    for row in override_rows:
        if str(row.get("Profile", "")).strip() != profile:
            continue
        status = str(row.get("ApprovalStatus", "")).strip().upper()
        value = row.get(override_value_field)
        if status != "APPROVED" or _is_missing(value):
            continue
        overrides.append(
            {
                "OverrideKey": row.get("OverrideKey"),
                "ActivityKey": row.get("ActivityKey"),
                "ChannelKey": row.get("ChannelKey"),
                "Date": _date_text(row.get("ForecastDate"), "ForecastDate"),
                "OverrideValue": value,
                "ApprovedFlag": True,
            }
        )
    return impacts, overrides


def run_forecast_excel(
    history_frame: object,
    policy_frame: object,
    calendar_frame: object,
    override_frame: object,
    *,
    profile: str,
    as_of_date: object,
) -> list[dict[str, object]]:
    """Return adjusted daily forecast candidates from governed workbook data."""
    as_of = _date_text(as_of_date, "as_of_date")
    history_rows = _records(history_frame)
    policy_rows = _records(policy_frame)
    event_rows = _records(calendar_frame)
    override_rows = _records(override_frame)

    daily: dict[tuple[str, str, str], dict[str, float]] = defaultdict(
        lambda: {"Volume": 0.0, "Handled": 0.0, "HandleSeconds": 0.0}
    )
    for row in history_rows:
        activity = str(row.get("ActivityKey", "")).strip()
        channel = str(row.get("ChannelKey", "")).strip()
        observed_date = _date_text(row.get("Date"), "Date")
        if observed_date > as_of:
            continue
        if not activity or not channel:
            raise ValueError("Forecast history requires ActivityKey and ChannelKey")
        key = (activity, channel, observed_date)
        daily[key]["Volume"] += float(row.get("Volume") or 0)
        daily[key]["Handled"] += float(row.get("Handled") or 0)
        daily[key]["HandleSeconds"] += float(row.get("HandleSeconds") or 0)

    by_group: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for (activity, channel, observed_date), totals in sorted(daily.items()):
        if totals["Handled"] <= 0:
            raise ValueError(f"Daily AHT is undefined for {activity}|{channel}|{observed_date}")
        by_group[(activity, channel)].append(
            {
                "Date": observed_date,
                "ActivityKey": activity,
                "ChannelKey": channel,
                "Volume": totals["Volume"],
                "AHTSeconds": totals["HandleSeconds"] / totals["Handled"],
            }
        )

    volume_baseline: list[dict[str, object]] = []
    aht_baseline: list[dict[str, object]] = []
    for (activity, channel), rows in sorted(by_group.items()):
        policy = _active_policy(
            policy_rows,
            profile=profile,
            activity=activity,
            channel=channel,
            as_of_date=as_of,
        )
        if str(policy.get("Method", "")).strip().upper() != "SEASONAL_NAIVE":
            raise ValueError("Only SEASONAL_NAIVE is implemented in the governed baseline")
        if str(policy.get("Frequency", "")).strip().upper() != "DAILY":
            raise ValueError("Only DAILY forecast frequency is implemented")
        history_periods = int(policy.get("HistoryPeriods"))
        horizon_periods = int(policy.get("HorizonPeriods"))
        season_length = int(policy.get("SeasonLength"))
        minimum_history = int(policy.get("MinimumHistory"))
        scoped = rows[-history_periods:]
        if len(scoped) < minimum_history:
            raise ValueError(f"History is below MinimumHistory for {activity}|{channel}")
        volume_baseline.extend(
            seasonal_naive_forecast(
                scoped,
                periods=horizon_periods,
                seasonal_periods=season_length,
                value_field="Volume",
            )
        )
        aht_rows = [dict(row, AHTValue=row["AHTSeconds"]) for row in scoped]
        aht_baseline.extend(
            seasonal_naive_forecast(
                aht_rows,
                periods=horizon_periods,
                seasonal_periods=season_length,
                value_field="AHTValue",
            )
        )

    volume_impacts, volume_overrides = _approved_adjustment_rows(
        event_rows,
        override_rows,
        profile=profile,
        impact_type="VOLUME_PCT",
        override_value_field="ForecastVolume",
    )
    aht_impacts, aht_overrides = _approved_adjustment_rows(
        event_rows,
        override_rows,
        profile=profile,
        impact_type="AHT_PCT",
        override_value_field="ForecastAHTSeconds",
    )
    adjusted_volume = apply_approved_adjustments(volume_baseline, volume_impacts, volume_overrides)
    adjusted_aht = apply_approved_adjustments(aht_baseline, aht_impacts, aht_overrides)
    aht_by_grain = {
        (row["ActivityKey"], row["ChannelKey"], row["Date"]): row
        for row in adjusted_aht
    }
    output: list[dict[str, object]] = []
    for volume_row in adjusted_volume:
        grain = (volume_row["ActivityKey"], volume_row["ChannelKey"], volume_row["Date"])
        aht_row = aht_by_grain[grain]
        output.append(
            {
                "Profile": profile,
                "Date": volume_row["Date"],
                "ActivityKey": volume_row["ActivityKey"],
                "ChannelKey": volume_row["ChannelKey"],
                "Method": "SEASONAL_NAIVE",
                "ForecastVolume": volume_row["FinalForecast"],
                "ForecastAHTSeconds": aht_row["FinalForecast"],
                "VolumeAdjustmentSource": volume_row["AdjustmentSource"],
                "AHTAdjustmentSource": aht_row["AdjustmentSource"],
                "AppliedVolumeEventKeys": volume_row["AppliedEventKeys"],
                "AppliedAHTEventKeys": aht_row["AppliedEventKeys"],
            }
        )
    return output


def run_capacity_excel(
    forecast_frame: object,
    policy_frame: object,
    *,
    profile: str,
) -> list[dict[str, object]]:
    """Return capacity candidates for approved interval forecast rows."""
    forecasts = _records(forecast_frame)
    policies = _records(policy_frame)
    output: list[dict[str, object]] = []
    for forecast in forecasts:
        if "ApprovalStatus" in forecast and str(forecast.get("ApprovalStatus", "")).strip().upper() != "APPROVED":
            raise ValueError("Capacity inputs must be approved interval forecast rows")
        activity = str(forecast.get("ActivityKey", "")).strip()
        channel = str(forecast.get("ChannelKey", "")).strip()
        if not activity or not channel:
            raise ValueError("Capacity input requires ActivityKey and ChannelKey")
        interval_text = _datetime_text(forecast.get("IntervalStart"), "IntervalStart")
        policy = _active_policy(
            policies,
            profile=profile,
            activity=activity,
            channel=channel,
            as_of_date=interval_text[:10],
        )
        method = str(policy.get("Method", "")).strip().upper()
        calculation_row = {
            "Method": method,
            "Volume": forecast.get("ForecastVolume"),
            "AHTSeconds": forecast.get("ForecastAHTSeconds"),
            "IntervalMinutes": policy.get("IntervalMinutes"),
            "TargetServiceLevel": policy.get("TargetServiceLevel"),
            "AnswerTimeSeconds": policy.get("AnswerTimeSeconds"),
            "Occupancy": policy.get("MaxOccupancy"),
            "Concurrency": policy.get("Concurrency"),
            "Shrinkage": policy.get("ShrinkagePct"),
            "FTEPerHead": policy.get("FTEPerHead"),
        }
        result = calculate_capacity_row(calculation_row)
        forecast_version = str(forecast.get("ForecastVersionKey", "")).strip()
        if not forecast_version:
            raise ValueError("Capacity input requires ForecastVersionKey")
        policy_key = str(policy.get("PolicyKey", "")).strip()
        compact_interval = interval_text.replace("-", "").replace(":", "").replace("T", "")[:12]
        requirement_key = "|".join((forecast_version, policy_key, compact_interval, activity))
        output.append(
            {
                "RequirementKey": requirement_key,
                "Profile": profile,
                "ForecastVersionKey": forecast_version,
                "CapacityPolicyKey": policy_key,
                "IntervalStart": interval_text,
                "ActivityKey": activity,
                "ChannelKey": channel,
                "ForecastVolume": forecast.get("ForecastVolume"),
                "ForecastAHTSeconds": forecast.get("ForecastAHTSeconds"),
                "RequiredFTE": result["ProductiveFTE"],
                "PaidFTE": result["PaidFTE"],
                "RequiredHeads": result["RequiredHeads"],
                "ShrinkagePct": policy.get("ShrinkagePct"),
                "RequirementVersion": f"{forecast_version}|{policy_key}",
                "Method": result["Method"],
                "AchievedOccupancy": result["AchievedOccupancy"],
                "AchievedServiceLevel": result["AchievedServiceLevel"],
            }
        )
    return output
