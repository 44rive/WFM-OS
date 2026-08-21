"""Deterministic anonymous shift-pattern fitting for WFM OS.

The dependency-free core fits governed pattern counts to complete 30-minute
requirement horizons. It never assigns named agents and never claims global
optimality; the documented greedy objective and tie-breaks are stable.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
import re
from typing import Iterable, Mapping


ScheduleRecord = Mapping[str, object]
SCHED_INTERVAL_KEYS = tuple(f"I{index:02d}" for index in range(48))
SCHED_WEEKDAYS = (
    "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"
)
SCHED_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SCHED_RULE_TYPES = {"MIN_PATTERN_COUNT", "MAX_PATTERN_COUNT", "PREFERENCE_COST"}


def _sched_date(value: object, field: str) -> date:
    if isinstance(value, datetime):
        raise ValueError(f"{field} must be a date, not a datetime")
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not SCHED_DATE.fullmatch(value):
        raise ValueError(f"{field} must use strict YYYY-MM-DD format")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid date") from exc


def _sched_datetime(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO datetime") from exc
    else:
        raise ValueError(f"{field} must be an ISO datetime")
    if result.tzinfo is not None:
        raise ValueError(f"{field} must be normalized to a timezone-naive local datetime")
    if result.minute not in {0, 30} or result.second != 0 or result.microsecond != 0:
        raise ValueError(f"{field} must align to an exact 30-minute boundary")
    return result


def _sched_decimal(
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


def _sched_integer(value: object, field: str, *, minimum: int = 0) -> int:
    number = _sched_decimal(value, field)
    if number != number.to_integral_value() or number < minimum:
        raise ValueError(f"{field} must be an integer at least {minimum}")
    return int(number)


def _sched_text(row: ScheduleRecord, field: str) -> str:
    if field not in row:
        raise ValueError(f"Missing field: {field}")
    value = str(row[field]).strip()
    if not value:
        raise ValueError(f"{field} cannot be blank")
    return value


def _sched_approved(value: object, field: str = "ApprovedFlag") -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().upper() in {"TRUE", "FALSE"}:
        return value.strip().upper() == "TRUE"
    raise ValueError(f"{field} must be TRUE or FALSE")


def _sched_active(row: ScheduleRecord, on_date: date) -> bool:
    valid_from = _sched_date(row.get("ValidFrom"), "ValidFrom")
    valid_to_value = row.get("ValidTo")
    valid_to = (
        _sched_date(valid_to_value, "ValidTo")
        if valid_to_value is not None and str(valid_to_value).strip()
        else date.max
    )
    if valid_to < valid_from:
        raise ValueError("ValidTo cannot precede ValidFrom")
    return valid_from <= on_date <= valid_to


def _prepare_schedule_requirements(
    rows: Iterable[ScheduleRecord],
) -> tuple[dict[tuple[str, datetime, str], dict[str, object]], dict[tuple[str, str], list[date]]]:
    requirements: dict[tuple[str, datetime, str], dict[str, object]] = {}
    group_intervals: dict[tuple[str, str, date], set[str]] = defaultdict(set)
    group_dates: dict[tuple[str, str], set[date]] = defaultdict(set)
    for row in rows:
        scenario = _sched_text(row, "ScenarioKey").upper()
        activity = _sched_text(row, "ActivityKey")
        interval_start = _sched_datetime(row.get("IntervalStart"), "IntervalStart")
        interval_key = str(row.get("IntervalKey") or f"I{interval_start.hour * 2 + interval_start.minute // 30:02d}").upper()
        expected_key = f"I{interval_start.hour * 2 + interval_start.minute // 30:02d}"
        if interval_key not in SCHED_INTERVAL_KEYS or interval_key != expected_key:
            raise ValueError("IntervalKey must match IntervalStart")
        grain = (scenario, interval_start, activity)
        if grain in requirements:
            raise ValueError(f"Duplicate schedule requirement grain: {grain}")
        required = _sched_decimal(row.get("RequiredFTE"), "RequiredFTE", minimum=Decimal(0))
        requirements[grain] = {
            "ScenarioKey": scenario,
            "BusinessDate": interval_start.date(),
            "IntervalStart": interval_start,
            "IntervalKey": interval_key,
            "ActivityKey": activity,
            "RequiredFTE": required,
            "RequirementVersion": str(row.get("RequirementVersion") or "").strip(),
        }
        group_intervals[(scenario, activity, interval_start.date())].add(interval_key)
        group_dates[(scenario, activity)].add(interval_start.date())
    if not requirements:
        raise ValueError("Approved interval requirements cannot be empty")
    expected = set(SCHED_INTERVAL_KEYS)
    for grain, intervals in group_intervals.items():
        if intervals != expected:
            missing = sorted(expected - intervals)
            raise ValueError(
                f"Schedule requirement day {grain} must contain all 48 intervals; missing {missing[0] if missing else 'duplicate'}"
            )
    ordered_dates: dict[tuple[str, str], list[date]] = {}
    for grain, dates in group_dates.items():
        ordered = sorted(dates)
        for prior, current in zip(ordered, ordered[1:]):
            if current - prior != timedelta(days=1):
                raise ValueError(f"Schedule requirement dates for {grain} must be contiguous")
        ordered_dates[grain] = ordered
    return requirements, ordered_dates


def _prepare_patterns(
    rows: Iterable[ScheduleRecord],
) -> dict[tuple[str, str, str], dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[ScheduleRecord]] = defaultdict(list)
    segment_keys: set[tuple[str, str, str, str]] = set()
    for row in rows:
        if not _sched_approved(row.get("ApprovedFlag")):
            continue
        version = _sched_text(row, "PatternVersionKey")
        pattern = _sched_text(row, "PatternKey")
        day_type = _sched_text(row, "DayType").upper()
        if day_type not in {"ALL", *SCHED_WEEKDAYS}:
            raise ValueError(f"Invalid DayType: {day_type}")
        segment = _sched_text(row, "SegmentKey")
        segment_grain = (version, pattern, day_type, segment)
        if segment_grain in segment_keys:
            raise ValueError(f"Duplicate shift-pattern segment: {segment_grain}")
        segment_keys.add(segment_grain)
        grouped[(version, pattern, day_type)].append(row)
    if not grouped:
        raise ValueError("At least one approved shift-pattern segment is required")

    definitions: dict[tuple[str, str, str], dict[str, object]] = {}
    for grain, source_rows in grouped.items():
        version, pattern, day_type = grain
        activity_values = {_sched_text(row, "ActivityKey") for row in source_rows}
        name_values = {_sched_text(row, "PatternName") for row in source_rows}
        valid_from_values = {_sched_date(row.get("ValidFrom"), "ValidFrom") for row in source_rows}
        valid_to_values = {
            _sched_date(row.get("ValidTo"), "ValidTo")
            if row.get("ValidTo") is not None and str(row.get("ValidTo")).strip()
            else date.max
            for row in source_rows
        }
        if any(len(values) != 1 for values in (activity_values, name_values, valid_from_values, valid_to_values)):
            raise ValueError(f"Pattern metadata must be consistent for {grain}")
        valid_from = next(iter(valid_from_values))
        valid_to = next(iter(valid_to_values))
        if valid_to < valid_from:
            raise ValueError(f"Pattern {grain} ValidTo precedes ValidFrom")
        segments: list[dict[str, object]] = []
        for row in source_rows:
            start = _sched_integer(row.get("StartMinute"), "StartMinute")
            end = _sched_integer(row.get("EndMinute"), "EndMinute", minimum=1)
            if start >= end or end > 2880 or start % 30 or end % 30:
                raise ValueError("Pattern segments must be half-open 30-minute offsets inside 0..2880")
            paid = _sched_approved(row.get("PaidFlag"), "PaidFlag")
            productive = _sched_approved(row.get("ProductiveFlag"), "ProductiveFlag")
            if productive and not paid:
                raise ValueError("A productive shift segment must also be paid")
            segments.append(
                {
                    "SegmentKey": _sched_text(row, "SegmentKey"),
                    "StartMinute": start,
                    "EndMinute": end,
                    "ScheduleTypeKey": _sched_text(row, "ScheduleTypeKey"),
                    "PaidFlag": paid,
                    "ProductiveFlag": productive,
                }
            )
        segments.sort(key=lambda item: (item["StartMinute"], item["EndMinute"], item["SegmentKey"]))
        for prior, current in zip(segments, segments[1:]):
            if current["StartMinute"] < prior["EndMinute"]:
                raise ValueError(f"Pattern segments overlap for {grain}")
        if not any(segment["PaidFlag"] for segment in segments):
            raise ValueError(f"Pattern {grain} must contain paid time")
        if not any(segment["ProductiveFlag"] for segment in segments):
            raise ValueError(f"Pattern {grain} must contain productive time")
        definitions[grain] = {
            "PatternVersionKey": version,
            "PatternKey": pattern,
            "PatternName": next(iter(name_values)),
            "ActivityKey": next(iter(activity_values)),
            "DayType": day_type,
            "ValidFrom": valid_from,
            "ValidTo": valid_to,
            "Segments": segments,
            "PaidHoursPerPattern": sum(
                (Decimal(segment["EndMinute"] - segment["StartMinute"]) / 60)
                for segment in segments if segment["PaidFlag"]
            ),
            "ProductiveHoursPerPattern": sum(
                (Decimal(segment["EndMinute"] - segment["StartMinute"]) / 60)
                for segment in segments if segment["ProductiveFlag"]
            ),
        }
    return definitions


def _prepare_rules(rows: Iterable[ScheduleRecord]) -> dict[tuple[str, str, str], list[dict[str, object]]]:
    rules: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    keys: set[str] = set()
    for row in rows:
        if not _sched_approved(row.get("ApprovedFlag")):
            continue
        rule_key = _sched_text(row, "RuleKey")
        if rule_key in keys:
            raise ValueError(f"Duplicate approved RuleKey: {rule_key}")
        keys.add(rule_key)
        rule_type = _sched_text(row, "RuleType").upper()
        if rule_type not in SCHED_RULE_TYPES:
            raise ValueError(f"Unsupported shift RuleType: {rule_type}")
        activity = _sched_text(row, "ActivityKey")
        pattern = _sched_text(row, "PatternKey")
        valid_from = _sched_date(row.get("ValidFrom"), "ValidFrom")
        valid_to_value = row.get("ValidTo")
        valid_to = (
            _sched_date(valid_to_value, "ValidTo")
            if valid_to_value is not None and str(valid_to_value).strip()
            else date.max
        )
        if valid_to < valid_from:
            raise ValueError(f"Rule {rule_key} ValidTo precedes ValidFrom")
        rules[(activity, pattern, rule_type)].append(
            {
                "RuleKey": rule_key,
                "ValidFrom": valid_from,
                "ValidTo": valid_to,
                "Value": _sched_decimal(row.get("Value"), "Value", minimum=Decimal(0)),
            }
        )
    if not rules:
        raise ValueError("At least one approved shift rule is required")
    for grain, grain_rows in rules.items():
        ordered = sorted(grain_rows, key=lambda item: (item["ValidFrom"], item["ValidTo"], item["RuleKey"]))
        for prior, current in zip(ordered, ordered[1:]):
            if current["ValidFrom"] <= prior["ValidTo"]:
                raise ValueError(f"Approved shift rules overlap for {grain}")
        rules[grain] = ordered
    return rules


def _patterns_for_date(
    definitions: dict[tuple[str, str, str], dict[str, object]], activity: str, business_date: date
) -> list[dict[str, object]]:
    weekday = SCHED_WEEKDAYS[business_date.weekday()]
    by_pattern: dict[str, list[dict[str, object]]] = defaultdict(list)
    for definition in definitions.values():
        if definition["ActivityKey"] != activity:
            continue
        if not definition["ValidFrom"] <= business_date <= definition["ValidTo"]:
            continue
        if definition["DayType"] in {"ALL", weekday}:
            by_pattern[str(definition["PatternKey"])].append(definition)
    selected: list[dict[str, object]] = []
    for pattern, candidates in sorted(by_pattern.items()):
        exact = [row for row in candidates if row["DayType"] == weekday]
        matches = exact if exact else [row for row in candidates if row["DayType"] == "ALL"]
        if len(matches) != 1:
            raise ValueError(f"Exactly one effective pattern version is required for {activity}/{pattern}/{business_date}")
        selected.append(matches[0])
    return selected


def _rule_value(
    rules: dict[tuple[str, str, str], list[dict[str, object]]],
    activity: str,
    pattern: str,
    rule_type: str,
    business_date: date,
) -> Decimal:
    matches = [
        row for row in rules.get((activity, pattern, rule_type), [])
        if row["ValidFrom"] <= business_date <= row["ValidTo"]
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Exactly one effective {rule_type} rule is required for {activity}/{pattern}/{business_date}"
        )
    return matches[0]["Value"]


def _pattern_contributions(
    definition: dict[str, object], business_date: date
) -> tuple[dict[datetime, Decimal], dict[datetime, Decimal]]:
    productive: dict[datetime, Decimal] = {}
    paid: dict[datetime, Decimal] = {}
    midnight = datetime.combine(business_date, time())
    for segment in definition["Segments"]:
        for offset in range(segment["StartMinute"], segment["EndMinute"], 30):
            interval_start = midnight + timedelta(minutes=offset)
            if segment["PaidFlag"]:
                paid[interval_start] = Decimal(1)
            if segment["ProductiveFlag"]:
                productive[interval_start] = Decimal(1)
    return productive, paid


def expand_schedule_plan(
    plan_rows: Iterable[ScheduleRecord], pattern_rows: Iterable[ScheduleRecord]
) -> list[dict[str, object]]:
    """Expand pattern-count rows to grouped paid/productive interval coverage."""
    definitions = _prepare_patterns(pattern_rows)
    grouped: dict[tuple[str, datetime, str], dict[str, object]] = {}
    for row in plan_rows:
        scenario = _sched_text(row, "ScenarioKey").upper()
        activity = _sched_text(row, "ActivityKey")
        business_date = _sched_date(row.get("BusinessDate"), "BusinessDate")
        version = _sched_text(row, "PatternVersionKey")
        pattern = _sched_text(row, "PatternKey")
        count = _sched_integer(row.get("PatternCount"), "PatternCount", minimum=1)
        matching = [
            definition for definition in _patterns_for_date(definitions, activity, business_date)
            if definition["PatternVersionKey"] == version and definition["PatternKey"] == pattern
        ]
        if len(matching) != 1:
            raise ValueError(f"Approved pattern cannot be resolved for {version}/{pattern}/{business_date}")
        productive, paid = _pattern_contributions(matching[0], business_date)
        for interval_start in sorted(set(productive) | set(paid)):
            grain = (scenario, interval_start, activity)
            target = grouped.setdefault(
                grain,
                {
                    "ScenarioKey": scenario,
                    "BusinessDate": interval_start.date().isoformat(),
                    "IntervalStart": interval_start.isoformat(),
                    "IntervalKey": f"I{interval_start.hour * 2 + interval_start.minute // 30:02d}",
                    "ActivityKey": activity,
                    "ScheduledPaidFTE": Decimal(0),
                    "ScheduledProductiveFTE": Decimal(0),
                },
            )
            target["ScheduledPaidFTE"] += Decimal(count) * paid.get(interval_start, Decimal(0))
            target["ScheduledProductiveFTE"] += Decimal(count) * productive.get(interval_start, Decimal(0))
    return [grouped[key] for key in sorted(grouped)]


def expand_pattern_occurrences(
    plan_rows: Iterable[ScheduleRecord], pattern_rows: Iterable[ScheduleRecord]
) -> list[dict[str, object]]:
    """Expand approved pattern counts into stable unit occurrences with segments."""
    definitions = _prepare_patterns(pattern_rows)
    output: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in plan_rows:
        schedule_version = _sched_text(row, "SchedulePlanVersionKey")
        scenario = _sched_text(row, "ScenarioKey").upper()
        business_date = _sched_date(row.get("BusinessDate"), "BusinessDate")
        activity = _sched_text(row, "ActivityKey")
        version = _sched_text(row, "PatternVersionKey")
        pattern = _sched_text(row, "PatternKey")
        count = _sched_integer(row.get("PatternCount"), "PatternCount", minimum=1)
        matching = [
            definition for definition in _patterns_for_date(definitions, activity, business_date)
            if definition["PatternVersionKey"] == version and definition["PatternKey"] == pattern
        ]
        if len(matching) != 1:
            raise ValueError(f"Approved pattern cannot be resolved for {version}/{pattern}/{business_date}")
        definition = matching[0]
        midnight = datetime.combine(business_date, time())
        segments = [
            {
                **segment,
                "SegmentStart": midnight + timedelta(minutes=segment["StartMinute"]),
                "SegmentEnd": midnight + timedelta(minutes=segment["EndMinute"]),
            }
            for segment in definition["Segments"]
        ]
        paid_segments = [segment for segment in segments if segment["PaidFlag"]]
        productive_segments = [segment for segment in segments if segment["ProductiveFlag"]]
        for ordinal in range(1, count + 1):
            occurrence_key = "|".join(
                (
                    schedule_version,
                    scenario,
                    business_date.isoformat(),
                    activity,
                    version,
                    pattern,
                    f"{ordinal:04d}",
                )
            )
            if occurrence_key in seen:
                raise ValueError(f"Duplicate schedule occurrence key: {occurrence_key}")
            seen.add(occurrence_key)
            output.append(
                {
                    "OccurrenceKey": occurrence_key,
                    "SchedulePlanVersionKey": schedule_version,
                    "ScenarioKey": scenario,
                    "BusinessDate": business_date,
                    "ActivityKey": activity,
                    "PatternVersionKey": version,
                    "PatternKey": pattern,
                    "PatternName": definition["PatternName"],
                    "OccurrenceOrdinal": ordinal,
                    "PaidStart": min(segment["SegmentStart"] for segment in paid_segments),
                    "PaidEnd": max(segment["SegmentEnd"] for segment in paid_segments),
                    "PaidHours": definition["PaidHoursPerPattern"],
                    "ProductiveHours": definition["ProductiveHoursPerPattern"],
                    "Segments": segments,
                    "ProductiveSegments": productive_segments,
                }
            )
    return sorted(output, key=lambda row: (row["PaidStart"], row["OccurrenceKey"]))


def fit_shift_patterns(
    requirement_rows: Iterable[ScheduleRecord],
    pattern_rows: Iterable[ScheduleRecord],
    rule_rows: Iterable[ScheduleRecord],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Fit anonymous pattern counts with the documented deterministic heuristic."""
    requirements, group_dates = _prepare_schedule_requirements(requirement_rows)
    definitions = _prepare_patterns(pattern_rows)
    rules = _prepare_rules(rule_rows)
    plan_output: list[dict[str, object]] = []
    coverage_output: list[dict[str, object]] = []

    for (scenario, activity), dates in sorted(group_dates.items()):
        group_keys = sorted(
            key for key in requirements if key[0] == scenario and key[2] == activity
        )
        productive_coverage = {key: Decimal(0) for key in group_keys}
        paid_coverage = {key: Decimal(0) for key in group_keys}
        occurrences: list[dict[str, object]] = []
        occurrence_dates = [dates[0] - timedelta(days=1), *dates]
        for business_date in occurrence_dates:
            for definition in _patterns_for_date(definitions, activity, business_date):
                productive_all, paid_all = _pattern_contributions(definition, business_date)
                productive = {
                    key: value for key, value in (
                        ((scenario, interval_start, activity), contribution)
                        for interval_start, contribution in productive_all.items()
                    ) if key in requirements
                }
                paid = {
                    key: value for key, value in (
                        ((scenario, interval_start, activity), contribution)
                        for interval_start, contribution in paid_all.items()
                    ) if key in requirements
                }
                if not productive:
                    continue
                minimum = _rule_value(rules, activity, definition["PatternKey"], "MIN_PATTERN_COUNT", business_date)
                maximum = _rule_value(rules, activity, definition["PatternKey"], "MAX_PATTERN_COUNT", business_date)
                preference = _rule_value(rules, activity, definition["PatternKey"], "PREFERENCE_COST", business_date)
                if minimum != minimum.to_integral_value() or maximum != maximum.to_integral_value():
                    raise ValueError("MIN_PATTERN_COUNT and MAX_PATTERN_COUNT must be integers")
                minimum_count, maximum_count = int(minimum), int(maximum)
                if maximum_count < minimum_count:
                    raise ValueError("MAX_PATTERN_COUNT cannot be below MIN_PATTERN_COUNT")
                occurrence = {
                    "ScenarioKey": scenario,
                    "BusinessDate": business_date,
                    "ActivityKey": activity,
                    "PatternVersionKey": definition["PatternVersionKey"],
                    "PatternKey": definition["PatternKey"],
                    "PatternName": definition["PatternName"],
                    "PatternCount": minimum_count,
                    "MaximumCount": maximum_count,
                    "PreferenceCost": preference,
                    "PaidHoursPerPattern": definition["PaidHoursPerPattern"],
                    "ProductiveHoursPerPattern": definition["ProductiveHoursPerPattern"],
                    "Productive": productive,
                    "Paid": paid,
                }
                occurrences.append(occurrence)
                for key, contribution in productive.items():
                    productive_coverage[key] += Decimal(minimum_count) * contribution
                for key, contribution in paid.items():
                    paid_coverage[key] += Decimal(minimum_count) * contribution

        if not occurrences:
            raise ValueError(f"No effective approved shift pattern covers {scenario}/{activity}")
        remaining_units = sum(item["MaximumCount"] - item["PatternCount"] for item in occurrences)
        if remaining_units > 1_000_000:
            raise ValueError("Shift rule capacity is too large for deterministic fitting")
        for _ in range(remaining_units):
            choices: list[tuple[tuple[object, ...], dict[str, object]]] = []
            for occurrence in occurrences:
                if occurrence["PatternCount"] >= occurrence["MaximumCount"]:
                    continue
                gain = Decimal(0)
                overage = Decimal(0)
                for key, contribution in occurrence["Productive"].items():
                    required = requirements[key]["RequiredFTE"]
                    current = productive_coverage[key]
                    deficit = max(Decimal(0), required - current)
                    gain += min(deficit, contribution)
                    overage += max(Decimal(0), current + contribution - required) - max(
                        Decimal(0), current - required
                    )
                if gain <= 0:
                    continue
                score = (
                    -gain,
                    overage,
                    occurrence["PaidHoursPerPattern"] * occurrence["PreferenceCost"],
                    occurrence["BusinessDate"],
                    occurrence["PatternVersionKey"],
                    occurrence["PatternKey"],
                )
                choices.append((score, occurrence))
            if not choices:
                break
            _, selected = min(choices, key=lambda item: item[0])
            selected["PatternCount"] += 1
            for key, contribution in selected["Productive"].items():
                productive_coverage[key] += contribution
            for key, contribution in selected["Paid"].items():
                paid_coverage[key] += contribution
            if all(productive_coverage[key] >= requirements[key]["RequiredFTE"] for key in group_keys):
                break

        uncovered_total = sum(
            (max(Decimal(0), requirements[key]["RequiredFTE"] - productive_coverage[key]) for key in group_keys),
            Decimal(0),
        )
        over_total = sum(
            (max(Decimal(0), productive_coverage[key] - requirements[key]["RequiredFTE"]) for key in group_keys),
            Decimal(0),
        )
        status = "COMPLETE" if uncovered_total == 0 else "UNCOVERED"
        for occurrence in sorted(
            occurrences,
            key=lambda item: (item["BusinessDate"], item["PatternVersionKey"], item["PatternKey"]),
        ):
            if occurrence["PatternCount"] <= 0:
                continue
            plan_output.append(
                {
                    "ScheduleCandidateKey": "|".join(
                        (
                            scenario,
                            activity,
                            occurrence["BusinessDate"].isoformat(),
                            occurrence["PatternVersionKey"],
                            occurrence["PatternKey"],
                        )
                    ),
                    "ScenarioKey": scenario,
                    "BusinessDate": occurrence["BusinessDate"].isoformat(),
                    "ActivityKey": activity,
                    "PatternVersionKey": occurrence["PatternVersionKey"],
                    "PatternKey": occurrence["PatternKey"],
                    "PatternName": occurrence["PatternName"],
                    "PatternCount": occurrence["PatternCount"],
                    "PaidHours": Decimal(occurrence["PatternCount"]) * occurrence["PaidHoursPerPattern"],
                    "ProductiveHours": Decimal(occurrence["PatternCount"]) * occurrence["ProductiveHoursPerPattern"],
                    "CoverageMethod": "GREEDY_DEFICIT_V1",
                    "CoverageStatus": status,
                    "UncoveredFTEIntervals": uncovered_total,
                    "OvercoveredFTEIntervals": over_total,
                }
            )
        for key in group_keys:
            requirement = requirements[key]
            required = requirement["RequiredFTE"]
            productive = productive_coverage[key]
            paid = paid_coverage[key]
            coverage_output.append(
                {
                    "ScenarioKey": scenario,
                    "BusinessDate": requirement["BusinessDate"].isoformat(),
                    "IntervalStart": requirement["IntervalStart"].isoformat(),
                    "IntervalKey": requirement["IntervalKey"],
                    "ActivityKey": activity,
                    "RequirementVersion": requirement["RequirementVersion"],
                    "RequiredFTE": required,
                    "ScheduledPaidFTE": paid,
                    "ScheduledProductiveFTE": productive,
                    "GapFTE": max(Decimal(0), required - productive),
                    "OverFTE": max(Decimal(0), productive - required),
                    "CoverageStatus": "COVERED" if productive >= required else "UNCOVERED",
                    "CoverageMethod": "GREEDY_DEFICIT_V1",
                }
            )
    return plan_output, coverage_output
