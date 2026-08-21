from __future__ import annotations

import csv
import unittest
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence


TEST_ROOT = Path(__file__).resolve().parent
INPUT_ROOT = TEST_ROOT / "anonymized-input"
EXPECTED_ROOT = TEST_ROOT / "expected-output"
INTERVAL = timedelta(minutes=30)
RATE_PLACES = 6


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def input_rows(name: str) -> list[dict[str, str]]:
    return read_csv(INPUT_ROOT / name)


def expected_rows(name: str) -> list[dict[str, str]]:
    return read_csv(EXPECTED_ROOT / name)


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.removesuffix("Z"))


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def as_bool(value: str) -> bool:
    normalized = value.strip().upper()
    if normalized not in {"TRUE", "FALSE"}:
        raise ValueError(f"Expected TRUE or FALSE, received {value!r}")
    return normalized == "TRUE"


def overlap_seconds(start: datetime, end: datetime, window_start: datetime, window_end: datetime) -> int:
    overlap_start = max(start, window_start)
    overlap_end = min(end, window_end)
    return max(0, int((overlap_end - overlap_start).total_seconds()))


def merged_overlap_seconds(
    intervals: Iterable[tuple[datetime, datetime]],
    window_start: datetime,
    window_end: datetime,
) -> int:
    clipped = sorted(
        (max(start, window_start), min(end, window_end))
        for start, end in intervals
        if overlap_seconds(start, end, window_start, window_end) > 0
    )
    if not clipped:
        return 0
    merged: list[list[datetime]] = []
    for start, end in clipped:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return sum(int((end - start).total_seconds()) for start, end in merged)


class IdentityResolver:
    """Minimal effective-dated reference behavior for anonymized fixtures."""

    def __init__(self, identities: Sequence[dict[str, str]]) -> None:
        self.identities = identities

    def resolve(self, system_key: str, external_identity: str, as_of: date) -> tuple[str, str]:
        matches = []
        for identity in self.identities:
            if identity["SystemKey"] != system_key or identity["ExternalAgentID"] != external_identity:
                continue
            valid_from = parse_date(identity["ValidFrom"])
            valid_to = parse_date(identity["ValidTo"]) if identity["ValidTo"] else date.max
            if valid_from <= as_of <= valid_to:
                matches.append(identity)
        if not matches:
            return "", "UNKNOWN_IDENTITY"
        if len(matches) > 1:
            return "", "AMBIGUOUS_IDENTITY"
        return matches[0]["AgentKey"], "RESOLVED"


def resolve_rows(
    rows: Sequence[dict[str, str]],
    resolver: IdentityResolver,
    *,
    entity: str,
    key_field: str,
    identity_field: str,
    timestamp_field: str,
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    accepted: list[dict[str, object]] = []
    quarantined: list[dict[str, str]] = []
    for row in rows:
        observed = parse_datetime(row[timestamp_field])
        agent_key, status = resolver.resolve(
            row["source_system"], row[identity_field], observed.date()
        )
        if status != "RESOLVED":
            quarantined.append(
                {
                    "entity": entity,
                    "source_key": row[key_field],
                    "source_system": row["source_system"],
                    "external_identity": row[identity_field],
                    "observed_at": row[timestamp_field],
                    "reason": status,
                }
            )
            continue
        enriched: dict[str, object] = dict(row)
        enriched["AgentKey"] = agent_key
        accepted.append(enriched)
    return accepted, quarantined


def load_resolved_fixtures() -> tuple[
    IdentityResolver,
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    resolver = IdentityResolver(input_rows("identity_mapping.csv"))
    schedules, schedule_quarantine = resolve_rows(
        input_rows("schedules.csv"),
        resolver,
        entity="ScheduleSegment",
        key_field="schedule_segment_id",
        identity_field="operational_id",
        timestamp_field="scheduled_start",
    )
    logins, login_quarantine = resolve_rows(
        input_rows("login_sessions.csv"),
        resolver,
        entity="LoginSession",
        key_field="login_session_id",
        identity_field="operational_id",
        timestamp_field="login_at",
    )
    events, event_quarantine = resolve_rows(
        input_rows("agent_events.csv"),
        resolver,
        entity="AgentEvent",
        key_field="agent_event_id",
        identity_field="operational_id",
        timestamp_field="event_start",
    )
    if schedule_quarantine or login_quarantine or event_quarantine:
        raise AssertionError("Known fixtures unexpectedly produced identity quarantine rows")

    state_map = {
        (row["source_system"], row["source_state"]): row
        for row in input_rows("state_mapping.csv")
    }
    for event in events:
        mapping = state_map.get((str(event["source_system"]), str(event["source_state"])))
        if mapping is None:
            raise AssertionError(f"Unmapped fixture state: {event['source_state']}")
        event["CanonicalState"] = mapping["canonical_state"]
        event["ProductiveFlag"] = as_bool(mapping["productive_flag"])
    return resolver, schedules, logins, events


def schedule_intersects(row: dict[str, object], start: datetime, end: datetime) -> bool:
    return overlap_seconds(
        parse_datetime(str(row["scheduled_start"])),
        parse_datetime(str(row["scheduled_end"])),
        start,
        end,
    ) > 0


def interval_staffing(
    schedules: Sequence[dict[str, object]],
    logins: Sequence[dict[str, object]],
    events: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for requirement in input_rows("staffing_requirements.csv"):
        start = parse_datetime(requirement["interval_start"])
        end = start + INTERVAL
        activity = requirement["activity_key"]
        interval_schedules = [
            row for row in schedules
            if row["activity_key"] == activity
            and as_bool(str(row["paid_flag"]))
            and schedule_intersects(row, start, end)
        ]
        scheduled_agents = {str(row["AgentKey"]) for row in interval_schedules}
        scheduled_productive_agents = {
            str(row["AgentKey"])
            for row in interval_schedules
            if as_bool(str(row["productive_flag"]))
        }
        present_agents = {
            str(row["AgentKey"])
            for row in logins
            if str(row["AgentKey"]) in scheduled_agents
            and overlap_seconds(
                parse_datetime(str(row["login_at"])),
                parse_datetime(str(row["logout_at"])),
                start,
                end,
            ) > 0
        }
        productive_agents = {
            str(row["AgentKey"])
            for row in events
            if bool(row["ProductiveFlag"])
            and str(row["AgentKey"]) in scheduled_productive_agents
            and overlap_seconds(
                parse_datetime(str(row["event_start"])),
                parse_datetime(str(row["event_end"])),
                start,
                end,
            ) > 0
        }
        required = int(requirement["required_fte"])
        output.append(
            {
                "business_date": requirement["business_date"],
                "interval_start": requirement["interval_start"],
                "activity_key": activity,
                "scheduled_heads": len(scheduled_agents),
                "scheduled_productive_heads": len(scheduled_productive_agents),
                "present_heads": len(present_agents),
                "productive_heads": len(productive_agents),
                "required_fte": required,
                "net_productive_heads": len(productive_agents) - required,
            }
        )
    return output


def sessions_for_agent(logins: Sequence[dict[str, object]], agent_key: str) -> list[tuple[datetime, datetime]]:
    return [
        (parse_datetime(str(row["login_at"])), parse_datetime(str(row["logout_at"])))
        for row in logins
        if row["AgentKey"] == agent_key
    ]


def daily_attendance(
    schedules: Sequence[dict[str, object]],
    logins: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in schedules:
        if not as_bool(str(row["paid_flag"])):
            continue
        business_date = parse_datetime(str(row["scheduled_start"])).date().isoformat()
        grouped[(business_date, str(row["AgentKey"]))].append(row)

    output: list[dict[str, object]] = []
    for (business_date, agent_key), segments in sorted(grouped.items()):
        schedule_start = min(parse_datetime(str(row["scheduled_start"])) for row in segments)
        schedule_end = max(parse_datetime(str(row["scheduled_end"])) for row in segments)
        scheduled_seconds = sum(
            int((parse_datetime(str(row["scheduled_end"])) - parse_datetime(str(row["scheduled_start"]))).total_seconds())
            for row in segments
        )
        sessions = sessions_for_agent(logins, agent_key)
        present_seconds = sum(
            merged_overlap_seconds(sessions, parse_datetime(str(row["scheduled_start"])), parse_datetime(str(row["scheduled_end"])))
            for row in segments
        )
        if sessions:
            first_login = min(start for start, _ in sessions)
            last_logout = max(end for _, end in sessions)
            late_seconds = max(0, int((first_login - schedule_start).total_seconds()))
            early_seconds = max(0, int((schedule_end - last_logout).total_seconds()))
        else:
            late_seconds = scheduled_seconds
            early_seconds = 0
        rate = present_seconds / scheduled_seconds if scheduled_seconds else 0.0
        outcome = "ABSENT" if present_seconds == 0 else "PRESENT" if present_seconds == scheduled_seconds else "PARTIAL"
        output.append(
            {
                "business_date": business_date,
                "agent_key": agent_key,
                "scheduled_minutes": scheduled_seconds // 60,
                "present_scheduled_minutes": present_seconds // 60,
                "late_minutes": late_seconds // 60,
                "early_leave_minutes": early_seconds // 60,
                "attendance_rate": rate,
                "outcome": outcome,
            }
        )
    return output


def event_is_adherent(schedule: dict[str, object], event: dict[str, object]) -> bool:
    if as_bool(str(schedule["productive_flag"])):
        return bool(event["ProductiveFlag"])
    return str(schedule["schedule_type"]).casefold() == str(event["CanonicalState"]).casefold()


def adherence_for_windows(
    schedules: Sequence[dict[str, object]],
    logins: Sequence[dict[str, object]],
    events: Sequence[dict[str, object]],
    windows: Sequence[tuple[str, str, str, datetime, datetime]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for business_date, grain_key, activity, start, end in windows:
        matching = [
            row for row in schedules
            if row["activity_key"] == activity
            and as_bool(str(row["paid_flag"]))
            and schedule_intersects(row, start, end)
        ]
        scheduled_seconds = 0
        logged_seconds = 0
        adherent_seconds = 0
        for schedule in matching:
            segment_start = max(start, parse_datetime(str(schedule["scheduled_start"])))
            segment_end = min(end, parse_datetime(str(schedule["scheduled_end"])))
            segment_seconds = max(0, int((segment_end - segment_start).total_seconds()))
            scheduled_seconds += segment_seconds
            agent_key = str(schedule["AgentKey"])
            logged_seconds += merged_overlap_seconds(sessions_for_agent(logins, agent_key), segment_start, segment_end)
            adherent_seconds += sum(
                overlap_seconds(
                    parse_datetime(str(event["event_start"])),
                    parse_datetime(str(event["event_end"])),
                    segment_start,
                    segment_end,
                )
                for event in events
                if event["AgentKey"] == agent_key and event_is_adherent(schedule, event)
            )
        row: dict[str, object] = {
            "business_date": business_date,
            "activity_key": activity,
            "scheduled_seconds": scheduled_seconds,
            "logged_seconds": logged_seconds,
            "adherent_seconds": adherent_seconds,
            "exception_seconds": scheduled_seconds - adherent_seconds,
            "conformance_rate": logged_seconds / scheduled_seconds if scheduled_seconds else 0.0,
            "adherence_rate": adherent_seconds / scheduled_seconds if scheduled_seconds else 0.0,
        }
        if grain_key:
            row["interval_start"] = grain_key
        output.append(row)
    return output


def interval_adherence(
    schedules: Sequence[dict[str, object]],
    logins: Sequence[dict[str, object]],
    events: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    windows = []
    for requirement in input_rows("staffing_requirements.csv"):
        start = parse_datetime(requirement["interval_start"])
        windows.append((requirement["business_date"], requirement["interval_start"], requirement["activity_key"], start, start + INTERVAL))
    return adherence_for_windows(schedules, logins, events, windows)


def daily_adherence(
    schedules: Sequence[dict[str, object]],
    logins: Sequence[dict[str, object]],
    events: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    business_date = "2026-01-16"
    day_start = datetime.fromisoformat(f"{business_date}T00:00:00")
    day_end = day_start + timedelta(days=1)
    agent_keys = sorted({str(row["AgentKey"]) for row in schedules})
    totals = defaultdict(int)
    for agent_key in agent_keys:
        agent_schedules = [row for row in schedules if row["AgentKey"] == agent_key]
        row = adherence_for_windows(
            agent_schedules,
            logins,
            events,
            [(business_date, "", "ACT_SUPPORT", day_start, day_end)],
        )[0]
        row["agent_key"] = agent_key
        output.append(row)
        for field in ("scheduled_seconds", "logged_seconds", "adherent_seconds", "exception_seconds"):
            totals[field] += int(row[field])
    output.append(
        {
            "business_date": business_date,
            "agent_key": "TOTAL",
            **totals,
            "conformance_rate": totals["logged_seconds"] / totals["scheduled_seconds"],
            "adherence_rate": totals["adherent_seconds"] / totals["scheduled_seconds"],
        }
    )
    return output


def close_day(
    existing_rows: Sequence[dict[str, str]],
    live_rows: Sequence[dict[str, object]],
    business_date: str,
    closed_at: str,
) -> list[dict[str, str]]:
    """Replace one business date by stable grain; running twice is identical."""
    output = [dict(row) for row in existing_rows if row["business_date"] != business_date]
    for live in live_rows:
        if live["business_date"] != business_date:
            continue
        output.append(
            {
                "business_date": str(live["business_date"]),
                "interval_start": str(live["interval_start"]),
                "activity_key": str(live["activity_key"]),
                "scheduled_heads": str(live["scheduled_heads"]),
                "scheduled_productive_heads": str(live["scheduled_productive_heads"]),
                "present_heads": str(live["present_heads"]),
                "productive_heads": str(live["productive_heads"]),
                "required_fte": str(live["required_fte"]),
                "net_productive_heads": str(live["net_productive_heads"]),
                "status": "FINAL",
                "closed_at": closed_at,
            }
        )
    return sorted(output, key=lambda row: (row["business_date"], row["interval_start"], row["activity_key"]))


class WorkforceCycleFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.resolver, cls.schedules, cls.logins, cls.events = load_resolved_fixtures()

    def assert_expected_rows(
        self,
        actual: Sequence[dict[str, object]],
        expected_file: str,
        *,
        key_fields: Sequence[str],
        integer_fields: Sequence[str] = (),
        rate_fields: Sequence[str] = (),
    ) -> None:
        expected = expected_rows(expected_file)
        key = lambda row: tuple(str(row[field]) for field in key_fields)
        actual_by_key = {key(row): row for row in actual}
        expected_by_key = {key(row): row for row in expected}
        self.assertEqual(set(actual_by_key), set(expected_by_key))
        for row_key, expected_row in expected_by_key.items():
            actual_row = actual_by_key[row_key]
            for field, expected_value in expected_row.items():
                if field in key_fields:
                    continue
                if field in integer_fields:
                    self.assertEqual(int(actual_row[field]), int(expected_value), (row_key, field))
                elif field in rate_fields:
                    self.assertAlmostEqual(float(actual_row[field]), float(expected_value), places=RATE_PLACES, msg=f"{row_key} {field}")
                else:
                    self.assertEqual(str(actual_row[field]), expected_value, (row_key, field))

    def test_people_identity_is_effective_dated(self) -> None:
        for expected in expected_rows("identity_resolution.csv"):
            agent_key, status = self.resolver.resolve(
                expected["system_key"],
                expected["external_identity"],
                parse_date(expected["as_of_date"]),
            )
            self.assertEqual(agent_key, expected["expected_agent_key"])
            self.assertEqual(status, expected["resolution_status"])

    def test_schedule_segments_resolve_and_preserve_grain(self) -> None:
        self.assertEqual(len(self.schedules), 4)
        self.assertEqual(len({row["schedule_segment_id"] for row in self.schedules}), 4)
        self.assertEqual({row["AgentKey"] for row in self.schedules}, {"AGENT_001", "AGENT_002", "AGENT_003"})
        paid_minutes = sum(
            int((parse_datetime(str(row["scheduled_end"])) - parse_datetime(str(row["scheduled_start"]))).total_seconds() / 60)
            for row in self.schedules if as_bool(str(row["paid_flag"]))
        )
        self.assertEqual(paid_minutes, 180)

    def test_login_sessions_resolve_and_are_positive(self) -> None:
        self.assertEqual(len(self.logins), 3)
        self.assertEqual(len({row["login_session_id"] for row in self.logins}), 3)
        self.assertTrue(all(parse_datetime(str(row["logout_at"])) > parse_datetime(str(row["login_at"])) for row in self.logins))

    def test_agent_events_resolve_map_and_do_not_overlap(self) -> None:
        self.assertEqual(len(self.events), 6)
        self.assertEqual({row["CanonicalState"] for row in self.events}, {"Available", "Handling", "Other", "Break"})
        grouped: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
        for row in self.events:
            grouped[str(row["AgentKey"])].append((parse_datetime(str(row["event_start"])), parse_datetime(str(row["event_end"]))))
        for intervals in grouped.values():
            ordered = sorted(intervals)
            self.assertTrue(all(left[1] <= right[0] for left, right in zip(ordered, ordered[1:])))

    def test_intraday_staffing_matches_interval_expectation(self) -> None:
        actual = interval_staffing(self.schedules, self.logins, self.events)
        self.assert_expected_rows(
            actual,
            "interval_staffing.csv",
            key_fields=("business_date", "interval_start", "activity_key"),
            integer_fields=("scheduled_heads", "scheduled_productive_heads", "present_heads", "productive_heads", "required_fte", "net_productive_heads"),
        )

    def test_attendance_matches_daily_expectation(self) -> None:
        actual = daily_attendance(self.schedules, self.logins)
        self.assert_expected_rows(
            actual,
            "daily_attendance.csv",
            key_fields=("business_date", "agent_key"),
            integer_fields=("scheduled_minutes", "present_scheduled_minutes", "late_minutes", "early_leave_minutes"),
            rate_fields=("attendance_rate",),
        )

    def test_interval_conformance_and_adherence(self) -> None:
        actual = interval_adherence(self.schedules, self.logins, self.events)
        self.assert_expected_rows(
            actual,
            "interval_adherence.csv",
            key_fields=("business_date", "interval_start", "activity_key"),
            integer_fields=("scheduled_seconds", "logged_seconds", "adherent_seconds", "exception_seconds"),
            rate_fields=("conformance_rate", "adherence_rate"),
        )

    def test_daily_conformance_and_adherence(self) -> None:
        actual = daily_adherence(self.schedules, self.logins, self.events)
        self.assert_expected_rows(
            actual,
            "daily_adherence.csv",
            key_fields=("business_date", "agent_key"),
            integer_fields=("scheduled_seconds", "logged_seconds", "adherent_seconds", "exception_seconds"),
            rate_fields=("conformance_rate", "adherence_rate"),
        )

    def test_unknown_identity_is_visible_in_quarantine(self) -> None:
        accepted, quarantine = resolve_rows(
            input_rows("unknown_identity_events.csv"),
            self.resolver,
            entity="AgentEvent",
            key_field="agent_event_id",
            identity_field="operational_id",
            timestamp_field="event_start",
        )
        self.assertEqual(accepted, [])
        self.assertEqual(quarantine, expected_rows("quarantine_unknown_identity.csv"))

    def test_close_day_is_replacement_based_and_idempotent(self) -> None:
        live = interval_staffing(self.schedules, self.logins, self.events)
        existing = input_rows("closed_staffing_existing.csv")
        first = close_day(existing, live, "2026-01-16", "2026-01-17T00:05:00Z")
        second = close_day(first, live, "2026-01-16", "2026-01-17T00:05:00Z")
        self.assertEqual(first, second)
        self.assertEqual(second, expected_rows("closed_staffing_after_close.csv"))
        grain = {(row["business_date"], row["interval_start"], row["activity_key"]) for row in second}
        self.assertEqual(len(grain), len(second))


if __name__ == "__main__":
    unittest.main()
