"""Deterministic paid-supply projection and hiring-wave planning for WFM OS."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import re
from typing import Iterable, Mapping, Sequence


Record = Mapping[str, object]
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def _optional_decimal(value: object, field: str) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    return _decimal(value, field)


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    number = _decimal(value, field)
    if number != number.to_integral_value() or number < minimum:
        raise ValueError(f"{field} must be an integer at least {minimum}")
    return int(number)


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


def _monday(value: object, field: str) -> date:
    result = _date(value, field)
    if result.weekday() != 0:
        raise ValueError(f"{field} must be a Monday")
    return result


def project_base_paid_supply(assumption_rows: Iterable[Record]) -> list[dict[str, object]]:
    """Recursively project approved weekly base paid supply by activity."""
    grouped: dict[str, list[tuple[date, Record]]] = defaultdict(list)
    seen: set[tuple[str, date]] = set()
    for row in assumption_rows:
        if not _approved(row.get("ApprovedFlag")):
            continue
        activity = _text(row, "ActivityKey")
        period = _monday(row.get("PeriodStart"), "PeriodStart")
        grain = (activity, period)
        if grain in seen:
            raise ValueError(f"Duplicate approved supply assumption: {grain}")
        seen.add(grain)
        grouped[activity].append((period, row))
    if not grouped:
        raise ValueError("At least one approved supply assumption is required")

    output: list[dict[str, object]] = []
    for activity in sorted(grouped):
        periods = sorted(grouped[activity])
        prior_period: date | None = None
        prior_base: Decimal | None = None
        for index, (period, row) in enumerate(periods):
            if prior_period is not None and period - prior_period != timedelta(days=7):
                raise ValueError(f"Supply periods for {activity} must be contiguous Mondays")
            opening = _optional_decimal(row.get("OpeningPaidFTE"), "OpeningPaidFTE")
            transfers_in = _decimal(row.get("TransfersInFTE"), "TransfersInFTE", minimum=Decimal(0))
            transfers_out = _decimal(row.get("TransfersOutFTE"), "TransfersOutFTE", minimum=Decimal(0))
            leavers = _decimal(row.get("LeaversFTE"), "LeaversFTE", minimum=Decimal(0))
            other_change = _decimal(row.get("OtherChangeFTE"), "OtherChangeFTE")
            if index == 0:
                if opening is None or opening < 0:
                    raise ValueError(f"First period for {activity} requires nonnegative OpeningPaidFTE")
                if any(value != 0 for value in (transfers_in, transfers_out, leavers, other_change)):
                    raise ValueError("First supply period movements must be zero; OpeningPaidFTE is the opening state")
                base = opening
            else:
                if opening is not None:
                    raise ValueError("OpeningPaidFTE is allowed only in the first period")
                assert prior_base is not None
                base = prior_base + transfers_in - transfers_out - leavers + other_change
                if base < 0:
                    raise ValueError(f"Supply movements produce negative BasePaidFTE for {activity}/{period}")
            output.append(
                {
                    "PeriodStart": period.isoformat(),
                    "ActivityKey": activity,
                    "OpeningPaidFTE": opening,
                    "TransfersInFTE": transfers_in,
                    "TransfersOutFTE": transfers_out,
                    "LeaversFTE": leavers,
                    "OtherChangeFTE": other_change,
                    "BasePaidFTE": base,
                }
            )
            prior_period, prior_base = period, base
    return output


def _validate_policies(policy_rows: Iterable[Record]) -> dict[str, list[dict[str, object]]]:
    policies: dict[str, list[dict[str, object]]] = defaultdict(list)
    keys: set[str] = set()
    for row in policy_rows:
        if not _approved(row.get("ApprovedFlag")):
            continue
        policy_key = _text(row, "PolicyKey")
        if policy_key in keys:
            raise ValueError(f"Duplicate approved PolicyKey: {policy_key}")
        keys.add(policy_key)
        activity = _text(row, "ActivityKey")
        valid_from = _date(row.get("ValidFrom"), "ValidFrom")
        valid_to_value = row.get("ValidTo")
        valid_to = (
            _date(valid_to_value, "ValidTo")
            if valid_to_value is not None and str(valid_to_value).strip()
            else date.max
        )
        if valid_to < valid_from:
            raise ValueError(f"Policy {policy_key} ValidTo precedes ValidFrom")
        expected_yield = _decimal(row.get("ExpectedYield"), "ExpectedYield")
        fte_per_head = _decimal(row.get("FTEPerHead"), "FTEPerHead")
        if not Decimal(0) < expected_yield <= Decimal(1):
            raise ValueError("ExpectedYield must be greater than zero and at most one")
        if not Decimal(0) < fte_per_head <= Decimal(1):
            raise ValueError("FTEPerHead must be greater than zero and at most one")
        policy = {
            "PolicyKey": policy_key,
            "ActivityKey": activity,
            "ValidFrom": valid_from,
            "ValidTo": valid_to,
            "RecruitmentLeadDays": _integer(row.get("RecruitmentLeadDays"), "RecruitmentLeadDays"),
            "TrainingLeadDays": _integer(row.get("TrainingLeadDays"), "TrainingLeadDays"),
            "NestingLeadDays": _integer(row.get("NestingLeadDays"), "NestingLeadDays"),
            "ExpectedYield": expected_yield,
            "FTEPerHead": fte_per_head,
            "MaxTrainingSeats": _integer(row.get("MaxTrainingSeats"), "MaxTrainingSeats", minimum=1),
            "BufferPaidFTE": _decimal(row.get("BufferPaidFTE"), "BufferPaidFTE", minimum=Decimal(0)),
        }
        policies[activity].append(policy)
    if not policies:
        raise ValueError("At least one approved hiring policy is required")
    for activity, rows in policies.items():
        ordered = sorted(rows, key=lambda item: (item["ValidFrom"], item["ValidTo"], item["PolicyKey"]))
        for prior, current in zip(ordered, ordered[1:]):
            if current["ValidFrom"] <= prior["ValidTo"]:
                raise ValueError(f"Approved hiring policies overlap for {activity}")
        policies[activity] = ordered
    return policies


def _policy_for(policies: dict[str, list[dict[str, object]]], activity: str, period: date) -> dict[str, object]:
    matches = [row for row in policies.get(activity, []) if row["ValidFrom"] <= period <= row["ValidTo"]]
    if len(matches) != 1:
        raise ValueError(f"Exactly one approved hiring policy is required for {activity}/{period}")
    return matches[0]


def plan_hiring(
    requirement_rows: Iterable[Record],
    base_supply_rows: Iterable[Record],
    policy_rows: Iterable[Record],
    *,
    as_of_date: object,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Iteratively close weekly paid-FTE deficits with deterministic waves."""
    as_of = _date(as_of_date, "as_of_date")
    base: dict[tuple[date, str], Decimal] = {}
    for row in base_supply_rows:
        period = _monday(row.get("PeriodStart"), "PeriodStart")
        activity = _text(row, "ActivityKey")
        grain = (period, activity)
        if grain in base:
            raise ValueError(f"Duplicate base supply row: {grain}")
        base[grain] = _decimal(row.get("BasePaidFTE"), "BasePaidFTE", minimum=Decimal(0))

    requirements: dict[tuple[str, str], list[tuple[date, Decimal]]] = defaultdict(list)
    requirement_seen: set[tuple[str, str, date]] = set()
    for row in requirement_rows:
        scenario = _text(row, "ScenarioKey")
        activity = _text(row, "ActivityKey")
        period = _monday(row.get("PeriodStart"), "PeriodStart")
        grain = (scenario, activity, period)
        if grain in requirement_seen:
            raise ValueError(f"Duplicate capacity requirement: {grain}")
        requirement_seen.add(grain)
        requirements[(scenario, activity)].append(
            (period, _decimal(row.get("RequiredPaidFTE"), "RequiredPaidFTE", minimum=Decimal(0)))
        )
    if not requirements:
        raise ValueError("Capacity requirements cannot be empty")
    policies = _validate_policies(policy_rows)

    supply_output: list[dict[str, object]] = []
    waves: list[dict[str, object]] = []
    for (scenario, activity) in sorted(requirements):
        periods = sorted(requirements[(scenario, activity)])
        prior_period: date | None = None
        scenario_waves: list[dict[str, object]] = []
        for period, required in periods:
            if prior_period is not None and period - prior_period != timedelta(days=7):
                raise ValueError(f"Requirement periods for {scenario}/{activity} must be contiguous Mondays")
            baseline = base.get((period, activity))
            if baseline is None:
                raise ValueError(f"Missing base supply for {activity}/{period}")
            policy = _policy_for(policies, activity, period)
            prior_hire_fte = sum(
                wave["ExpectedPaidFTE"] for wave in scenario_waves if wave["ProficiencyDate"] <= period
            )
            target = required + policy["BufferPaidFTE"]
            deficit = max(Decimal(0), target - baseline - prior_hire_fte)
            if deficit > 0:
                contribution_per_head = policy["ExpectedYield"] * policy["FTEPerHead"]
                heads = int((deficit / contribution_per_head).to_integral_value(rounding=ROUND_CEILING))
                remaining = heads
                wave_part = 1
                while remaining > 0:
                    part_heads = min(remaining, policy["MaxTrainingSeats"])
                    nesting_start = period - timedelta(days=policy["NestingLeadDays"])
                    training_start = nesting_start - timedelta(days=policy["TrainingLeadDays"])
                    recruitment_start = training_start - timedelta(days=policy["RecruitmentLeadDays"])
                    wave = {
                        "WaveKey": f"{scenario}|{activity}|{period.isoformat()}|W{wave_part:02d}",
                        "ScenarioKey": scenario,
                        "ActivityKey": activity,
                        "PolicyKey": policy["PolicyKey"],
                        "PlannedHeads": part_heads,
                        "ExpectedYield": policy["ExpectedYield"],
                        "FTEPerHead": policy["FTEPerHead"],
                        "ExpectedPaidFTE": Decimal(part_heads) * contribution_per_head,
                        "RecruitmentStart": recruitment_start,
                        "TrainingStart": training_start,
                        "NestingStart": nesting_start,
                        "ProficiencyDate": period,
                        "TimingStatus": "LATE_TO_PLAN" if recruitment_start < as_of else "ON_TIME",
                    }
                    scenario_waves.append(wave)
                    waves.append({
                        **wave,
                        "RecruitmentStart": recruitment_start.isoformat(),
                        "TrainingStart": training_start.isoformat(),
                        "NestingStart": nesting_start.isoformat(),
                        "ProficiencyDate": period.isoformat(),
                    })
                    remaining -= part_heads
                    wave_part += 1
            planned_hire = sum(
                wave["ExpectedPaidFTE"] for wave in scenario_waves if wave["ProficiencyDate"] <= period
            )
            projected = baseline + planned_hire
            residual = max(Decimal(0), target - projected)
            supply_output.append(
                {
                    "PeriodStart": period.isoformat(),
                    "ScenarioKey": scenario,
                    "ActivityKey": activity,
                    "PolicyKey": policy["PolicyKey"],
                    "RequiredPaidFTE": required,
                    "BufferPaidFTE": policy["BufferPaidFTE"],
                    "BaselinePaidFTE": baseline,
                    "PlannedHirePaidFTE": planned_hire,
                    "ProjectedPaidFTE": projected,
                    "ResidualGapPaidFTE": residual,
                }
            )
            prior_period = period
    return supply_output, waves
