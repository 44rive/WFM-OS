from __future__ import annotations

import csv
import importlib.util
import unittest
from collections import defaultdict
from decimal import Decimal
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


planning = load_module("wfm_planning_v04", "90_Source_Code/03_Python/planning.py")
supply = load_module("wfm_supply_v04", "90_Source_Code/03_Python/supply.py")
excel_adapter = load_module("wfm_excel_adapter_v04", "90_Source_Code/03_Python/excel_adapter.py")
excel_adapter.intervalize_daily_candidates = planning.intervalize_daily_candidates
excel_adapter.apply_approved_scenarios = planning.apply_approved_scenarios
excel_adapter.aggregate_weekly_peak_capacity = planning.aggregate_weekly_peak_capacity
excel_adapter.project_base_paid_supply = supply.project_base_paid_supply
excel_adapter.plan_hiring = supply.plan_hiring


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


class PlanningSupplyTest(unittest.TestCase):
    def assert_rows(
        self,
        actual: list[dict[str, object]],
        expected_name: str,
        *,
        keys: tuple[str, ...],
        numeric: tuple[str, ...],
    ) -> None:
        wanted = expected(expected_name)
        row_key = lambda row: tuple(str(row[field]) for field in keys)
        actual_map = {row_key(row): row for row in actual}
        wanted_map = {row_key(row): row for row in wanted}
        self.assertEqual(set(actual_map), set(wanted_map))
        for key, wanted_row in wanted_map.items():
            actual_row = actual_map[key]
            for field, value in wanted_row.items():
                if field in keys:
                    continue
                if field in numeric:
                    actual_value = actual_row.get(field)
                    if actual_value is None:
                        self.assertEqual(value, "", (key, field))
                    else:
                        self.assertAlmostEqual(float(actual_value), float(value), places=8, msg=f"{key} {field}")
                else:
                    self.assertEqual(str(actual_row.get(field, "")), value, (key, field))

    def interval_candidates(self) -> list[dict[str, object]]:
        return planning.intervalize_daily_candidates(
            inputs("planning_daily_candidates.csv"),
            inputs("planning_intraday_profiles.csv"),
        )

    def test_intervalization_reconciles_daily_totals_and_uses_precedence(self) -> None:
        intervals = self.interval_candidates()
        by_date: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in intervals:
            by_date[str(row["Date"])].append(row)
        actual: list[dict[str, object]] = []
        daily_source = {
            row["Date"]: Decimal(row["ForecastVolume"])
            for row in inputs("planning_daily_candidates.csv")
            if row["ApprovedFlag"] == "TRUE"
        }
        for day, day_rows in sorted(by_date.items()):
            indexed = {str(row["IntervalKey"]): row for row in day_rows}
            actual.append(
                {
                    "Date": day,
                    "ProfileDayType": day_rows[0]["ProfileDayType"],
                    "ProfileValidFrom": day_rows[0]["ProfileValidFrom"],
                    "IntervalCount": len(day_rows),
                    "DailyForecastVolume": daily_source[day],
                    "AllocatedForecastVolume": sum(
                        (row["ForecastVolume"] for row in day_rows), Decimal(0)
                    ),
                    "I00Volume": indexed["I00"]["ForecastVolume"],
                    "I47Volume": indexed["I47"]["ForecastVolume"],
                }
            )
        self.assert_rows(
            actual,
            "planning_interval_reconciliation.csv",
            keys=("Date",),
            numeric=("IntervalCount", "DailyForecastVolume", "AllocatedForecastVolume", "I00Volume", "I47Volume"),
        )

    def test_intervalization_supports_different_profile_keys_by_activity(self) -> None:
        candidates = inputs("planning_daily_candidates.csv")[:1]
        second = dict(candidates[0], CandidateKey="CAND_002", ActivityKey="ACT_CASES")
        second["IntradayProfileKey"] = "PROFILE_CASES"
        profiles = inputs("planning_intraday_profiles.csv")
        all_rows = [row for row in profiles if row["DayType"] == "ALL"]
        case_profile = [dict(row, ProfileKey="PROFILE_CASES") for row in all_rows]
        result = planning.intervalize_daily_candidates(candidates + [second], profiles + case_profile)
        self.assertEqual(len(result), 96)

    def test_intervalization_rejects_bad_profile_sum_and_duplicate_interval(self) -> None:
        candidate = [inputs("planning_daily_candidates.csv")[1]]
        profiles = inputs("planning_intraday_profiles.csv")
        bad_sum = [dict(row) for row in profiles]
        all_i00 = next(row for row in bad_sum if row["DayType"] == "ALL" and row["IntervalKey"] == "I00")
        all_i00["VolumeWeight"] = "0.03"
        with self.assertRaisesRegex(ValueError, "VolumeWeight must sum to 1"):
            planning.intervalize_daily_candidates(candidate, bad_sum)
        duplicate = profiles + [dict(next(row for row in profiles if row["DayType"] == "ALL" and row["IntervalKey"] == "I00"))]
        with self.assertRaisesRegex(ValueError, "Duplicate active profile interval"):
            planning.intervalize_daily_candidates(candidate, duplicate)

    def test_scenarios_keep_complete_base_and_match_expected(self) -> None:
        scenarios = planning.apply_approved_scenarios(
            self.interval_candidates(), inputs("planning_scenarios_v04.csv")
        )
        grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
        for row in scenarios:
            grouped[(str(row["ScenarioKey"]), str(row["Date"]))].append(row)
        actual = []
        for (scenario, day), day_rows in sorted(grouped.items()):
            volume = sum((row["ForecastVolume"] for row in day_rows), Decimal(0))
            workload = sum((row["ForecastVolume"] * row["ForecastAHT"] for row in day_rows), Decimal(0))
            actual.append(
                {
                    "ScenarioKey": scenario,
                    "Date": day,
                    "ForecastVolume": volume,
                    "ForecastAHT": Decimal(0) if volume == 0 else workload / volume,
                    "Shrinkage": day_rows[0]["Shrinkage"],
                }
            )
        self.assert_rows(
            actual,
            "planning_scenario_summary_v04.csv",
            keys=("ScenarioKey", "Date"),
            numeric=("ForecastVolume", "ForecastAHT", "Shrinkage"),
        )

    def test_scenarios_reject_overlap_and_negative_results(self) -> None:
        base = self.interval_candidates()
        scenario = inputs("planning_scenarios_v04.csv")[0]
        with self.assertRaisesRegex(ValueError, "Duplicate or overlapping"):
            planning.apply_approved_scenarios(base, [scenario, dict(scenario)])
        negative = dict(scenario, ScenarioKey="NEG", VolumeChangePct="-101")
        with self.assertRaisesRegex(ValueError, "negative volume"):
            planning.apply_approved_scenarios(base, [negative])

    def test_weekly_peak_capacity_matches_expected_and_rejects_bad_grain(self) -> None:
        actual = planning.aggregate_weekly_peak_capacity(
            inputs("planning_capacity_candidates_v04.csv")
        )
        self.assert_rows(
            actual,
            "planning_weekly_peak_capacity.csv",
            keys=("PeriodStart", "ScenarioKey", "ActivityKey"),
            numeric=("RequiredPaidFTE",),
        )
        source = inputs("planning_capacity_candidates_v04.csv")
        with self.assertRaisesRegex(ValueError, "Duplicate capacity candidate grain"):
            planning.aggregate_weekly_peak_capacity(source + [dict(source[0])])
        mixed = source + [dict(source[0], ChannelKey="CHAT", IntervalKey="I03")]
        with self.assertRaisesRegex(ValueError, "multiple ChannelKey"):
            planning.aggregate_weekly_peak_capacity(mixed)

    def test_recursive_base_supply_matches_expected(self) -> None:
        actual = supply.project_base_paid_supply(
            inputs("planning_supply_assumptions.csv")
        )
        self.assert_rows(
            actual,
            "planning_base_supply.csv",
            keys=("PeriodStart", "ActivityKey"),
            numeric=("OpeningPaidFTE", "TransfersInFTE", "TransfersOutFTE", "LeaversFTE", "OtherChangeFTE", "BasePaidFTE"),
        )

    def test_base_supply_fails_closed_on_missing_opening_and_gaps(self) -> None:
        source = inputs("planning_supply_assumptions.csv")[:4]
        missing_opening = [dict(row) for row in source]
        missing_opening[0]["OpeningPaidFTE"] = ""
        with self.assertRaisesRegex(ValueError, "requires nonnegative OpeningPaidFTE"):
            supply.project_base_paid_supply(missing_opening)
        gap = [source[0], source[2]]
        with self.assertRaisesRegex(ValueError, "contiguous Mondays"):
            supply.project_base_paid_supply(gap)

    def test_hiring_plan_matches_expected_and_does_not_repeat_filled_gap(self) -> None:
        base = supply.project_base_paid_supply(
            inputs("planning_supply_assumptions.csv")
        )
        supply_rows, waves = supply.plan_hiring(
            inputs("planning_hiring_requirements.csv"),
            base,
            inputs("planning_hiring_policies.csv"),
            as_of_date="2026-01-15",
        )
        self.assert_rows(
            supply_rows,
            "planning_hiring_supply.csv",
            keys=("PeriodStart", "ScenarioKey", "ActivityKey"),
            numeric=("RequiredPaidFTE", "BufferPaidFTE", "BaselinePaidFTE", "PlannedHirePaidFTE", "ProjectedPaidFTE", "ResidualGapPaidFTE"),
        )
        self.assert_rows(
            waves,
            "planning_hiring_waves.csv",
            keys=("WaveKey",),
            numeric=("PlannedHeads", "ExpectedYield", "FTEPerHead", "ExpectedPaidFTE"),
        )
        self.assertEqual([row["ProficiencyDate"] for row in waves], ["2026-02-02", "2026-02-02", "2026-02-16"])
        self.assertEqual([row["PlannedHeads"] for row in waves[:2]], [2, 2])
        self.assertEqual([row["TimingStatus"] for row in waves], ["LATE_TO_PLAN", "LATE_TO_PLAN", "ON_TIME"])

    def test_hiring_rejects_overlapping_policy_and_missing_supply(self) -> None:
        base = supply.project_base_paid_supply(
            inputs("planning_supply_assumptions.csv")
        )
        requirements = inputs("planning_hiring_requirements.csv")
        policies = inputs("planning_hiring_policies.csv")
        overlap = dict(policies[0], PolicyKey="POLICY_OVERLAP", ValidFrom="2026-02-01", ValidTo="2026-02-10")
        with self.assertRaisesRegex(ValueError, "policies overlap"):
            supply.plan_hiring(requirements, base, policies + [overlap], as_of_date="2026-01-15")
        with self.assertRaisesRegex(ValueError, "Missing base supply"):
            supply.plan_hiring(requirements, base[:-1], policies, as_of_date="2026-01-15")

    def test_excel_intraday_adapter_keeps_base_and_approved_scenarios(self) -> None:
        daily = [
            {
                **row,
                "Profile": "DEFAULT",
                "ForecastAHTSeconds": row["ForecastAHT"],
            }
            for row in inputs("planning_daily_candidates.csv")
        ]
        profiles = [
            {
                **row,
                "Profile": "DEFAULT",
                "Approved": row["ApprovedFlag"],
            }
            for row in inputs("planning_intraday_profiles.csv")
        ]
        scenarios = [
            {
                **row,
                "Profile": "DEFAULT",
                "ApprovalStatus": "APPROVED" if row["ApprovedFlag"] == "TRUE" else "DRAFT",
            }
            for row in inputs("planning_scenarios_v04.csv")
        ]
        actual = excel_adapter.run_intraday_excel(
            FakeFrame(daily),
            FakeFrame(profiles),
            FakeFrame(scenarios),
            profile="DEFAULT",
        )
        self.assertEqual(len(actual), 288)
        self.assertEqual({row["Scenario"] for row in actual}, {"BASE", "SCN_UP", "SCN_ZERO"})
        base_total = sum(
            row["ForecastVolume"]
            for row in actual
            if row["Scenario"] == "BASE" and row["Date"] == "2026-02-02"
        )
        up_total = sum(
            row["ForecastVolume"]
            for row in actual
            if row["Scenario"] == "SCN_UP" and row["Date"] == "2026-02-02"
        )
        self.assertAlmostEqual(base_total, 100.0, places=8)
        self.assertAlmostEqual(up_total, 110.0, places=8)

    def test_excel_supply_adapter_matches_governed_core(self) -> None:
        requirements = [
            {
                "Date": row["PeriodStart"],
                "IntervalKey": "I00",
                "ScenarioKey": row["ScenarioKey"],
                "ActivityKey": row["ActivityKey"],
                "ChannelKey": "VOICE",
                "PaidFTE": row["RequiredPaidFTE"],
            }
            for row in inputs("planning_hiring_requirements.csv")
        ]
        assumptions = [
            {**row, "Profile": "DEFAULT", "ApprovalStatus": "APPROVED"}
            for row in inputs("planning_supply_assumptions.csv")
        ]
        policies = [
            {**row, "Profile": "DEFAULT", "Approved": row["ApprovedFlag"]}
            for row in inputs("planning_hiring_policies.csv")
        ]
        supply_rows, hiring_rows = excel_adapter.run_supply_excel(
            FakeFrame(requirements),
            FakeFrame([{"ActivityKey": "ACT_SUPPORT", "OpeningPaidFTE": 6}]),
            FakeFrame(assumptions),
            FakeFrame(policies),
            profile="DEFAULT",
            as_of_date="2026-01-15",
        )
        self.assert_rows(
            supply_rows,
            "planning_hiring_supply.csv",
            keys=("PeriodStart", "ScenarioKey", "ActivityKey"),
            numeric=("RequiredPaidFTE", "BufferPaidFTE", "BaselinePaidFTE", "PlannedHirePaidFTE", "ProjectedPaidFTE", "ResidualGapPaidFTE"),
        )
        self.assert_rows(
            hiring_rows,
            "planning_hiring_waves.csv",
            keys=("WaveKey",),
            numeric=("PlannedHeads", "ExpectedYield", "FTEPerHead", "ExpectedPaidFTE"),
        )
        self.assertTrue(all(row["RecruitmentStart"] <= row["TrainingStart"] for row in hiring_rows))
        self.assertTrue(all(row["TrainingStart"] <= row["NestingStart"] for row in hiring_rows))


if __name__ == "__main__":
    unittest.main()
