from __future__ import annotations

import csv
import importlib.util
import unittest
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TEST_ROOT.parent
INPUT_ROOT = TEST_ROOT / "anonymized-input"
EXPECTED_ROOT = TEST_ROOT / "expected-output"


def load_module(name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scheduling = load_module("wfm_scheduling_v05", "90_Source_Code/03_Python/scheduling.py")
leave = load_module("wfm_leave_v05", "90_Source_Code/03_Python/leave.py")
excel_adapter = load_module("wfm_excel_adapter_v05", "90_Source_Code/03_Python/excel_adapter.py")
excel_adapter.fit_shift_patterns = scheduling.fit_shift_patterns
excel_adapter.calculate_leave_allowance = leave.calculate_leave_allowance


class FakeFrame:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records

    def to_dict(self, orientation: str) -> list[dict[str, object]]:
        if orientation != "records":
            raise ValueError("FakeFrame only supports records orientation")
        return self.records


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def inputs(name: str) -> list[dict[str, str]]:
    return rows(INPUT_ROOT / name)


def expected(name: str) -> list[dict[str, str]]:
    return rows(EXPECTED_ROOT / name)


class ScheduleLeaveTest(unittest.TestCase):
    def fitted(self):
        return scheduling.fit_shift_patterns(
            inputs("schedule_requirements_v05.csv"),
            inputs("shift_patterns_v05.csv"),
            inputs("shift_rules_v05.csv"),
        )

    def test_pattern_fit_is_deterministic_and_reconciles(self) -> None:
        plan, coverage = self.fitted()
        wanted = expected("schedule_pattern_plan_v05.csv")
        actual_by_key = {row["ScheduleCandidateKey"]: row for row in plan}
        self.assertEqual(set(actual_by_key), {row["ScheduleCandidateKey"] for row in wanted})
        for wanted_row in wanted:
            actual = actual_by_key[wanted_row["ScheduleCandidateKey"]]
            for field, value in wanted_row.items():
                if field in {"PatternCount", "PaidHours", "ProductiveHours", "UncoveredFTEIntervals", "OvercoveredFTEIntervals"}:
                    self.assertAlmostEqual(float(actual[field]), float(value), places=8)
                else:
                    self.assertEqual(str(actual[field]), value)
        summary = {row["IntervalKey"]: row for row in coverage}
        for wanted_row in expected("schedule_interval_summary_v05.csv"):
            actual = summary[wanted_row["IntervalKey"]]
            for field, value in wanted_row.items():
                if field.endswith("FTE"):
                    self.assertAlmostEqual(float(actual[field]), float(value), places=8)
                else:
                    self.assertEqual(str(actual[field]), value)
        self.assertEqual(len(coverage), 48)

    def test_infeasible_fit_stays_visible(self) -> None:
        requirements = [dict(row, RequiredFTE="3" if int(row["IntervalKey"][1:]) < 12 else "0") for row in inputs("schedule_requirements_v05.csv")]
        plan, coverage = scheduling.fit_shift_patterns(
            requirements,
            inputs("shift_patterns_v05.csv"),
            inputs("shift_rules_v05.csv"),
        )
        self.assertTrue(all(row["CoverageStatus"] == "UNCOVERED" for row in plan))
        self.assertGreater(sum(float(row["GapFTE"]) for row in coverage), 0)

    def test_requirements_patterns_and_rules_fail_closed(self) -> None:
        requirements = inputs("schedule_requirements_v05.csv")
        with self.assertRaisesRegex(ValueError, "all 48 intervals"):
            scheduling.fit_shift_patterns(
                requirements[:-1],
                inputs("shift_patterns_v05.csv"),
                inputs("shift_rules_v05.csv"),
            )
        patterns = inputs("shift_patterns_v05.csv")
        overlap = dict(patterns[0], SegmentKey="OVERLAP", StartMinute="120", EndMinute="180")
        with self.assertRaisesRegex(ValueError, "segments overlap"):
            scheduling.fit_shift_patterns(
                requirements,
                patterns + [overlap],
                inputs("shift_rules_v05.csv"),
            )
        rules = inputs("shift_rules_v05.csv")
        duplicate_period = dict(rules[0], RuleKey="RULE_OVERLAP", ValidFrom="2026-01-02")
        with self.assertRaisesRegex(ValueError, "rules overlap"):
            scheduling.fit_shift_patterns(requirements, patterns, rules + [duplicate_period])

    def test_cross_midnight_pattern_expands_to_next_business_date(self) -> None:
        patterns = [{
            "PatternVersionKey": "PV_NIGHT", "PatternKey": "P_NIGHT", "PatternName": "Night",
            "ActivityKey": "ACT_SUPPORT", "DayType": "SUNDAY", "SegmentKey": "WORK",
            "StartMinute": "1320", "EndMinute": "1800", "ScheduleTypeKey": "WORK",
            "PaidFlag": "TRUE", "ProductiveFlag": "TRUE", "ValidFrom": "2026-01-01",
            "ValidTo": "", "ApprovedFlag": "TRUE",
        }]
        expanded = scheduling.expand_schedule_plan(
            [{
                "ScenarioKey": "BASE", "BusinessDate": "2026-02-01", "ActivityKey": "ACT_SUPPORT",
                "PatternVersionKey": "PV_NIGHT", "PatternKey": "P_NIGHT", "PatternCount": 1,
            }],
            patterns,
        )
        self.assertEqual(expanded[0]["IntervalStart"], "2026-02-01T22:00:00")
        self.assertEqual(expanded[-1]["IntervalStart"], "2026-02-02T05:30:00")
        self.assertEqual({row["BusinessDate"] for row in expanded}, {"2026-02-01", "2026-02-02"})

    def test_exact_weekday_pattern_precedes_all_pattern(self) -> None:
        common = {
            "PatternVersionKey": "PV1", "PatternKey": "P_SCOPED", "PatternName": "Scoped",
            "ActivityKey": "ACT_SUPPORT", "SegmentKey": "WORK", "ScheduleTypeKey": "WORK",
            "PaidFlag": "TRUE", "ProductiveFlag": "TRUE", "ValidFrom": "2026-01-01",
            "ValidTo": "", "ApprovedFlag": "TRUE",
        }
        patterns = [
            {**common, "DayType": "ALL", "StartMinute": "0", "EndMinute": "60"},
            {**common, "DayType": "MONDAY", "StartMinute": "120", "EndMinute": "180"},
        ]
        expanded = scheduling.expand_schedule_plan(
            [{
                "ScenarioKey": "BASE", "BusinessDate": "2026-02-02", "ActivityKey": "ACT_SUPPORT",
                "PatternVersionKey": "PV1", "PatternKey": "P_SCOPED", "PatternCount": 1,
            }],
            patterns,
        )
        self.assertEqual([row["IntervalKey"] for row in expanded], ["I04", "I05"])

    def test_leave_allowance_uses_only_interval_headroom(self) -> None:
        _, coverage = self.fitted()
        for row in coverage:
            row["SchedulePlanVersionKey"] = "SCH_V1"
        actual = leave.calculate_leave_allowance(
            coverage,
            inputs("leave_policies_v05.csv"),
        )
        summary = {row["IntervalKey"]: row for row in actual}
        for wanted_row in expected("leave_interval_summary_v05.csv"):
            row = summary[wanted_row["IntervalKey"]]
            self.assertEqual(row["PolicyKey"], wanted_row["PolicyKey"])
            self.assertAlmostEqual(float(row["CalculatedAllowanceHours"]), float(wanted_row["CalculatedAllowanceHours"]), places=8)
            self.assertAlmostEqual(float(row["RemainingCoverageFTE"]), float(wanted_row["RemainingCoverageFTE"]), places=8)
            self.assertEqual(row["AllowanceStatus"], wanted_row["AllowanceStatus"])

    def test_leave_rejects_duplicate_coverage_and_unsafe_policy(self) -> None:
        _, coverage = self.fitted()
        with self.assertRaisesRegex(ValueError, "Duplicate approved schedule coverage grain"):
            leave.calculate_leave_allowance(
                coverage + [dict(coverage[0])],
                inputs("leave_policies_v05.csv"),
            )
        unsafe = [dict(inputs("leave_policies_v05.csv")[0], CoverageFloorPct="0.9")]
        with self.assertRaisesRegex(ValueError, "between 1 and 2"):
            leave.calculate_leave_allowance(coverage, unsafe)

    def test_excel_adapters_scope_profile_and_publish_plain_values(self) -> None:
        requirements = [{**row, "Profile": "ENTERPRISE_A", "ApprovalStatus": "APPROVED"} for row in inputs("schedule_requirements_v05.csv")]
        patterns = [{**row, "Profile": "ENTERPRISE_A", "Approved": row.pop("ApprovedFlag")} for row in [dict(item) for item in inputs("shift_patterns_v05.csv")]]
        rules = [{**row, "Profile": "ENTERPRISE_A", "Approved": row.pop("ApprovedFlag")} for row in [dict(item) for item in inputs("shift_rules_v05.csv")]]
        plan, coverage = excel_adapter.run_schedule_excel(
            FakeFrame(requirements), FakeFrame(patterns), FakeFrame(rules), profile="ENTERPRISE_A"
        )
        self.assertEqual({row["Profile"] for row in plan + coverage}, {"ENTERPRISE_A"})
        self.assertIsInstance(plan[0]["PaidHours"], float)
        approved_coverage = [
            {**row, "SchedulePlanVersionKey": "SCH_V1", "ApprovalStatus": "APPROVED"}
            for row in coverage
        ]
        policies = [{**row, "Profile": "ENTERPRISE_A", "Approved": row.pop("ApprovedFlag")} for row in [dict(item) for item in inputs("leave_policies_v05.csv")]]
        allowance = excel_adapter.run_leave_excel(
            FakeFrame(approved_coverage), FakeFrame(policies), profile="ENTERPRISE_A"
        )
        self.assertEqual(len(allowance), 48)
        self.assertEqual({row["Profile"] for row in allowance}, {"ENTERPRISE_A"})
        self.assertIsInstance(allowance[0]["CalculatedAllowanceHours"], float)


if __name__ == "__main__":
    unittest.main()
