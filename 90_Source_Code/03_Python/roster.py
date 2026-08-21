"""Deterministic, governed named-roster assignment for WFM OS.

The core consumes an approved anonymous BASE schedule and returns a candidate
named roster.  It is deliberately dependency-free for Python in Excel.  The
bounded greedy/repair method is deterministic, auditable, and not an optimizer.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
import re
from typing import Iterable, Mapping


RosterRecord = Mapping[str, object]
ROSTER_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ROSTER_WEEKDAYS = (
    "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"
)
ROSTER_METHOD = "CONSTRAINED_GREEDY_REPAIR_V1"
ROSTER_INTERVAL = timedelta(minutes=30)


def _roster_text(row: RosterRecord, field: str) -> str:
    if field not in row:
        raise ValueError(f"Missing field: {field}")
    value = str(row[field]).strip()
    if not value:
        raise ValueError(f"{field} cannot be blank")
    return value


def _roster_date(value: object, field: str) -> date:
    if isinstance(value, datetime):
        raise ValueError(f"{field} must be a date, not a datetime")
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not ROSTER_DATE.fullmatch(value.strip()):
        raise ValueError(f"{field} must use strict YYYY-MM-DD format")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid date") from exc


def _roster_datetime(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO datetime") from exc
    else:
        raise ValueError(f"{field} must be an ISO datetime")
    if result.tzinfo is not None:
        raise ValueError(f"{field} must be a timezone-naive local datetime")
    if result.minute not in {0, 30} or result.second or result.microsecond:
        raise ValueError(f"{field} must align to an exact 30-minute boundary")
    return result


def _roster_decimal(
    value: object, field: str, *, minimum: Decimal | None = None
) -> Decimal:
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


def _roster_integer(value: object, field: str, *, minimum: int = 0) -> int:
    number = _roster_decimal(value, field)
    if number != number.to_integral_value() or number < minimum:
        raise ValueError(f"{field} must be an integer at least {minimum}")
    return int(number)


def _roster_true(value: object, field: str = "Approved") -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().upper() in {"TRUE", "FALSE"}:
        return value.strip().upper() == "TRUE"
    raise ValueError(f"{field} must be TRUE or FALSE")


def _roster_optional_true(row: RosterRecord, field: str, default: bool = True) -> bool:
    value = row.get(field)
    if value is None or str(value).strip() == "":
        return default
    return _roster_true(value, field)


def _roster_active(row: RosterRecord, on_date: date) -> bool:
    valid_from = _roster_date(row.get("ValidFrom"), "ValidFrom")
    raw_valid_to = row.get("ValidTo")
    valid_to = (
        _roster_date(raw_valid_to, "ValidTo")
        if raw_valid_to is not None and str(raw_valid_to).strip()
        else date.max
    )
    if valid_to < valid_from:
        raise ValueError("ValidTo cannot precede ValidFrom")
    return valid_from <= on_date <= valid_to


def _roster_period_start(work_date: date, period_start_day: object) -> date:
    raw = str(period_start_day).strip().upper()
    if raw in ROSTER_WEEKDAYS:
        weekday = ROSTER_WEEKDAYS.index(raw)
    else:
        weekday = _roster_integer(period_start_day, "PeriodStartDay", minimum=1) - 1
        if weekday > 6:
            raise ValueError("PeriodStartDay must be MONDAY..SUNDAY or 1..7")
    return work_date - timedelta(days=(work_date.weekday() - weekday) % 7)


def _roster_paid_intervals(occurrence: RosterRecord) -> list[datetime]:
    intervals: list[datetime] = []
    for segment in occurrence.get("Segments", []):
        if not bool(segment.get("PaidFlag")):
            continue
        start = _roster_datetime(segment.get("SegmentStart"), "SegmentStart")
        end = _roster_datetime(segment.get("SegmentEnd"), "SegmentEnd")
        while start < end:
            intervals.append(start)
            start += ROSTER_INTERVAL
    return sorted(set(intervals))


def _roster_prepare_people(rows: Iterable[RosterRecord]) -> dict[str, list[dict[str, object]]]:
    people: dict[str, list[dict[str, object]]] = defaultdict(list)
    for source in rows:
        row = dict(source)
        agent = _roster_text(row, "AgentKey")
        if any(str(key).lower() in {"displayname", "employeebusinessid"} for key in row):
            row.pop("DisplayName", None)
            row.pop("EmployeeBusinessID", None)
        people[agent].append(row)
    if not people:
        raise ValueError("Agent rows cannot be empty")
    return people


def _roster_effective(
    rows: Iterable[RosterRecord], on_date: date, *, approved: bool = True
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for source in rows:
        row = dict(source)
        if approved and not _roster_optional_true(row, "Approved"):
            continue
        if _roster_active(row, on_date):
            output.append(row)
    return output


def _roster_one(
    rows: Iterable[RosterRecord], on_date: date, label: str, *, approved: bool = True
) -> dict[str, object]:
    matches = _roster_effective(rows, on_date, approved=approved)
    if len(matches) != 1:
        raise ValueError(f"Exactly one effective {label} is required on {on_date}; found {len(matches)}")
    return matches[0]


def _roster_policy_for(
    policies: list[dict[str, object]], activity: str, on_date: date
) -> dict[str, object]:
    matches = [
        row for row in _roster_effective(policies, on_date)
        if _roster_text(row, "ActivityKey") in {activity, "ALL"}
    ]
    exact = [row for row in matches if _roster_text(row, "ActivityKey") == activity]
    selected = exact if exact else [row for row in matches if _roster_text(row, "ActivityKey") == "ALL"]
    if len(selected) != 1:
        raise ValueError(f"Exactly one effective roster policy is required for {activity}/{on_date}")
    policy = selected[0]
    if _roster_text(policy, "AssignmentMethod").upper() != ROSTER_METHOD:
        raise ValueError(f"Only {ROSTER_METHOD} is implemented")
    if _roster_text(policy, "AvailabilityMode").upper() != "EXPLICIT_WINDOWS":
        raise ValueError("Only EXPLICIT_WINDOWS availability is implemented")
    if _roster_text(policy, "FairnessMethod").upper() != "TARGET_LOAD_BURDEN_V1":
        raise ValueError("Only TARGET_LOAD_BURDEN_V1 fairness is implemented")
    if _roster_text(policy, "WorkdayAttributionMode").upper() != "PATTERN_BUSINESS_DATE":
        raise ValueError("Only PATTERN_BUSINESS_DATE workday attribution is implemented")
    if _roster_text(policy, "MinimumHoursMode").upper() not in {"DIAGNOSTIC", "HARD"}:
        raise ValueError("MinimumHoursMode must be DIAGNOSTIC or HARD")
    return policy


def _roster_contract_for(
    contracts: list[dict[str, object]], agent: str, policy: RosterRecord, on_date: date
) -> dict[str, object] | None:
    policy_key = _roster_text(policy, "RosterPolicyKey")
    matches = [
        row for row in _roster_effective(contracts, on_date)
        if _roster_text(row, "AgentKey") == agent
        and _roster_text(row, "RosterPolicyKey") == policy_key
    ]
    if len(matches) > 1:
        raise ValueError(f"Overlapping agent contracts for {agent}/{policy_key}/{on_date}")
    if not matches:
        return None
    contract = matches[0]
    if _roster_text(contract, "PeriodType").upper() != "WEEK":
        raise ValueError("Only WEEK agent-contract periods are implemented")
    return contract


def _roster_is_active_person(
    people: dict[str, list[dict[str, object]]], agent: str, on_date: date
) -> bool:
    matches = [row for row in people.get(agent, []) if _roster_active(row, on_date)]
    if len(matches) > 1:
        raise ValueError(f"Overlapping active-person rows for {agent}/{on_date}")
    if not matches:
        return False
    if "Enabled" in matches[0] and not _roster_optional_true(matches[0], "Enabled"):
        return False
    return str(matches[0].get("EmploymentStatus", "")).strip().upper() == "ACTIVE"


def _roster_has_eligibility(
    rows: list[dict[str, object]], agent: str, activity: str, on_date: date
) -> bool:
    matches = [
        row for row in _roster_effective(rows, on_date)
        if _roster_text(row, "AgentKey") == agent
        and _roster_text(row, "ActivityKey") == activity
    ]
    if len(matches) > 1:
        raise ValueError(f"Overlapping activity eligibility for {agent}/{activity}/{on_date}")
    return len(matches) == 1


def _roster_has_skills(
    requirements: list[dict[str, object]],
    skills: list[dict[str, object]],
    agent: str,
    occurrence: RosterRecord,
) -> bool:
    on_date = occurrence["BusinessDate"]
    activity = str(occurrence["ActivityKey"])
    pattern = str(occurrence["PatternKey"])
    candidates = [
        row for row in _roster_effective(requirements, on_date)
        if _roster_text(row, "ActivityKey") == activity
        and _roster_text(row, "PatternKey") in {pattern, "ALL"}
    ]
    exact = [row for row in candidates if _roster_text(row, "PatternKey") == pattern]
    selected = exact if exact else [row for row in candidates if _roster_text(row, "PatternKey") == "ALL"]
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in selected:
        groups[_roster_text(row, "SkillGroupKey")].append(row)
    effective_skills = [
        row for row in _roster_effective(skills, on_date)
        if _roster_text(row, "AgentKey") == agent
    ]
    skill_levels: dict[str, Decimal] = {}
    for row in effective_skills:
        key = _roster_text(row, "SkillKey")
        level = _roster_decimal(row.get("ProficiencyLevel"), "ProficiencyLevel", minimum=Decimal(0))
        skill_levels[key] = max(level, skill_levels.get(key, Decimal(0)))
    return all(
        any(
            skill_levels.get(_roster_text(requirement, "SkillKey"), Decimal(-1))
            >= _roster_decimal(requirement.get("MinimumLevel"), "MinimumLevel", minimum=Decimal(0))
            for requirement in group_rows
        )
        for group_rows in groups.values()
    )


def _roster_is_available(
    windows: list[dict[str, object]], agent: str, occurrence: RosterRecord
) -> bool:
    paid = _roster_paid_intervals(occurrence)
    if not paid:
        return False
    relevant: list[tuple[datetime, datetime, str]] = []
    for row in windows:
        if not _roster_optional_true(row, "Approved") or _roster_text(row, "AgentKey") != agent:
            continue
        start = _roster_datetime(row.get("WindowStart"), "WindowStart")
        end = _roster_datetime(row.get("WindowEnd"), "WindowEnd")
        if end <= start:
            raise ValueError("Availability WindowEnd must follow WindowStart")
        window_type = _roster_text(row, "AvailabilityType").upper()
        if window_type not in {"AVAILABLE", "UNAVAILABLE"}:
            raise ValueError("AvailabilityType must be AVAILABLE or UNAVAILABLE")
        relevant.append((start, end, window_type))
    for interval_start in paid:
        interval_end = interval_start + ROSTER_INTERVAL
        if any(start < interval_end and end > interval_start and kind == "UNAVAILABLE" for start, end, kind in relevant):
            return False
        if not any(start <= interval_start and end >= interval_end and kind == "AVAILABLE" for start, end, kind in relevant):
            return False
    return True


def _roster_preference(
    rows: list[dict[str, object]], agent: str, occurrence: RosterRecord
) -> tuple[Decimal, Decimal]:
    on_date = occurrence["BusinessDate"]
    weekday = ROSTER_WEEKDAYS[on_date.weekday()]
    pattern = str(occurrence["PatternKey"])
    matches = [
        row for row in _roster_effective(rows, on_date)
        if _roster_text(row, "AgentKey") == agent
        and _roster_text(row, "PatternKey") in {pattern, "ALL"}
        and _roster_text(row, "DayType").upper() in {weekday, "ALL"}
    ]
    ranked = sorted(
        matches,
        key=lambda row: (
            _roster_text(row, "PatternKey") != pattern,
            _roster_text(row, "DayType").upper() != weekday,
            _roster_text(row, "PreferenceKey"),
        ),
    )
    if not ranked:
        return Decimal(0), Decimal(0)
    best_rank = (
        _roster_text(ranked[0], "PatternKey") != pattern,
        _roster_text(ranked[0], "DayType").upper() != weekday,
    )
    best = [
        row for row in ranked
        if (
            _roster_text(row, "PatternKey") != pattern,
            _roster_text(row, "DayType").upper() != weekday,
        ) == best_rank
    ]
    if len(best) != 1:
        raise ValueError(f"Ambiguous preference for {agent}/{pattern}/{on_date}")
    return (
        _roster_decimal(best[0].get("PreferenceCost"), "PreferenceCost", minimum=Decimal(0)),
        _roster_decimal(best[0].get("UnfavorableWeight"), "UnfavorableWeight", minimum=Decimal(0)),
    )


def _roster_daily_paid(occurrence: RosterRecord) -> dict[date, Decimal]:
    daily: dict[date, Decimal] = defaultdict(Decimal)
    for interval_start in _roster_paid_intervals(occurrence):
        daily[interval_start.date()] += Decimal("0.5")
    return daily


def _roster_violation(
    agent: str,
    occurrence: RosterRecord,
    contract: RosterRecord,
    assigned: list[dict[str, object]],
) -> str | None:
    start = occurrence["PaidStart"]
    end = occurrence["PaidEnd"]
    span_hours = Decimal(str((end - start).total_seconds())) / Decimal(3600)
    paid_hours = _roster_decimal(occurrence.get("PaidHours"), "PaidHours", minimum=Decimal(0))
    if paid_hours > _roster_decimal(contract.get("MaxPaidHoursPerShift"), "MaxPaidHoursPerShift", minimum=Decimal(0)):
        return "MAX_SHIFT_PAID_HOURS"
    if span_hours > _roster_decimal(contract.get("MaxShiftSpanHours"), "MaxShiftSpanHours", minimum=Decimal(0)):
        return "MAX_SHIFT_SPAN_HOURS"

    agent_rows = [row for row in assigned if row["AgentKey"] == agent]
    minimum_rest = _roster_decimal(contract.get("MinRestHours"), "MinRestHours", minimum=Decimal(0))
    for row in agent_rows:
        prior = row["Occurrence"]
        if start < prior["PaidEnd"] and end > prior["PaidStart"]:
            return "ASSIGNMENT_OVERLAP"
        rest = None
        if end <= prior["PaidStart"]:
            rest = Decimal(str((prior["PaidStart"] - end).total_seconds())) / Decimal(3600)
        elif start >= prior["PaidEnd"]:
            rest = Decimal(str((start - prior["PaidEnd"]).total_seconds())) / Decimal(3600)
        if rest is not None and rest < minimum_rest:
            return "MINIMUM_REST"

    daily_hours: dict[date, Decimal] = defaultdict(Decimal)
    weekly_hours: dict[date, Decimal] = defaultdict(Decimal)
    business_dates: set[date] = set()
    assignments_per_day: dict[date, int] = defaultdict(int)
    for row in [*agent_rows, {"Occurrence": occurrence}]:
        current = row["Occurrence"]
        business_date = current["BusinessDate"]
        business_dates.add(business_date)
        assignments_per_day[business_date] += 1
        for paid_date, hours in _roster_daily_paid(current).items():
            daily_hours[paid_date] += hours
            weekly_hours[_roster_period_start(paid_date, contract.get("PeriodStartDay"))] += hours
    daily_limit = _roster_decimal(contract.get("MaxPaidHoursPerDay"), "MaxPaidHoursPerDay", minimum=Decimal(0))
    if any(hours > daily_limit for hours in daily_hours.values()):
        return "MAX_DAILY_PAID_HOURS"
    weekly_limit = _roster_decimal(contract.get("MaxPaidHours"), "MaxPaidHours", minimum=Decimal(0))
    if any(hours > weekly_limit for hours in weekly_hours.values()):
        return "MAX_WEEKLY_PAID_HOURS"
    max_assignments = _roster_integer(contract.get("MaxAssignmentsPerWorkday"), "MaxAssignmentsPerWorkday", minimum=1)
    if any(count > max_assignments for count in assignments_per_day.values()):
        return "MAX_ASSIGNMENTS_PER_WORKDAY"
    consecutive_limit = _roster_integer(contract.get("MaxConsecutiveWorkdays"), "MaxConsecutiveWorkdays", minimum=1)
    ordered = sorted(business_dates)
    run = 1
    longest = 1 if ordered else 0
    for prior, current in zip(ordered, ordered[1:]):
        run = run + 1 if current == prior + timedelta(days=1) else 1
        longest = max(longest, run)
    if longest > consecutive_limit:
        return "MAX_CONSECUTIVE_WORKDAYS"
    return None


def _roster_static_reason(
    agent: str,
    occurrence: RosterRecord,
    people: dict[str, list[dict[str, object]]],
    policy: RosterRecord,
    contracts: list[dict[str, object]],
    eligibility: list[dict[str, object]],
    agent_skills: list[dict[str, object]],
    requirements: list[dict[str, object]],
    availability: list[dict[str, object]],
) -> tuple[str | None, dict[str, object] | None]:
    business_date = occurrence["BusinessDate"]
    if not _roster_is_active_person(people, agent, business_date):
        return "INACTIVE_AGENT", None
    contract = _roster_contract_for(contracts, agent, policy, business_date)
    if contract is None:
        return "NO_EFFECTIVE_CONTRACT", None
    if not _roster_has_eligibility(eligibility, agent, str(occurrence["ActivityKey"]), business_date):
        return "NOT_ACTIVITY_ELIGIBLE", contract
    if not _roster_has_skills(requirements, agent_skills, agent, occurrence):
        return "SKILL_REQUIREMENT_NOT_MET", contract
    if not _roster_is_available(availability, agent, occurrence):
        return "OUTSIDE_APPROVED_AVAILABILITY", contract
    return None, contract


def _roster_score(
    agent: str,
    occurrence: RosterRecord,
    contract: RosterRecord,
    assigned: list[dict[str, object]],
    preferences: list[dict[str, object]],
) -> tuple[Decimal, Decimal, Decimal, int, str]:
    target = _roster_decimal(contract.get("TargetPaidHours"), "TargetPaidHours", minimum=Decimal(0))
    period_hours: dict[date, Decimal] = defaultdict(Decimal)
    for row in assigned:
        if row["AgentKey"] != agent:
            continue
        for paid_date, hours in _roster_daily_paid(row["Occurrence"]).items():
            period_hours[_roster_period_start(paid_date, contract.get("PeriodStartDay"))] += hours
    affected_periods: set[date] = set()
    for paid_date, hours in _roster_daily_paid(occurrence).items():
        period = _roster_period_start(paid_date, contract.get("PeriodStartDay"))
        period_hours[period] += hours
        affected_periods.add(period)
    projected = max((period_hours[period] for period in affected_periods), default=Decimal(0))
    load = projected / target if target else projected
    preference, unfavorable = _roster_preference(preferences, agent, occurrence)
    burden = sum(
        (_roster_preference(preferences, agent, row["Occurrence"])[1] for row in assigned if row["AgentKey"] == agent),
        Decimal(0),
    ) + unfavorable
    count = sum(1 for row in assigned if row["AgentKey"] == agent)
    return load, burden, preference, count, agent


def _roster_candidate_agents(
    occurrence: RosterRecord,
    agents: list[str],
    people: dict[str, list[dict[str, object]]],
    policy: RosterRecord,
    contracts: list[dict[str, object]],
    eligibility: list[dict[str, object]],
    agent_skills: list[dict[str, object]],
    requirements: list[dict[str, object]],
    availability: list[dict[str, object]],
    assigned: list[dict[str, object]],
) -> list[tuple[str, dict[str, object]]]:
    candidates: list[tuple[str, dict[str, object]]] = []
    for agent in agents:
        reason, contract = _roster_static_reason(
            agent, occurrence, people, policy, contracts, eligibility,
            agent_skills, requirements, availability,
        )
        if reason is None and contract is not None and _roster_violation(agent, occurrence, contract, assigned) is None:
            candidates.append((agent, contract))
    return candidates


def _roster_assignment_row(
    occurrence: RosterRecord,
    agent: str,
    contract: RosterRecord,
    score: tuple[Decimal, Decimal, Decimal, int, str],
    schedule_version: str,
) -> dict[str, object]:
    key = str(occurrence["OccurrenceKey"])
    return {
        "AssignmentKey": key,
        "RosterCandidateKey": key,
        "RosterVersionKey": "",
        "SchedulePlanVersionKey": schedule_version,
        "ScenarioKey": occurrence["ScenarioKey"],
        "ApprovalStatus": "PENDING",
        "OccurrenceKey": occurrence["OccurrenceKey"],
        "BusinessDate": occurrence["BusinessDate"].isoformat(),
        "ActivityKey": occurrence["ActivityKey"],
        "PatternVersionKey": occurrence["PatternVersionKey"],
        "PatternKey": occurrence["PatternKey"],
        "OccurrenceOrdinal": occurrence["OccurrenceOrdinal"],
        "AgentKey": agent,
        "ContractKey": _roster_text(contract, "ContractKey"),
        "PaidStart": occurrence["PaidStart"].isoformat(),
        "PaidEnd": occurrence["PaidEnd"].isoformat(),
        "PaidHours": occurrence["PaidHours"],
        "ProductiveHours": occurrence["ProductiveHours"],
        "AssignmentMethod": ROSTER_METHOD,
        "AssignmentStatus": "ASSIGNED",
        "FairnessScore": score[0],
        "UnfavorableBurden": score[1],
        "PreferenceCost": score[2],
        "Segments": occurrence["Segments"],
        "Occurrence": occurrence,
    }


def _roster_flat_segments(assignments: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for assignment in assignments:
        occurrence = assignment["Occurrence"]
        for segment in occurrence["Segments"]:
            start = segment["SegmentStart"]
            end = segment["SegmentEnd"]
            while start < end:
                output.append(
                    {
                        "RosterCandidateKey": assignment["RosterCandidateKey"],
                        "OccurrenceKey": occurrence["OccurrenceKey"],
                        "SegmentKey": f"{occurrence['OccurrenceKey']}|{segment['SegmentKey']}|{start.isoformat()}",
                        "BusinessDate": occurrence["BusinessDate"].isoformat(),
                        "IntervalStart": start.isoformat(),
                        "IntervalKey": f"I{start.hour * 2 + start.minute // 30:02d}",
                        "AgentKey": assignment["AgentKey"],
                        "ActivityKey": occurrence["ActivityKey"],
                        "ScheduleTypeKey": segment["ScheduleTypeKey"],
                        "PaidFlag": segment["PaidFlag"],
                        "ProductiveFlag": segment["ProductiveFlag"],
                        "ScheduledSeconds": 1800,
                        "PublicationStatus": "CANDIDATE",
                    }
                )
                start += ROSTER_INTERVAL
    return sorted(output, key=lambda row: (row["IntervalStart"], row["AgentKey"], row["SegmentKey"]))


def _roster_period_summaries(
    assignments: list[dict[str, object]], contracts: list[dict[str, object]]
) -> list[dict[str, object]]:
    totals: dict[tuple[str, str, date], Decimal] = defaultdict(Decimal)
    contract_index = {_roster_text(row, "ContractKey"): row for row in contracts if _roster_optional_true(row, "Approved")}
    for assignment in assignments:
        contract = contract_index[assignment["ContractKey"]]
        for paid_date, hours in _roster_daily_paid(assignment["Occurrence"]).items():
            period = _roster_period_start(paid_date, contract.get("PeriodStartDay"))
            totals[(assignment["AgentKey"], assignment["ContractKey"], period)] += hours
    output: list[dict[str, object]] = []
    for (agent, contract_key, period), hours in sorted(totals.items()):
        contract = contract_index[contract_key]
        minimum = _roster_decimal(contract.get("MinPaidHours"), "MinPaidHours", minimum=Decimal(0))
        target = _roster_decimal(contract.get("TargetPaidHours"), "TargetPaidHours", minimum=Decimal(0))
        maximum = _roster_decimal(contract.get("MaxPaidHours"), "MaxPaidHours", minimum=Decimal(0))
        status = "BELOW_MINIMUM" if hours < minimum else "ABOVE_TARGET" if hours > target else "WITHIN_TARGET"
        output.append(
            {
                "AgentKey": agent,
                "ContractKey": contract_key,
                "RosterPolicyKey": _roster_text(contract, "RosterPolicyKey"),
                "PeriodStart": period.isoformat(),
                "PeriodEnd": (period + timedelta(days=6)).isoformat(),
                "AssignedPaidHours": hours,
                "MinPaidHours": minimum,
                "TargetPaidHours": target,
                "MaxPaidHours": maximum,
                "VarianceToTargetHours": hours - target,
                "PeriodStatus": status,
            }
        )
    return output


def assign_named_roster(
    schedule_plan_rows: Iterable[RosterRecord],
    pattern_rows: Iterable[RosterRecord],
    horizon_coverage_rows: Iterable[RosterRecord],
    agent_rows: Iterable[RosterRecord],
    roster_policy_rows: Iterable[RosterRecord],
    contract_rows: Iterable[RosterRecord],
    activity_eligibility_rows: Iterable[RosterRecord],
    agent_skill_rows: Iterable[RosterRecord],
    skill_requirement_rows: Iterable[RosterRecord],
    availability_rows: Iterable[RosterRecord],
    preference_rows: Iterable[RosterRecord] = (),
    locked_assignment_rows: Iterable[RosterRecord] = (),
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """Assign unit schedule occurrences to eligible agents deterministically."""
    plan = [dict(row) for row in schedule_plan_rows]
    if not plan:
        raise ValueError("Approved anonymous schedule cannot be empty")
    scenarios = {_roster_text(row, "ScenarioKey").upper() for row in plan}
    if scenarios != {"BASE"}:
        raise ValueError("Named roster generation requires only the approved BASE scenario")
    schedule_versions = {_roster_text(row, "SchedulePlanVersionKey") for row in plan}
    if len(schedule_versions) != 1:
        raise ValueError("Named roster generation requires exactly one schedule plan version")
    schedule_version = next(iter(schedule_versions))

    coverage_diagnostics: list[dict[str, object]] = []
    coverage = [dict(row) for row in horizon_coverage_rows]
    for row in coverage:
        status = str(row.get("CoverageStatus", "")).strip().upper()
        uncovered = _roster_decimal(row.get("UncoveredFTE", 0), "UncoveredFTE", minimum=Decimal(0))
        if status in {"UNCOVERED", "BLOCKING"} or uncovered > 0:
            coverage_diagnostics.append(
                {
                    "DiagnosticKey": f"COVERAGE|{row.get('IntervalStart')}|{row.get('ActivityKey')}",
                    "Severity": "BLOCKING",
                    "Entity": "SCHEDULE_COVERAGE",
                    "EntityKey": str(row.get("ScheduleCandidateKey") or row.get("IntervalStart") or ""),
                    "ReasonCode": "APPROVED_SCHEDULE_UNDERCOVERED",
                    "Detail": "Named assignment cannot cure anonymous schedule undercoverage.",
                }
            )

    people = _roster_prepare_people(agent_rows)
    agents = sorted(people)
    policies = [dict(row) for row in roster_policy_rows]
    contracts = [dict(row) for row in contract_rows]
    eligibility = [dict(row) for row in activity_eligibility_rows]
    skills = [dict(row) for row in agent_skill_rows]
    requirements = [dict(row) for row in skill_requirement_rows]
    availability = [dict(row) for row in availability_rows]
    preferences = [dict(row) for row in preference_rows]
    occurrences = expand_pattern_occurrences(plan, pattern_rows)

    static_counts: dict[str, int] = {}
    for occurrence in occurrences:
        policy = _roster_policy_for(policies, str(occurrence["ActivityKey"]), occurrence["BusinessDate"])
        static_counts[str(occurrence["OccurrenceKey"])] = sum(
            1
            for agent in agents
            if _roster_static_reason(
                agent, occurrence, people, policy, contracts, eligibility,
                skills, requirements, availability,
            )[0] is None
        )
    locked = {
        str(row.get("OccurrenceKey") or ""): str(row.get("AgentKey") or "")
        for row in locked_assignment_rows
    }
    occurrences.sort(
        key=lambda row: (
            0 if str(row["OccurrenceKey"]) in locked else 1,
            static_counts[str(row["OccurrenceKey"])],
            row["PaidStart"],
            -int((row["PaidEnd"] - row["PaidStart"]).total_seconds()),
            row["OccurrenceKey"],
        )
    )

    assigned_state: list[dict[str, object]] = []
    assignments: list[dict[str, object]] = []
    diagnostics = list(coverage_diagnostics)
    for occurrence in occurrences:
        policy = _roster_policy_for(policies, str(occurrence["ActivityKey"]), occurrence["BusinessDate"])
        candidates = _roster_candidate_agents(
            occurrence, agents, people, policy, contracts, eligibility,
            skills, requirements, availability, assigned_state,
        )
        locked_agent = locked.get(str(occurrence["OccurrenceKey"]))
        if locked_agent:
            candidates = [candidate for candidate in candidates if candidate[0] == locked_agent]
        scored = sorted(
            (
                _roster_score(agent, occurrence, contract, assigned_state, preferences),
                agent,
                contract,
            )
            for agent, contract in candidates
        )
        if scored:
            score, agent, contract = scored[0]
            assignment = _roster_assignment_row(occurrence, agent, contract, score, schedule_version)
            assignments.append(assignment)
            assigned_state.append({"AgentKey": agent, "Occurrence": occurrence, "Assignment": assignment})
            diagnostics.append(
                {
                    "DiagnosticKey": f"ASSIGNMENT|{occurrence['OccurrenceKey']}",
                    "Severity": "INFO",
                    "Entity": "ROSTER_OCCURRENCE",
                    "EntityKey": occurrence["OccurrenceKey"],
                    "ReasonCode": "ASSIGNED",
                    "Detail": f"Assigned from {len(scored)} feasible candidates.",
                }
            )
            continue

        repaired = False
        repair_depth = _roster_integer(policy.get("RepairDepth"), "RepairDepth", minimum=0)
        max_pairs = _roster_integer(policy.get("MaxCandidatePairs"), "MaxCandidatePairs", minimum=0)
        if repair_depth >= 1 and max_pairs > 0:
            pairs_checked = 0
            for displaced in sorted(assigned_state, key=lambda row: row["Occurrence"]["OccurrenceKey"]):
                if pairs_checked >= max_pairs:
                    break
                displaced_agent = displaced["AgentKey"]
                reason, contract = _roster_static_reason(
                    displaced_agent, occurrence, people, policy, contracts, eligibility,
                    skills, requirements, availability,
                )
                without_displaced = [row for row in assigned_state if row is not displaced]
                if reason is not None or contract is None or _roster_violation(displaced_agent, occurrence, contract, without_displaced):
                    continue
                old_occurrence = displaced["Occurrence"]
                old_policy = _roster_policy_for(policies, str(old_occurrence["ActivityKey"]), old_occurrence["BusinessDate"])
                replacements = _roster_candidate_agents(
                    old_occurrence, [agent for agent in agents if agent != displaced_agent], people,
                    old_policy, contracts, eligibility, skills, requirements, availability,
                    without_displaced,
                )
                for replacement_agent, replacement_contract in replacements:
                    pairs_checked += 1
                    if pairs_checked > max_pairs:
                        break
                    provisional = [*without_displaced, {"AgentKey": displaced_agent, "Occurrence": occurrence}]
                    if _roster_violation(replacement_agent, old_occurrence, replacement_contract, provisional):
                        continue
                    assignments.remove(displaced["Assignment"])
                    score_new = _roster_score(displaced_agent, occurrence, contract, without_displaced, preferences)
                    score_old = _roster_score(replacement_agent, old_occurrence, replacement_contract, provisional, preferences)
                    new_assignment = _roster_assignment_row(occurrence, displaced_agent, contract, score_new, schedule_version)
                    replacement = _roster_assignment_row(old_occurrence, replacement_agent, replacement_contract, score_old, schedule_version)
                    assignments.extend([new_assignment, replacement])
                    assigned_state = [
                        *without_displaced,
                        {"AgentKey": displaced_agent, "Occurrence": occurrence, "Assignment": new_assignment},
                        {"AgentKey": replacement_agent, "Occurrence": old_occurrence, "Assignment": replacement},
                    ]
                    diagnostics.append(
                        {
                            "DiagnosticKey": f"REPAIR|{occurrence['OccurrenceKey']}",
                            "Severity": "INFO",
                            "Entity": "ROSTER_OCCURRENCE",
                            "EntityKey": occurrence["OccurrenceKey"],
                            "ReasonCode": "ASSIGNED_BY_ONE_STEP_REPAIR",
                            "Detail": f"Displaced {old_occurrence['OccurrenceKey']} after {pairs_checked} bounded pair checks.",
                        }
                    )
                    repaired = True
                    break
                if repaired:
                    break
        if not repaired:
            reasons: dict[str, int] = defaultdict(int)
            for agent in agents:
                reason, contract = _roster_static_reason(
                    agent, occurrence, people, policy, contracts, eligibility,
                    skills, requirements, availability,
                )
                if reason is None and contract is not None:
                    reason = _roster_violation(agent, occurrence, contract, assigned_state)
                reasons[reason or "UNKNOWN"] += 1
            detail = "; ".join(f"{key}={value}" for key, value in sorted(reasons.items()))
            diagnostics.append(
                {
                    "DiagnosticKey": f"UNASSIGNED|{occurrence['OccurrenceKey']}",
                    "Severity": "BLOCKING",
                    "Entity": "ROSTER_OCCURRENCE",
                    "EntityKey": occurrence["OccurrenceKey"],
                    "ReasonCode": "NO_FEASIBLE_AGENT",
                    "Detail": detail,
                }
            )

    assignments.sort(key=lambda row: (row["PaidStart"], row["AgentKey"], row["OccurrenceKey"]))
    period_summaries = _roster_period_summaries(assignments, contracts)
    for row in period_summaries:
        if row["PeriodStatus"] == "BELOW_MINIMUM":
            minimum_policy = _roster_one(
                [
                    policy for policy in policies
                    if _roster_text(policy, "RosterPolicyKey") == row["RosterPolicyKey"]
                ],
                _roster_date(row["PeriodStart"], "PeriodStart"),
                f"roster policy {row['RosterPolicyKey']}",
            )
            severity = (
                "BLOCKING"
                if _roster_text(minimum_policy, "MinimumHoursMode").upper() == "HARD"
                else "REVIEW"
            )
            diagnostics.append(
                {
                    "DiagnosticKey": f"MINIMUM|{row['AgentKey']}|{row['PeriodStart']}",
                    "Severity": severity,
                    "Entity": "AGENT_PERIOD",
                    "EntityKey": f"{row['AgentKey']}|{row['PeriodStart']}",
                    "ReasonCode": "BELOW_CONTRACT_MINIMUM",
                    "Detail": f"Assigned {row['AssignedPaidHours']} hours versus minimum {row['MinPaidHours']}.",
                }
            )
    return assignments, _roster_flat_segments(assignments), sorted(diagnostics, key=lambda row: row["DiagnosticKey"]), period_summaries


def validate_named_roster(
    assignment_rows: Iterable[RosterRecord],
    agent_rows: Iterable[RosterRecord],
    roster_policy_rows: Iterable[RosterRecord],
    contract_rows: Iterable[RosterRecord],
    activity_eligibility_rows: Iterable[RosterRecord],
    agent_skill_rows: Iterable[RosterRecord],
    skill_requirement_rows: Iterable[RosterRecord],
    availability_rows: Iterable[RosterRecord],
) -> list[dict[str, object]]:
    """Revalidate a complete candidate/approved roster after a controlled change."""
    assignments = [dict(row) for row in assignment_rows]
    people = _roster_prepare_people(agent_rows)
    policies = [dict(row) for row in roster_policy_rows]
    contracts = [dict(row) for row in contract_rows]
    eligibility = [dict(row) for row in activity_eligibility_rows]
    skills = [dict(row) for row in agent_skill_rows]
    requirements = [dict(row) for row in skill_requirement_rows]
    availability = [dict(row) for row in availability_rows]
    state: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    for row in sorted(assignments, key=lambda item: (str(item.get("PaidStart")), str(item.get("OccurrenceKey")))):
        occurrence = dict(row.get("Occurrence") or {})
        if not occurrence:
            raise ValueError("Roster validation requires the governed nested Occurrence payload")
        agent = _roster_text(row, "AgentKey")
        policy = _roster_policy_for(policies, str(occurrence["ActivityKey"]), occurrence["BusinessDate"])
        reason, contract = _roster_static_reason(
            agent, occurrence, people, policy, contracts, eligibility,
            skills, requirements, availability,
        )
        if reason is None and contract is not None:
            reason = _roster_violation(agent, occurrence, contract, state)
        if reason is not None:
            diagnostics.append(
                {
                    "DiagnosticKey": f"VALIDATE|{row.get('AssignmentKey')}|{reason}",
                    "Severity": "BLOCKING",
                    "Entity": "ROSTER_ASSIGNMENT",
                    "EntityKey": str(row.get("AssignmentKey") or row.get("OccurrenceKey") or ""),
                    "ReasonCode": reason,
                    "Detail": "The assignment fails full roster revalidation.",
                }
            )
        state.append({"AgentKey": agent, "Occurrence": occurrence})
    return diagnostics
