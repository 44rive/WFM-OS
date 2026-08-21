"""Thin Python-in-Excel adapters around the governed planning calculation core.

This module intentionally contains table-shaping code only. It expects
``forecast.py``, ``capacity.py``, ``planning.py``, ``supply.py``,
``scheduling.py``, ``leave.py``, ``roster.py``, ``leave_requests.py``, and
``swaps.py`` to have been evaluated in earlier Python cells, following the
workbook Python manifest and row-major calculation order.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal


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


def _plain(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _plain_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{key: _plain(value) for key, value in row.items()} for row in rows]


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
    intraday_profile_by_group: dict[tuple[str, str], str] = {}
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
        intraday_profile = str(policy.get("IntradayProfileKey", "")).strip()
        if not intraday_profile:
            raise ValueError(f"Forecast policy requires IntradayProfileKey for {activity}|{channel}")
        intraday_profile_by_group[(activity, channel)] = intraday_profile
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
                "Grain": "DAILY",
                "IntradayProfileKey": intraday_profile_by_group[
                    (volume_row["ActivityKey"], volume_row["ChannelKey"])
                ],
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
    scenario_frame: object | None = None,
    *,
    profile: str,
) -> list[dict[str, object]]:
    """Return capacity candidates for approved interval forecast rows."""
    forecasts = _records(forecast_frame)
    policies = _records(policy_frame)
    scenario_rows = _records(scenario_frame) if scenario_frame is not None else []
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
        scenario_key = str(
            forecast.get("ScenarioKey", forecast.get("Scenario", "BASE")) or "BASE"
        ).strip().upper()
        shrinkage_change = 0.0
        if scenario_key != "BASE":
            interval_date = interval_text[:10]
            matches = []
            for scenario in scenario_rows:
                if str(scenario.get("Profile", "")).strip() != profile:
                    continue
                if str(scenario.get("ScenarioKey", "")).strip().upper() != scenario_key:
                    continue
                if str(scenario.get("ApprovalStatus", "")).strip().upper() != "APPROVED":
                    continue
                if str(scenario.get("ActivityKey", "")).strip() != activity:
                    continue
                if str(scenario.get("ChannelKey", "")).strip() != channel:
                    continue
                start = _date_text(scenario.get("StartDate"), "StartDate")
                end = _date_text(scenario.get("EndDate"), "EndDate")
                if start <= interval_date <= end:
                    matches.append(scenario)
            if len(matches) != 1:
                raise ValueError(
                    f"Expected one approved scenario scope for {scenario_key}|{activity}|{channel}|{interval_date}; found {len(matches)}"
                )
            shrinkage_change = float(matches[0].get("ShrinkageChangePct") or 0)
        shrinkage = float(policy.get("ShrinkagePct")) * (1.0 + shrinkage_change / 100.0)
        if not 0 <= shrinkage < 1:
            raise ValueError(f"Scenario {scenario_key} produces invalid shrinkage")
        calculation_row = {
            "Method": method,
            "Volume": forecast.get("ForecastVolume"),
            "AHTSeconds": forecast.get("ForecastAHTSeconds"),
            "IntervalMinutes": policy.get("IntervalMinutes"),
            "TargetServiceLevel": policy.get("TargetServiceLevel"),
            "AnswerTimeSeconds": policy.get("AnswerTimeSeconds"),
            "Occupancy": policy.get("MaxOccupancy"),
            "Concurrency": policy.get("Concurrency"),
            "Shrinkage": shrinkage,
            "FTEPerHead": policy.get("FTEPerHead"),
        }
        result = calculate_capacity_row(calculation_row)
        forecast_version = str(forecast.get("ForecastVersionKey", "")).strip()
        if not forecast_version:
            raise ValueError("Capacity input requires ForecastVersionKey")
        policy_key = str(policy.get("PolicyKey", "")).strip()
        compact_interval = interval_text.replace("-", "").replace(":", "").replace("T", "")[:12]
        requirement_key = "|".join((forecast_version, scenario_key, policy_key, compact_interval, activity))
        output.append(
            {
                "RequirementKey": requirement_key,
                "Profile": profile,
                "ForecastVersionKey": forecast_version,
                "CapacityPolicyKey": policy_key,
                "ScenarioKey": scenario_key,
                "IntervalStart": interval_text,
                "ActivityKey": activity,
                "ChannelKey": channel,
                "ForecastVolume": forecast.get("ForecastVolume"),
                "ForecastAHTSeconds": forecast.get("ForecastAHTSeconds"),
                "RequiredFTE": result["ProductiveFTE"],
                "PaidFTE": result["PaidFTE"],
                "RequiredHeads": result["RequiredHeads"],
                "ShrinkagePct": shrinkage,
                "RequirementVersion": f"{forecast_version}|{scenario_key}|{policy_key}",
                "Method": result["Method"],
                "AchievedOccupancy": result["AchievedOccupancy"],
                "AchievedServiceLevel": result["AchievedServiceLevel"],
            }
        )
    return output


def run_intraday_excel(
    daily_frame: object,
    profile_frame: object,
    scenario_frame: object,
    *,
    profile: str,
) -> list[dict[str, object]]:
    """Return complete BASE and approved scenario interval candidates."""
    daily_rows = []
    for row in _records(daily_frame):
        if str(row.get("Profile", "")).strip() not in {"", profile}:
            continue
        if "ApprovalStatus" in row:
            approved = str(row.get("ApprovalStatus", "")).strip().upper() == "APPROVED"
        elif "ApprovedFlag" in row:
            approved = _truth(row.get("ApprovedFlag"), "ApprovedFlag")
        elif "Approved" in row:
            approved = _truth(row.get("Approved"), "Approved")
        else:
            approved = True
        daily_rows.append(
            {
                **row,
                "ForecastAHT": row.get("ForecastAHTSeconds"),
                "Shrinkage": 0,
                "ApprovedFlag": approved,
            }
        )
    profiles = [
        {
            **row,
            "ApprovedFlag": row.get("Approved"),
        }
        for row in _records(profile_frame)
        if str(row.get("Profile", "")).strip() == profile
    ]
    scenarios = [
        {
            **row,
            "ApprovedFlag": str(row.get("ApprovalStatus", "")).strip().upper() == "APPROVED",
        }
        for row in _records(scenario_frame)
        if str(row.get("Profile", "")).strip() == profile
    ]
    intervals = intervalize_daily_candidates(daily_rows, profiles)
    scenario_intervals = apply_approved_scenarios(intervals, scenarios)
    output: list[dict[str, object]] = []
    for row in scenario_intervals:
        candidate = dict(row)
        candidate["Profile"] = profile
        candidate["Scenario"] = candidate.pop("ScenarioKey")
        candidate["ForecastAHTSeconds"] = candidate.pop("ForecastAHT")
        candidate.pop("Shrinkage", None)
        output.append(candidate)
    return _plain_rows(output)


def run_supply_excel(
    requirement_frame: object,
    workforce_snapshot_frame: object,
    assumption_frame: object,
    policy_frame: object,
    *,
    profile: str,
    as_of_date: object,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return weekly supply/gap and hiring-wave candidates from approved requirements."""
    requirements = _records(requirement_frame)
    weekly = aggregate_weekly_peak_capacity(requirements)
    weeks_by_activity: dict[str, set[str]] = defaultdict(set)
    for row in weekly:
        weeks_by_activity[str(row["ActivityKey"])].add(str(row["PeriodStart"]))

    snapshot: dict[str, float] = {}
    for row in _records(workforce_snapshot_frame):
        activity = str(row.get("ActivityKey", "")).strip()
        if not activity:
            continue
        if activity in snapshot:
            raise ValueError(f"Duplicate workforce supply snapshot for {activity}")
        snapshot[activity] = float(row.get("OpeningPaidFTE"))

    approved_assumptions: dict[tuple[str, str], dict[str, object]] = {}
    for row in _records(assumption_frame):
        if str(row.get("Profile", "")).strip() != profile:
            continue
        if str(row.get("ApprovalStatus", "")).strip().upper() != "APPROVED":
            continue
        activity = str(row.get("ActivityKey", "")).strip()
        period = _date_text(row.get("PeriodStart"), "PeriodStart")
        key = (activity, period)
        if key in approved_assumptions:
            raise ValueError(f"Duplicate approved supply assumption for {activity}|{period}")
        approved_assumptions[key] = row

    core_assumptions: list[dict[str, object]] = []
    for activity, periods in sorted(weeks_by_activity.items()):
        ordered_periods = sorted(periods)
        if activity not in snapshot:
            raise ValueError(f"Workforce supply snapshot is missing {activity}")
        for index, period in enumerate(ordered_periods):
            source = approved_assumptions.get((activity, period), {})
            opening = source.get("OpeningPaidFTE")
            if index == 0 and _is_missing(opening):
                opening = snapshot[activity]
            core_assumptions.append(
                {
                    "PeriodStart": period,
                    "ActivityKey": activity,
                    "OpeningPaidFTE": opening if index == 0 else source.get("OpeningPaidFTE"),
                    "TransfersInFTE": source.get("TransfersInFTE") or 0,
                    "TransfersOutFTE": source.get("TransfersOutFTE") or 0,
                    "LeaversFTE": source.get("LeaversFTE") or 0,
                    "OtherChangeFTE": source.get("OtherChangeFTE") or 0,
                    "ApprovedFlag": True,
                }
            )
    base_supply = project_base_paid_supply(core_assumptions)
    policies = [
        {**row, "ApprovedFlag": row.get("Approved")}
        for row in _records(policy_frame)
        if str(row.get("Profile", "")).strip() == profile
    ]
    supply_rows, hiring_rows = plan_hiring(
        weekly,
        base_supply,
        policies,
        as_of_date=_date_text(as_of_date, "as_of_date"),
    )
    return (
        _plain_rows([{**row, "Profile": profile} for row in supply_rows]),
        _plain_rows([{**row, "Profile": profile} for row in hiring_rows]),
    )


def run_schedule_excel(
    requirement_frame: object,
    pattern_frame: object,
    rule_frame: object,
    *,
    profile: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return anonymous pattern-count and interval-coverage candidates."""
    requirements: list[dict[str, object]] = []
    for row in _records(requirement_frame):
        row_profile = str(row.get("Profile") or "").strip()
        if row_profile not in {"", profile}:
            continue
        if "ApprovalStatus" in row and str(row.get("ApprovalStatus") or "").strip().upper() != "APPROVED":
            raise ValueError("Schedule inputs must be approved interval requirement rows")
        requirements.append(row)

    patterns = [
        {**row, "ApprovedFlag": row.get("Approved")}
        for row in _records(pattern_frame)
        if str(row.get("Profile") or "").strip() == profile
    ]
    rules = [
        {**row, "ApprovedFlag": row.get("Approved")}
        for row in _records(rule_frame)
        if str(row.get("Profile") or "").strip() == profile
    ]
    plan_rows, coverage_rows = fit_shift_patterns(requirements, patterns, rules)
    return (
        _plain_rows([{**row, "Profile": profile} for row in plan_rows]),
        _plain_rows([{**row, "Profile": profile} for row in coverage_rows]),
    )


def run_leave_excel(
    schedule_coverage_frame: object,
    policy_frame: object,
    *,
    profile: str,
) -> list[dict[str, object]]:
    """Return interval leave-capacity candidates from approved schedule coverage."""
    coverage: list[dict[str, object]] = []
    for row in _records(schedule_coverage_frame):
        row_profile = str(row.get("Profile") or "").strip()
        if row_profile not in {"", profile}:
            continue
        if "ApprovalStatus" in row and str(row.get("ApprovalStatus") or "").strip().upper() != "APPROVED":
            raise ValueError("Leave inputs must be approved schedule coverage rows")
        coverage.append(row)
    policies = [
        {**row, "ApprovedFlag": row.get("Approved")}
        for row in _records(policy_frame)
        if str(row.get("Profile") or "").strip() == profile
    ]
    return _plain_rows(
        [{**row, "Profile": profile} for row in calculate_leave_allowance(coverage, policies)]
    )


def _profile_rows(frame: object, profile: str) -> list[dict[str, object]]:
    return [
        row for row in _records(frame)
        if str(row.get("Profile") or "").strip() in {"", profile}
    ]


def _approved_profile_rows(frame: object, profile: str) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in _profile_rows(frame, profile):
        if "ApprovalStatus" in row:
            if str(row.get("ApprovalStatus") or "").strip().upper() != "APPROVED":
                continue
        elif "Approved" in row and not _truth(row.get("Approved"), "Approved"):
            continue
        output.append(row)
    return output


def _public_roster_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {key: value for key, value in row.items() if key not in {"Occurrence", "Segments"}}
        for row in rows
    ]


roster_segment_candidates: list[dict[str, object]] = []
roster_diagnostic_candidates: list[dict[str, object]] = []
roster_period_candidates: list[dict[str, object]] = []
leave_consumption_candidates: list[dict[str, object]] = []
swap_proposal_candidates: list[dict[str, object]] = []
swap_diagnostic_candidates: list[dict[str, object]] = []


def run_roster_excel(
    schedule_plan_frame: object,
    pattern_frame: object,
    coverage_frame: object,
    people_frame: object,
    roster_policy_frame: object,
    contract_frame: object,
    eligibility_frame: object,
    agent_skill_frame: object,
    skill_requirement_frame: object,
    availability_frame: object,
    preference_frame: object,
    *,
    profile: str,
) -> list[dict[str, object]]:
    """Return named-roster candidates and retain governed companion outputs."""
    global roster_segment_candidates, roster_diagnostic_candidates, roster_period_candidates
    schedule_plan = _approved_profile_rows(schedule_plan_frame, profile)
    coverage = _approved_profile_rows(coverage_frame, profile)
    patterns = [
        {**row, "ApprovedFlag": row.get("Approved")}
        for row in _profile_rows(pattern_frame, profile)
    ]
    assignments, segments, diagnostics, periods = assign_named_roster(
        schedule_plan,
        patterns,
        coverage,
        _profile_rows(people_frame, profile),
        _profile_rows(roster_policy_frame, profile),
        _profile_rows(contract_frame, profile),
        _profile_rows(eligibility_frame, profile),
        _profile_rows(agent_skill_frame, profile),
        _profile_rows(skill_requirement_frame, profile),
        _profile_rows(availability_frame, profile),
        _profile_rows(preference_frame, profile),
    )
    roster_segment_candidates = _plain_rows([{**row, "Profile": profile} for row in segments])
    roster_diagnostic_candidates = _plain_rows([{**row, "Profile": profile} for row in diagnostics])
    roster_period_candidates = _plain_rows([{**row, "Profile": profile} for row in periods])
    return _plain_rows(
        [{**row, "Profile": profile} for row in _public_roster_rows(assignments)]
    )


def run_leave_requests_excel(
    roster_frame: object,
    schedule_plan_frame: object,
    pattern_frame: object,
    leave_plan_frame: object,
    request_frame: object,
    leave_type_policy_frame: object,
    entitlement_frame: object,
    prior_decision_frame: object,
    swap_decision_frame: object,
    *,
    profile: str,
) -> list[dict[str, object]]:
    """Return named leave recommendations and retain interval consumption."""
    global leave_consumption_candidates
    schedule_plan = _approved_profile_rows(schedule_plan_frame, profile)
    patterns = [
        {**row, "ApprovedFlag": row.get("Approved")}
        for row in _profile_rows(pattern_frame, profile)
    ]
    roster_rows = _roster_with_occurrences(
        _approved_profile_rows(roster_frame, profile), schedule_plan, patterns
    )
    approved_swaps = [
        row for row in _approved_profile_rows(swap_decision_frame, profile)
        if str(row.get("RecommendationStatus") or "").strip().upper() == "APPROVE"
    ]
    swap_versions = {
        str(row.get("SwapDecisionVersionKey") or "").strip()
        for row in approved_swaps
        if str(row.get("SwapDecisionVersionKey") or "").strip()
    }
    if len(swap_versions) > 1:
        raise ValueError("Leave evaluation requires at most one approved swap-decision version")
    by_assignment = {str(row.get("AssignmentKey") or "").strip(): row for row in roster_rows}
    touched: set[str] = set()
    for swap in sorted(approved_swaps, key=lambda row: str(row.get("SwapRequestKey") or "")):
        key_a = str(swap.get("AssignmentKeyA") or "").strip()
        key_b = str(swap.get("AssignmentKeyB") or "").strip()
        if key_a in touched or key_b in touched:
            raise ValueError("One assignment cannot be affected by multiple approved swaps")
        if key_a not in by_assignment or key_b not in by_assignment:
            raise ValueError("Approved swap assignment is missing from the approved roster")
        row_a, row_b = by_assignment[key_a], by_assignment[key_b]
        if row_a["AgentKey"] != swap.get("AgentKeyA") or row_b["AgentKey"] != swap.get("AgentKeyB"):
            raise ValueError("Approved swap ownership does not match the approved roster")
        row_a["AgentKey"], row_b["AgentKey"] = row_b["AgentKey"], row_a["AgentKey"]
        touched.update({key_a, key_b})
    roster_segments = _roster_flat_segments(
        [{**row, "RosterCandidateKey": row.get("AssignmentKey")} for row in roster_rows]
    )
    decisions, consumption = evaluate_leave_requests(
        roster_rows,
        roster_segments,
        _approved_profile_rows(leave_plan_frame, profile),
        _profile_rows(request_frame, profile),
        _profile_rows(leave_type_policy_frame, profile),
        _profile_rows(entitlement_frame, profile),
        _profile_rows(prior_decision_frame, profile),
        swap_decision_version=next(iter(swap_versions), ""),
    )
    leave_consumption_candidates = _plain_rows(
        [{**row, "Profile": profile} for row in consumption]
    )
    return _plain_rows([{**row, "Profile": profile} for row in decisions])


def _roster_with_occurrences(
    roster_rows: list[dict[str, object]],
    schedule_plan_rows: list[dict[str, object]],
    pattern_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    occurrences = {
        row["OccurrenceKey"]: row
        for row in expand_pattern_occurrences(schedule_plan_rows, pattern_rows)
    }
    output: list[dict[str, object]] = []
    for row in roster_rows:
        key = str(row.get("OccurrenceKey") or "").strip()
        if key not in occurrences:
            raise ValueError(f"Approved roster occurrence cannot be reconstructed: {key}")
        output.append({**row, "Occurrence": occurrences[key], "Segments": occurrences[key]["Segments"]})
    return output


def run_swaps_excel(
    roster_frame: object,
    schedule_plan_frame: object,
    pattern_frame: object,
    request_frame: object,
    people_frame: object,
    roster_policy_frame: object,
    contract_frame: object,
    eligibility_frame: object,
    agent_skill_frame: object,
    skill_requirement_frame: object,
    availability_frame: object,
    *,
    profile: str,
) -> list[dict[str, object]]:
    """Return bilateral swap recommendations and companion proposal outputs."""
    global swap_proposal_candidates, swap_diagnostic_candidates
    schedule_plan = _approved_profile_rows(schedule_plan_frame, profile)
    patterns = [
        {**row, "ApprovedFlag": row.get("Approved")}
        for row in _profile_rows(pattern_frame, profile)
    ]
    roster_rows = _roster_with_occurrences(
        _approved_profile_rows(roster_frame, profile), schedule_plan, patterns
    )
    decisions, proposals, diagnostics = evaluate_swap_requests(
        roster_rows,
        _profile_rows(request_frame, profile),
        _profile_rows(people_frame, profile),
        _profile_rows(roster_policy_frame, profile),
        _profile_rows(contract_frame, profile),
        _profile_rows(eligibility_frame, profile),
        _profile_rows(agent_skill_frame, profile),
        _profile_rows(skill_requirement_frame, profile),
        _profile_rows(availability_frame, profile),
    )
    swap_proposal_candidates = _plain_rows(
        [{**row, "Profile": profile} for row in _public_roster_rows(proposals)]
    )
    swap_diagnostic_candidates = _plain_rows(
        [{**row, "Profile": profile} for row in diagnostics]
    )
    return _plain_rows([{**row, "Profile": profile} for row in decisions])
