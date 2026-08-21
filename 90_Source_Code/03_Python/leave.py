"""Deterministic interval leave-capacity calculation for WFM OS."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
import re
from typing import Iterable, Mapping


LeaveRecord = Mapping[str, object]
LEAVE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LEAVE_INTERVAL_HOURS = Decimal("0.5")


def _leave_date(value: object, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if len(text) >= 10:
        text = text[:10]
    if not LEAVE_DATE.fullmatch(text):
        raise ValueError(f"{field} must use strict YYYY-MM-DD format")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid date") from exc


def _leave_decimal(value: object, field: str, *, minimum: Decimal | None = None) -> Decimal:
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


def _leave_text(row: LeaveRecord, field: str) -> str:
    if field not in row:
        raise ValueError(f"Missing field: {field}")
    value = str(row[field]).strip()
    if not value:
        raise ValueError(f"{field} cannot be blank")
    return value


def _leave_approved(value: object, field: str = "ApprovedFlag") -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().upper() in {"TRUE", "FALSE"}:
        return value.strip().upper() == "TRUE"
    raise ValueError(f"{field} must be TRUE or FALSE")


def _prepare_leave_policies(rows: Iterable[LeaveRecord]) -> dict[str, list[dict[str, object]]]:
    policies: dict[str, list[dict[str, object]]] = defaultdict(list)
    keys: set[str] = set()
    for row in rows:
        if not _leave_approved(row.get("ApprovedFlag")):
            continue
        policy_key = _leave_text(row, "PolicyKey")
        if policy_key in keys:
            raise ValueError(f"Duplicate approved PolicyKey: {policy_key}")
        keys.add(policy_key)
        activity = _leave_text(row, "ActivityKey")
        valid_from = _leave_date(row.get("ValidFrom"), "ValidFrom")
        valid_to_value = row.get("ValidTo")
        valid_to = (
            _leave_date(valid_to_value, "ValidTo")
            if valid_to_value is not None and str(valid_to_value).strip()
            else date.max
        )
        if valid_to < valid_from:
            raise ValueError(f"Policy {policy_key} ValidTo precedes ValidFrom")
        floor = _leave_decimal(row.get("CoverageFloorPct"), "CoverageFloorPct")
        maximum_pct = _leave_decimal(row.get("MaxLeavePctOfScheduled"), "MaxLeavePctOfScheduled")
        increment = _leave_decimal(row.get("AllowanceIncrementHours"), "AllowanceIncrementHours")
        if not Decimal(1) <= floor <= Decimal(2):
            raise ValueError("CoverageFloorPct must be between 1 and 2")
        if not Decimal(0) <= maximum_pct <= Decimal(1):
            raise ValueError("MaxLeavePctOfScheduled must be between 0 and 1")
        if not Decimal(0) < increment <= LEAVE_INTERVAL_HOURS:
            raise ValueError("AllowanceIncrementHours must be greater than zero and at most 0.5")
        policies[activity].append(
            {
                "PolicyKey": policy_key,
                "ValidFrom": valid_from,
                "ValidTo": valid_to,
                "CoverageFloorPct": floor,
                "ReserveFTE": _leave_decimal(row.get("ReserveFTE"), "ReserveFTE", minimum=Decimal(0)),
                "MaxLeavePctOfScheduled": maximum_pct,
                "AllowanceIncrementHours": increment,
            }
        )
    if not policies:
        raise ValueError("At least one approved leave policy is required")
    for activity, activity_rows in policies.items():
        ordered = sorted(activity_rows, key=lambda row: (row["ValidFrom"], row["ValidTo"], row["PolicyKey"]))
        for prior, current in zip(ordered, ordered[1:]):
            if current["ValidFrom"] <= prior["ValidTo"]:
                raise ValueError(f"Approved leave policies overlap for {activity}")
        policies[activity] = ordered
    return policies


def calculate_leave_allowance(
    schedule_coverage_rows: Iterable[LeaveRecord],
    policy_rows: Iterable[LeaveRecord],
) -> list[dict[str, object]]:
    """Calculate the maximum removable staff-hours at each approved interval."""
    policies = _prepare_leave_policies(policy_rows)
    seen: set[tuple[str, str, str]] = set()
    output: list[dict[str, object]] = []
    for row in schedule_coverage_rows:
        scenario = _leave_text(row, "ScenarioKey").upper()
        interval_start = _leave_text(row, "IntervalStart")
        business_date = _leave_date(interval_start, "IntervalStart")
        activity = _leave_text(row, "ActivityKey")
        grain = (scenario, interval_start, activity)
        if grain in seen:
            raise ValueError(f"Duplicate approved schedule coverage grain: {grain}")
        seen.add(grain)
        matches = [
            policy for policy in policies.get(activity, [])
            if policy["ValidFrom"] <= business_date <= policy["ValidTo"]
        ]
        if len(matches) != 1:
            raise ValueError(f"Exactly one approved leave policy is required for {activity}/{business_date}")
        policy = matches[0]
        required = _leave_decimal(row.get("RequiredFTE"), "RequiredFTE", minimum=Decimal(0))
        scheduled = _leave_decimal(
            row.get("ScheduledProductiveFTE"), "ScheduledProductiveFTE", minimum=Decimal(0)
        )
        floor_fte = required * policy["CoverageFloorPct"] + policy["ReserveFTE"]
        headroom_fte = max(Decimal(0), scheduled - floor_fte)
        percentage_cap_fte = scheduled * policy["MaxLeavePctOfScheduled"]
        allowance_fte = min(headroom_fte, percentage_cap_fte)
        raw_hours = allowance_fte * LEAVE_INTERVAL_HOURS
        increment = policy["AllowanceIncrementHours"]
        allowance_hours = (raw_hours / increment).to_integral_value(rounding=ROUND_FLOOR) * increment
        remaining = scheduled - allowance_hours / LEAVE_INTERVAL_HOURS
        output.append(
            {
                "LeaveCandidateKey": "|".join((scenario, interval_start, activity)),
                "SchedulePlanVersionKey": str(row.get("SchedulePlanVersionKey") or "").strip(),
                "ScenarioKey": scenario,
                "PolicyKey": policy["PolicyKey"],
                "BusinessDate": business_date.isoformat(),
                "IntervalStart": interval_start,
                "IntervalKey": str(row.get("IntervalKey") or "").strip(),
                "ActivityKey": activity,
                "RequiredFTE": required,
                "ScheduledProductiveFTE": scheduled,
                "CoverageFloorFTE": floor_fte,
                "CalculatedAllowanceHours": allowance_hours,
                "RecommendedAllowanceHours": allowance_hours,
                "RemainingCoverageFTE": remaining,
                "AllowanceStatus": "AVAILABLE" if allowance_hours > 0 else "NO_HEADROOM",
            }
        )
    if not output:
        raise ValueError("Approved schedule coverage cannot be empty")
    return sorted(output, key=lambda row: (row["ScenarioKey"], row["IntervalStart"], row["ActivityKey"]))
