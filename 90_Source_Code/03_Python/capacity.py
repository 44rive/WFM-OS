"""Dependency-free synchronous and asynchronous WFM capacity calculations."""

from __future__ import annotations

import math
from typing import Mapping


def _finite(value: object, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric, not boolean")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return number


def _validate_common(
    volume: object,
    aht_seconds: object,
    interval_minutes: object,
    occupancy: object,
    concurrency: object,
    shrinkage: object,
    fte_per_head: object,
) -> tuple[float, float, float, float, float, float, float]:
    demand = _finite(volume, "volume", minimum=0.0)
    aht = _finite(aht_seconds, "aht_seconds", minimum=0.0)
    interval = _finite(interval_minutes, "interval_minutes", minimum=0.0)
    occupancy_value = _finite(occupancy, "occupancy", minimum=0.0)
    concurrency_value = _finite(concurrency, "concurrency", minimum=1.0)
    shrinkage_value = _finite(shrinkage, "shrinkage", minimum=0.0)
    fte_value = _finite(fte_per_head, "fte_per_head", minimum=0.0)
    if interval <= 0:
        raise ValueError("interval_minutes must be greater than zero")
    if demand > 0 and aht <= 0:
        raise ValueError("aht_seconds must be greater than zero when volume is positive")
    if not 0 < occupancy_value <= 1:
        raise ValueError("occupancy must be greater than zero and at most one")
    if not 0 <= shrinkage_value < 1:
        raise ValueError("shrinkage must be at least zero and less than one")
    if not 0 < fte_value <= 1:
        raise ValueError("fte_per_head must be greater than zero and at most one")
    return demand, aht, interval, occupancy_value, concurrency_value, shrinkage_value, fte_value


def _paid_and_heads(productive_fte: float, shrinkage: float, fte_per_head: float) -> tuple[float, int]:
    paid_fte = productive_fte / (1.0 - shrinkage)
    required_heads = math.ceil(paid_fte / fte_per_head) if paid_fte else 0
    return paid_fte, required_heads


def _erlang_c_wait_probability(traffic: float, agents: int) -> float:
    if traffic == 0:
        return 0.0
    if agents <= traffic:
        return 1.0
    erlang_b = 1.0
    for server in range(1, agents + 1):
        erlang_b = (traffic * erlang_b) / (server + traffic * erlang_b)
    utilization = traffic / agents
    return erlang_b / (1.0 - utilization + utilization * erlang_b)


def erlang_c_capacity(
    *,
    volume: object,
    aht_seconds: object,
    interval_minutes: object,
    target_service_level: object,
    answer_time_seconds: object,
    occupancy: object,
    concurrency: object = 1.0,
    shrinkage: object = 0.0,
    fte_per_head: object = 1.0,
    max_agents: int = 100_000,
) -> dict[str, object]:
    """Return capacity for synchronous demand using Erlang C.

    Concurrency reduces offered traffic before queueing. Productive FTE is the
    first integer agent count satisfying both service level and occupancy.
    Shrinkage then converts productive FTE to paid FTE; required heads are paid
    FTE divided by FTE per head, rounded upward.
    """
    demand, aht, interval, occupancy_limit, concurrency_value, shrinkage_value, fte_value = _validate_common(
        volume, aht_seconds, interval_minutes, occupancy, concurrency, shrinkage, fte_per_head
    )
    service_target = _finite(target_service_level, "target_service_level", minimum=0.0)
    answer_target = _finite(answer_time_seconds, "answer_time_seconds", minimum=0.0)
    if not 0 < service_target < 1:
        raise ValueError("target_service_level must be greater than zero and less than one")
    if isinstance(max_agents, bool) or not isinstance(max_agents, int) or max_agents <= 0:
        raise ValueError("max_agents must be a positive integer")
    offered_traffic = demand * aht / (interval * 60.0)
    effective_traffic = offered_traffic / concurrency_value
    if demand == 0:
        return {
            "Method": "ERLANG_C",
            "OfferedTrafficErlangs": 0.0,
            "EffectiveTrafficErlangs": 0.0,
            "ProductiveFTE": 0.0,
            "PaidFTE": 0.0,
            "RequiredHeads": 0,
            "AchievedOccupancy": 0.0,
            "AchievedServiceLevel": 1.0,
        }

    first_agent_count = max(1, math.floor(effective_traffic) + 1)
    for agents in range(first_agent_count, max_agents + 1):
        achieved_occupancy = effective_traffic / agents
        wait_probability = _erlang_c_wait_probability(effective_traffic, agents)
        achieved_service = 1.0 - wait_probability * math.exp(
            -(agents - effective_traffic) * answer_target / aht
        )
        if achieved_occupancy <= occupancy_limit and achieved_service >= service_target:
            paid_fte, required_heads = _paid_and_heads(float(agents), shrinkage_value, fte_value)
            return {
                "Method": "ERLANG_C",
                "OfferedTrafficErlangs": offered_traffic,
                "EffectiveTrafficErlangs": effective_traffic,
                "ProductiveFTE": float(agents),
                "PaidFTE": paid_fte,
                "RequiredHeads": required_heads,
                "AchievedOccupancy": achieved_occupancy,
                "AchievedServiceLevel": achieved_service,
            }
    raise ValueError(f"No Erlang C solution found within max_agents={max_agents}")


def workload_capacity(
    *,
    volume: object,
    aht_seconds: object,
    interval_minutes: object,
    occupancy: object,
    concurrency: object = 1.0,
    shrinkage: object = 0.0,
    fte_per_head: object = 1.0,
) -> dict[str, object]:
    """Return capacity for asynchronous work using a workload model."""
    demand, aht, interval, occupancy_limit, concurrency_value, shrinkage_value, fte_value = _validate_common(
        volume, aht_seconds, interval_minutes, occupancy, concurrency, shrinkage, fte_per_head
    )
    offered_traffic = demand * aht / (interval * 60.0)
    effective_traffic = offered_traffic / concurrency_value
    productive_fte = effective_traffic / occupancy_limit
    paid_fte, required_heads = _paid_and_heads(productive_fte, shrinkage_value, fte_value)
    return {
        "Method": "WORKLOAD",
        "OfferedTrafficErlangs": offered_traffic,
        "EffectiveTrafficErlangs": effective_traffic,
        "ProductiveFTE": productive_fte,
        "PaidFTE": paid_fte,
        "RequiredHeads": required_heads,
        "AchievedOccupancy": occupancy_limit if demand else 0.0,
        "AchievedServiceLevel": None,
    }


def calculate_capacity(method: str, **parameters: object) -> dict[str, object]:
    """Dispatch a canonical capacity method without vendor-specific behavior."""
    normalized = str(method).strip().upper()
    if normalized == "ERLANG_C":
        return erlang_c_capacity(**parameters)
    if normalized == "WORKLOAD":
        allowed = {
            "volume", "aht_seconds", "interval_minutes", "occupancy",
            "concurrency", "shrinkage", "fte_per_head",
        }
        unexpected = sorted(set(parameters) - allowed)
        if unexpected:
            raise ValueError(f"WORKLOAD received unsupported parameters: {', '.join(unexpected)}")
        return workload_capacity(**parameters)
    raise ValueError("method must be ERLANG_C or WORKLOAD")


def calculate_capacity_row(row: Mapping[str, object]) -> dict[str, object]:
    """Translate a canonical CSV/worksheet row into a capacity result."""
    method = str(row.get("Method", "")).strip().upper()
    common = {
        "volume": row.get("Volume"),
        "aht_seconds": row.get("AHTSeconds"),
        "interval_minutes": row.get("IntervalMinutes"),
        "occupancy": row.get("Occupancy"),
        "concurrency": row.get("Concurrency"),
        "shrinkage": row.get("Shrinkage"),
        "fte_per_head": row.get("FTEPerHead"),
    }
    if method == "ERLANG_C":
        common.update(
            {
                "target_service_level": row.get("TargetServiceLevel"),
                "answer_time_seconds": row.get("AnswerTimeSeconds"),
            }
        )
    return calculate_capacity(method, **common)
