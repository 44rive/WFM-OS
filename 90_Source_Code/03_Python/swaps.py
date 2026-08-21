"""Bilateral whole-occurrence swap validation for WFM OS."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping


SwapRecord = Mapping[str, object]
SWAP_METHOD = "SWAP_VALIDATE_V1"


def _swap_text(row: SwapRecord, field: str) -> str:
    if field not in row:
        raise ValueError(f"Missing field: {field}")
    value = str(row[field]).strip()
    if not value:
        raise ValueError(f"{field} cannot be blank")
    return value


def _swap_datetime(value: object, field: str, *, optional: bool = False) -> datetime | None:
    if value is None or str(value).strip() == "":
        if optional:
            return None
        raise ValueError(f"{field} cannot be blank")
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
    return result


def _swap_assignment_for(
    assignment_index: dict[str, dict[str, object]], assignment_key: str
) -> dict[str, object] | None:
    return assignment_index.get(assignment_key)


def evaluate_swap_requests(
    roster_assignment_rows: Iterable[SwapRecord],
    request_rows: Iterable[SwapRecord],
    agent_rows: Iterable[SwapRecord],
    roster_policy_rows: Iterable[SwapRecord],
    contract_rows: Iterable[SwapRecord],
    activity_eligibility_rows: Iterable[SwapRecord],
    agent_skill_rows: Iterable[SwapRecord],
    skill_requirement_rows: Iterable[SwapRecord],
    availability_rows: Iterable[SwapRecord],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """Recommend bilateral swaps after simulating and revalidating the full roster."""
    assignments = [dict(row) for row in roster_assignment_rows]
    if not assignments:
        raise ValueError("An approved named roster is required")
    assignment_index: dict[str, dict[str, object]] = {}
    for assignment in assignments:
        key = _swap_text(assignment, "AssignmentKey")
        if key in assignment_index:
            raise ValueError(f"Duplicate AssignmentKey: {key}")
        if not assignment.get("Occurrence"):
            raise ValueError("Swap validation requires the governed whole Occurrence payload")
        assignment_index[key] = assignment
    roster_versions = {
        str(row.get("RosterVersionKey") or "").strip()
        for row in assignments
        if str(row.get("RosterVersionKey") or "").strip()
    }
    if len(roster_versions) != 1:
        raise ValueError("Swap validation requires exactly one approved roster version")
    roster_version = next(iter(roster_versions))

    ordered: list[tuple[datetime, str, dict[str, object]]] = []
    seen_requests: set[str] = set()
    for source in request_rows:
        request = dict(source)
        if not str(request.get("SwapRequestKey") or "").strip():
            continue
        key = _swap_text(request, "SwapRequestKey")
        if key in seen_requests:
            raise ValueError(f"Duplicate SwapRequestKey: {key}")
        seen_requests.add(key)
        if _swap_text(request, "RequestStatus").upper() not in {"PENDING", "SUBMITTED"}:
            continue
        ordered.append((_swap_datetime(request.get("SubmittedAt"), "SubmittedAt"), key, request))
    ordered.sort(key=lambda item: item[:2])

    decisions: list[dict[str, object]] = []
    proposals: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    reserved_assignments: set[str] = set()
    working = list(assignments)
    for _, request_key, request in ordered:
        assignment_key_a = _swap_text(request, "AssignmentKeyA")
        assignment_key_b = _swap_text(request, "AssignmentKeyB")
        agent_a = _swap_text(request, "AgentKeyA")
        agent_b = _swap_text(request, "AgentKeyB")
        recommendation = "APPROVE"
        reason = "BILATERAL_WHOLE_OCCURRENCE_SWAP_VALID"
        validation_reason = ""

        if str(request.get("RosterVersionKey") or "").strip() != roster_version:
            recommendation, reason = "DECLINE", "ROSTER_VERSION_MISMATCH"
        elif assignment_key_a == assignment_key_b or agent_a == agent_b:
            recommendation, reason = "DECLINE", "SWAP_REQUIRES_TWO_DISTINCT_ASSIGNMENTS_AND_AGENTS"
        elif _swap_datetime(request.get("ConsentAAt"), "ConsentAAt", optional=True) is None:
            recommendation, reason = "REVIEW_REQUIRED", "AGENT_A_CONSENT_MISSING"
        elif _swap_datetime(request.get("ConsentBAt"), "ConsentBAt", optional=True) is None:
            recommendation, reason = "REVIEW_REQUIRED", "AGENT_B_CONSENT_MISSING"
        elif assignment_key_a in reserved_assignments or assignment_key_b in reserved_assignments:
            recommendation, reason = "DECLINE", "ASSIGNMENT_ALREADY_RESERVED_BY_EARLIER_SWAP"

        assignment_a = _swap_assignment_for(assignment_index, assignment_key_a)
        assignment_b = _swap_assignment_for(assignment_index, assignment_key_b)
        if recommendation == "APPROVE" and (assignment_a is None or assignment_b is None):
            recommendation, reason = "DECLINE", "ASSIGNMENT_NOT_FOUND_IN_APPROVED_ROSTER"
        if (
            recommendation == "APPROVE"
            and (
                _swap_text(assignment_a, "AgentKey") != agent_a
                or _swap_text(assignment_b, "AgentKey") != agent_b
            )
        ):
            recommendation, reason = "DECLINE", "REQUESTED_AGENT_DOES_NOT_OWN_ASSIGNMENT"

        proposed_a: dict[str, object] | None = None
        proposed_b: dict[str, object] | None = None
        if recommendation == "APPROVE":
            proposed_a = dict(assignment_a)
            proposed_b = dict(assignment_b)
            proposed_a["AgentKey"] = agent_b
            proposed_b["AgentKey"] = agent_a
            proposed_a["OriginalAssignmentKey"] = assignment_key_a
            proposed_b["OriginalAssignmentKey"] = assignment_key_b
            proposed_a["AssignmentKey"] = assignment_key_a
            proposed_b["AssignmentKey"] = assignment_key_b
            proposed_a["SwapRequestKey"] = request_key
            proposed_b["SwapRequestKey"] = request_key
            proposed_a["AssignmentStatus"] = "PROPOSED_SWAP"
            proposed_b["AssignmentStatus"] = "PROPOSED_SWAP"
            simulated = [
                proposed_a if row["AssignmentKey"] == assignment_key_a
                else proposed_b if row["AssignmentKey"] == assignment_key_b
                else row
                for row in working
            ]
            validation = validate_named_roster(
                simulated,
                agent_rows,
                roster_policy_rows,
                contract_rows,
                activity_eligibility_rows,
                agent_skill_rows,
                skill_requirement_rows,
                availability_rows,
            )
            blocking = [row for row in validation if row.get("Severity") == "BLOCKING"]
            if blocking:
                recommendation = "DECLINE"
                validation_reason = str(blocking[0].get("ReasonCode") or "ROSTER_REVALIDATION_FAILED")
                reason = f"FULL_ROSTER_REVALIDATION_FAILED:{validation_reason}"
                diagnostics.extend(
                    {
                        **row,
                        "DiagnosticKey": f"SWAP|{request_key}|{row['DiagnosticKey']}",
                        "SwapRequestKey": request_key,
                    }
                    for row in blocking
                )
            else:
                working = simulated
                assignment_index.pop(assignment_key_a)
                assignment_index.pop(assignment_key_b)
                assignment_index[proposed_a["AssignmentKey"]] = proposed_a
                assignment_index[proposed_b["AssignmentKey"]] = proposed_b
                reserved_assignments.update({assignment_key_a, assignment_key_b})
                proposals.extend([proposed_a, proposed_b])

        decisions.append(
            {
                "SwapDecisionRowKey": f"SWAP_DECISION|{request_key}",
                "SwapDecisionVersionKey": "",
                "RosterVersionKey": roster_version,
                "SwapRequestKey": request_key,
                "ApprovalStatus": "PENDING",
                "AssignmentKeyA": assignment_key_a,
                "AgentKeyA": agent_a,
                "AssignmentKeyB": assignment_key_b,
                "AgentKeyB": agent_b,
                "RecommendationMethod": SWAP_METHOD,
                "RecommendationStatus": recommendation,
                "DecisionReason": reason,
                "ValidationReason": validation_reason,
            }
        )
    return decisions, proposals, diagnostics
