"""Governed full-request leave recommendation for an approved named roster."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping


LeaveRequestRecord = Mapping[str, object]
LEAVE_REQUEST_INTERVAL = timedelta(minutes=30)
LEAVE_REQUEST_METHOD = "LEAVE_REQUEST_QUEUE_V1"


def _leave_request_text(row: LeaveRequestRecord, field: str) -> str:
    if field not in row:
        raise ValueError(f"Missing field: {field}")
    value = str(row[field]).strip()
    if not value:
        raise ValueError(f"{field} cannot be blank")
    return value


def _leave_request_datetime(value: object, field: str, *, align: bool = True) -> datetime:
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
        raise ValueError(f"{field} must be timezone-naive local time")
    if align and (result.minute not in {0, 30} or result.second or result.microsecond):
        raise ValueError(f"{field} must align to an exact 30-minute boundary")
    return result


def _leave_request_date(value: object, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a valid date") from exc


def _leave_request_decimal(
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


def _leave_request_integer(value: object, field: str, *, minimum: int = 0) -> int:
    number = _leave_request_decimal(value, field)
    if number != number.to_integral_value() or number < minimum:
        raise ValueError(f"{field} must be an integer at least {minimum}")
    return int(number)


def _leave_request_true(value: object, field: str = "Approved") -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().upper() in {"TRUE", "FALSE"}:
        return value.strip().upper() == "TRUE"
    raise ValueError(f"{field} must be TRUE or FALSE")


def _leave_request_active(row: LeaveRequestRecord, on_date: date) -> bool:
    valid_from = _leave_request_date(row.get("ValidFrom"), "ValidFrom")
    raw_valid_to = row.get("ValidTo")
    valid_to = (
        _leave_request_date(raw_valid_to, "ValidTo")
        if raw_valid_to is not None and str(raw_valid_to).strip()
        else date.max
    )
    if valid_to < valid_from:
        raise ValueError("ValidTo cannot precede ValidFrom")
    return valid_from <= on_date <= valid_to


def _leave_request_policy(
    rows: list[dict[str, object]], leave_type: str, on_date: date
) -> dict[str, object]:
    matches = [
        row for row in rows
        if _leave_request_true(row.get("Approved"))
        and _leave_request_text(row, "LeaveTypeKey") == leave_type
        and _leave_request_active(row, on_date)
    ]
    if len(matches) != 1:
        raise ValueError(f"Exactly one approved leave-type policy is required for {leave_type}/{on_date}")
    policy = matches[0]
    if _leave_request_text(policy, "CapacityDecisionMode").upper() not in {
        "CAPACITY_CONTROLLED", "INFORMATION_ONLY", "ALWAYS_REVIEW"
    }:
        raise ValueError("Unsupported CapacityDecisionMode")
    if _leave_request_text(policy, "EntitlementCheckMode").upper() not in {
        "REQUIRED", "OPTIONAL", "NONE"
    }:
        raise ValueError("Unsupported EntitlementCheckMode")
    if _leave_request_text(policy, "PartialApprovalMode").upper() != "FULL_REQUEST_ONLY":
        raise ValueError("v0.6 supports only FULL_REQUEST_ONLY leave decisions")
    return policy


def _leave_request_roster_intervals(
    segment_rows: list[dict[str, object]], agent: str, start: datetime, end: datetime
) -> list[dict[str, object]]:
    by_interval: dict[tuple[datetime, str], dict[str, object]] = {}
    for row in segment_rows:
        if _leave_request_text(row, "AgentKey") != agent:
            continue
        interval_start = _leave_request_datetime(row.get("IntervalStart"), "IntervalStart")
        interval_end = interval_start + LEAVE_REQUEST_INTERVAL
        if interval_start < end and interval_end > start:
            key = (interval_start, _leave_request_text(row, "ActivityKey"))
            current = by_interval.setdefault(
                key,
                {
                    "IntervalStart": interval_start,
                    "ActivityKey": key[1],
                    "PaidFlag": False,
                    "ProductiveFlag": False,
                },
            )
            current["PaidFlag"] = bool(current["PaidFlag"]) or bool(row.get("PaidFlag"))
            current["ProductiveFlag"] = bool(current["ProductiveFlag"]) or bool(row.get("ProductiveFlag"))
    return [by_interval[key] for key in sorted(by_interval)]


def _leave_request_allowances(
    rows: list[dict[str, object]], leave_plan_version: str
) -> dict[tuple[datetime, str], Decimal]:
    output: dict[tuple[datetime, str], Decimal] = {}
    for row in rows:
        if str(row.get("LeavePlanVersionKey") or "").strip() not in {"", leave_plan_version}:
            continue
        status = str(row.get("ApprovalStatus") or "APPROVED").strip().upper()
        if status != "APPROVED":
            continue
        interval = _leave_request_datetime(row.get("IntervalStart"), "IntervalStart")
        activity = _leave_request_text(row, "ActivityKey")
        grain = (interval, activity)
        if grain in output:
            raise ValueError(f"Duplicate approved leave allowance: {grain}")
        raw = row.get("ApprovedAllowanceHours")
        if raw is None or str(raw).strip() == "":
            raw = row.get("CalculatedAllowanceHours")
        output[grain] = _leave_request_decimal(raw, "ApprovedAllowanceHours", minimum=Decimal(0))
    if not output:
        raise ValueError("Approved leave-plan allowance cannot be empty")
    return output


def _leave_request_entitlement(
    rows: list[dict[str, object]], agent: str, leave_type: str, on_date: date
) -> Decimal | None:
    matches = [
        row for row in rows
        if str(row.get("AgentKey") or "").strip() == agent
        and str(row.get("LeaveTypeKey") or "").strip() == leave_type
        and _leave_request_true(row.get("Approved"))
        and _leave_request_date(row.get("AsOfDate"), "AsOfDate") <= on_date
    ]
    if not matches:
        return None
    latest_date = max(_leave_request_date(row.get("AsOfDate"), "AsOfDate") for row in matches)
    latest = [row for row in matches if _leave_request_date(row.get("AsOfDate"), "AsOfDate") == latest_date]
    if len(latest) != 1:
        raise ValueError(f"Ambiguous latest entitlement snapshot for {agent}/{leave_type}")
    return _leave_request_decimal(latest[0].get("AvailableHours"), "AvailableHours", minimum=Decimal(0))


def evaluate_leave_requests(
    roster_assignment_rows: Iterable[LeaveRequestRecord],
    roster_segment_rows: Iterable[LeaveRequestRecord],
    leave_plan_rows: Iterable[LeaveRequestRecord],
    request_rows: Iterable[LeaveRequestRecord],
    leave_type_policy_rows: Iterable[LeaveRequestRecord],
    entitlement_snapshot_rows: Iterable[LeaveRequestRecord],
    prior_decision_rows: Iterable[LeaveRequestRecord] = (),
    *,
    swap_decision_version: str = "",
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Evaluate queued full leave requests without approving or mutating roster rows."""
    assignments = [dict(row) for row in roster_assignment_rows]
    segments = [dict(row) for row in roster_segment_rows]
    leave_plan = [dict(row) for row in leave_plan_rows]
    requests = [dict(row) for row in request_rows]
    policies = [dict(row) for row in leave_type_policy_rows]
    snapshots = [dict(row) for row in entitlement_snapshot_rows]
    prior = [dict(row) for row in prior_decision_rows]
    if not assignments or not segments:
        raise ValueError("An approved named roster and its interval segments are required")
    roster_versions = {
        str(row.get("RosterVersionKey") or "").strip()
        for row in assignments
        if str(row.get("RosterVersionKey") or "").strip()
    }
    if len(roster_versions) > 1:
        raise ValueError("Leave evaluation requires one roster version")
    roster_version = next(iter(roster_versions), "")
    leave_versions = {
        str(row.get("LeavePlanVersionKey") or "").strip()
        for row in leave_plan
        if str(row.get("LeavePlanVersionKey") or "").strip()
    }
    if len(leave_versions) != 1:
        raise ValueError("Leave evaluation requires one approved leave-plan version")
    leave_plan_version = next(iter(leave_versions))
    allowance = _leave_request_allowances(leave_plan, leave_plan_version)

    capacity_used: dict[tuple[datetime, str], Decimal] = defaultdict(Decimal)
    consumed_agent_intervals: set[tuple[str, datetime]] = set()
    entitlement_used: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for decision in prior:
        if str(decision.get("ApprovalStatus") or "").strip().upper() != "APPROVED":
            continue
        if str(decision.get("RecommendationStatus") or "").strip().upper() not in {"APPROVE", "APPROVED"}:
            continue
        agent = _leave_request_text(decision, "AgentKey")
        leave_type = _leave_request_text(decision, "LeaveTypeKey")
        start = _leave_request_datetime(decision.get("RequestedStart"), "RequestedStart")
        end = _leave_request_datetime(decision.get("RequestedEnd"), "RequestedEnd")
        for interval in _leave_request_roster_intervals(segments, agent, start, end):
            if interval["PaidFlag"]:
                consumed_agent_intervals.add((agent, interval["IntervalStart"]))
            if interval["ProductiveFlag"]:
                capacity_used[(interval["IntervalStart"], interval["ActivityKey"])] += Decimal("0.5")
        entitlement_used[(agent, leave_type)] += _leave_request_decimal(
            decision.get("ApprovedHours", 0), "ApprovedHours", minimum=Decimal(0)
        )

    ordered_requests: list[tuple[int, datetime, str, dict[str, object]]] = []
    seen_keys: set[str] = set()
    for request in requests:
        if not str(request.get("LeaveRequestKey") or "").strip():
            continue
        key = _leave_request_text(request, "LeaveRequestKey")
        if key in seen_keys:
            raise ValueError(f"Duplicate LeaveRequestKey: {key}")
        seen_keys.add(key)
        status = _leave_request_text(request, "RequestStatus").upper()
        if status not in {"PENDING", "SUBMITTED"}:
            continue
        ordered_requests.append(
            (
                _leave_request_integer(request.get("PriorityRank"), "PriorityRank", minimum=0),
                _leave_request_datetime(request.get("SubmittedAt"), "SubmittedAt", align=False),
                key,
                request,
            )
        )
    ordered_requests.sort(key=lambda item: item[:3])

    decisions: list[dict[str, object]] = []
    consumption: list[dict[str, object]] = []
    for _, _, request_key, request in ordered_requests:
        agent = _leave_request_text(request, "AgentKey")
        leave_type = _leave_request_text(request, "LeaveTypeKey")
        start = _leave_request_datetime(request.get("RequestedStart"), "RequestedStart")
        end = _leave_request_datetime(request.get("RequestedEnd"), "RequestedEnd")
        if end <= start:
            raise ValueError(f"RequestedEnd must follow RequestedStart for {request_key}")
        policy = _leave_request_policy(policies, leave_type, start.date())
        mode = _leave_request_text(policy, "CapacityDecisionMode").upper()
        entitlement_mode = _leave_request_text(policy, "EntitlementCheckMode").upper()
        roster_intervals = _leave_request_roster_intervals(segments, agent, start, end)
        paid_intervals = [row for row in roster_intervals if row["PaidFlag"]]
        productive_intervals = [row for row in roster_intervals if row["ProductiveFlag"]]
        requested_hours = Decimal("0.5") * len(paid_intervals)
        recommendation = "APPROVE"
        reason = "FULL_REQUEST_WITHIN_GOVERNED_LIMITS"

        if mode == "ALWAYS_REVIEW":
            recommendation = "REVIEW_REQUIRED"
            reason = "LOCAL_OR_PROTECTED_LEAVE_REQUIRES_HUMAN_REVIEW"
        elif not paid_intervals:
            recommendation = "REVIEW_REQUIRED"
            reason = "NO_SCHEDULED_PAID_TIME_IN_REQUEST"
        elif any((agent, row["IntervalStart"]) in consumed_agent_intervals for row in paid_intervals):
            recommendation = "DECLINE"
            reason = "OVERLAPS_EXISTING_APPROVED_LEAVE"

        entitlement = _leave_request_entitlement(snapshots, agent, leave_type, start.date())
        remaining_entitlement = (
            entitlement - entitlement_used[(agent, leave_type)]
            if entitlement is not None else None
        )
        if recommendation == "APPROVE" and entitlement_mode == "REQUIRED" and entitlement is None:
            recommendation = "REVIEW_REQUIRED"
            reason = "REQUIRED_ENTITLEMENT_SNAPSHOT_MISSING"
        elif (
            recommendation == "APPROVE"
            and entitlement_mode in {"REQUIRED", "OPTIONAL"}
            and remaining_entitlement is not None
            and remaining_entitlement < requested_hours
        ):
            recommendation = "DECLINE"
            reason = "INSUFFICIENT_EXTERNAL_ENTITLEMENT_SNAPSHOT"

        if recommendation == "APPROVE" and mode == "CAPACITY_CONTROLLED":
            failing = [
                row for row in productive_intervals
                if capacity_used[(row["IntervalStart"], row["ActivityKey"])] + Decimal("0.5")
                > allowance.get((row["IntervalStart"], row["ActivityKey"]), Decimal(0))
            ]
            if failing:
                recommendation = "DECLINE"
                reason = "APPROVED_LEAVE_CAPACITY_EXHAUSTED"

        approved_hours = requested_hours if recommendation == "APPROVE" else Decimal(0)
        decisions.append(
            {
                "LeaveDecisionRowKey": f"LEAVE_DECISION|{request_key}",
                "LeaveDecisionVersionKey": "",
                "RosterVersionKey": roster_version,
                "SwapDecisionVersionKey": swap_decision_version,
                "LeavePlanVersionKey": leave_plan_version,
                "LeaveRequestKey": request_key,
                "ApprovalStatus": "PENDING",
                "AgentKey": agent,
                "LeaveTypeKey": leave_type,
                "RequestedStart": start.isoformat(),
                "RequestedEnd": end.isoformat(),
                "RequestedHours": requested_hours,
                "ApprovedHours": approved_hours,
                "RecommendationMethod": LEAVE_REQUEST_METHOD,
                "RecommendationStatus": recommendation,
                "DecisionReason": reason,
                "ExternalEntitlementHours": entitlement,
                "RemainingEntitlementBeforeRequest": remaining_entitlement,
            }
        )
        if recommendation == "APPROVE":
            entitlement_used[(agent, leave_type)] += requested_hours
            for row in paid_intervals:
                consumed_agent_intervals.add((agent, row["IntervalStart"]))
            for row in productive_intervals:
                grain = (row["IntervalStart"], row["ActivityKey"])
                capacity_used[grain] += Decimal("0.5")
                consumption.append(
                    {
                        "LeaveRequestKey": request_key,
                        "AgentKey": agent,
                        "IntervalStart": row["IntervalStart"].isoformat(),
                        "ActivityKey": row["ActivityKey"],
                        "ConsumedAllowanceHours": Decimal("0.5"),
                        "RemainingAllowanceHours": allowance.get(grain, Decimal(0)) - capacity_used[grain],
                    }
                )
    return decisions, consumption
