from __future__ import annotations

import csv
import importlib.util
import math
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


forecast = load_module("wfm_forecast", "90_Source_Code/03_Python/forecast.py")
capacity = load_module("wfm_capacity", "90_Source_Code/03_Python/capacity.py")
excel_adapter = load_module("wfm_excel_adapter", "90_Source_Code/03_Python/excel_adapter.py")
excel_adapter.seasonal_naive_forecast = forecast.seasonal_naive_forecast
excel_adapter.apply_approved_adjustments = forecast.apply_approved_adjustments
excel_adapter.calculate_capacity_row = capacity.calculate_capacity_row


class FakeFrame:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records

    def to_dict(self, orientation: str) -> list[dict[str, object]]:
        if orientation != "records":
            raise ValueError("FakeFrame only supports records orientation")
        return self.records


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def input_rows(name: str) -> list[dict[str, str]]:
    return read_csv(INPUT_ROOT / name)


def expected_rows(name: str) -> list[dict[str, str]]:
    return read_csv(EXPECTED_ROOT / name)


class PlanningCycleTest(unittest.TestCase):
    def assert_expected(
        self,
        actual: list[dict[str, object]],
        expected_file: str,
        *,
        keys: tuple[str, ...],
        numeric: tuple[str, ...],
        nullable_numeric: tuple[str, ...] = (),
    ) -> None:
        expected = expected_rows(expected_file)
        row_key = lambda row: tuple(str(row[field]) for field in keys)
        actual_map = {row_key(row): row for row in actual}
        expected_map = {row_key(row): row for row in expected}
        self.assertEqual(set(actual_map), set(expected_map))
        for key, expected_row in expected_map.items():
            actual_row = actual_map[key]
            for field, expected_value in expected_row.items():
                if field in keys:
                    continue
                if field in nullable_numeric and expected_value == "":
                    self.assertIsNone(actual_row[field], (key, field))
                elif field in numeric or field in nullable_numeric:
                    self.assertAlmostEqual(float(actual_row[field]), float(expected_value), places=6, msg=f"{key} {field}")
                else:
                    actual_value = "" if actual_row[field] is None else str(actual_row[field])
                    self.assertEqual(actual_value, expected_value, (key, field))

    def test_grouped_seasonal_naive_matches_expected(self) -> None:
        actual = forecast.seasonal_naive_forecast(
            input_rows("planning_forecast_history.csv"), periods=4, seasonal_periods=7
        )
        self.assert_expected(
            actual,
            "planning_seasonal_naive.csv",
            keys=("Date", "ActivityKey", "ChannelKey"),
            numeric=("BaselineForecast",),
        )

    def test_seasonal_naive_repeats_for_horizons_longer_than_one_season(self) -> None:
        history = [
            {"Date": f"2026-01-0{day}", "ActivityKey": "ACT", "ChannelKey": "VOICE", "Volume": day}
            for day in range(1, 8)
        ]
        actual = forecast.seasonal_naive_forecast(history, periods=8, seasonal_periods=7)
        self.assertEqual([row["BaselineForecast"] for row in actual], [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 1.0])

    def test_forecast_rejects_invalid_date_and_grain(self) -> None:
        rows = input_rows("planning_forecast_history.csv")
        with self.assertRaisesRegex(ValueError, "Duplicate history grain"):
            forecast.seasonal_naive_forecast(rows + [dict(rows[0])], periods=1, seasonal_periods=7)
        timestamped = [dict(row) for row in rows]
        timestamped[0]["Date"] = "2026-01-01T00:00:00"
        with self.assertRaisesRegex(ValueError, "strict YYYY-MM-DD"):
            forecast.seasonal_naive_forecast(timestamped, periods=1, seasonal_periods=7)
        missing_day = [row for row in rows if not (row["ActivityKey"] == "ACT_SUPPORT" and row["Date"] == "2026-01-06")]
        with self.assertRaisesRegex(ValueError, "missing daily observation"):
            forecast.seasonal_naive_forecast(missing_day, periods=1, seasonal_periods=7)
        blank_group = [dict(row) for row in rows]
        blank_group[0]["ChannelKey"] = ""
        with self.assertRaisesRegex(ValueError, "cannot be blank"):
            forecast.seasonal_naive_forecast(blank_group, periods=1, seasonal_periods=7)
        with self.assertRaisesRegex(ValueError, "positive integer"):
            forecast.seasonal_naive_forecast(rows, periods=0, seasonal_periods=7)

    def test_forecast_rejects_short_history_and_nonfinite_demand(self) -> None:
        short = [
            {"Date": f"2026-01-0{day}", "ActivityKey": "ACT", "ChannelKey": "VOICE", "Volume": day}
            for day in range(1, 7)
        ]
        with self.assertRaisesRegex(ValueError, "requires at least"):
            forecast.seasonal_naive_forecast(short, periods=1, seasonal_periods=7)
        short.append({"Date": "2026-01-07", "ActivityKey": "ACT", "ChannelKey": "VOICE", "Volume": math.nan})
        with self.assertRaisesRegex(ValueError, "must be finite"):
            forecast.seasonal_naive_forecast(short, periods=1, seasonal_periods=7)

    def test_backtest_scores_and_zero_actual_policy(self) -> None:
        actual = forecast.score_backtest(input_rows("planning_backtest.csv"))
        self.assert_expected(
            actual,
            "planning_backtest_scores.csv",
            keys=("ActivityKey", "ChannelKey"),
            numeric=("ObservationCount", "ActualTotal", "ForecastTotal", "MAE", "RMSE"),
            nullable_numeric=("WAPEPercent", "SignedBiasPercent"),
        )
        cases = next(row for row in actual if row["ActivityKey"] == "ACT_CASES")
        self.assertIsNone(cases["WAPEPercent"])
        self.assertIsNone(cases["SignedBiasPercent"])
        self.assertEqual(cases["ZeroActualPolicy"], "UNDEFINED_DENOMINATOR")

    def test_backtest_rejects_duplicate_and_negative_actual(self) -> None:
        rows = input_rows("planning_backtest.csv")
        with self.assertRaisesRegex(ValueError, "Duplicate backtest grain"):
            forecast.score_backtest(rows + [dict(rows[0])])
        negative = [dict(row) for row in rows]
        negative[0]["Actual"] = "-1"
        with self.assertRaisesRegex(ValueError, "at least 0"):
            forecast.score_backtest(negative)

    def test_approved_adjustments_match_expected_and_override_wins(self) -> None:
        baseline = forecast.seasonal_naive_forecast(
            input_rows("planning_forecast_history.csv"), periods=4, seasonal_periods=7
        )
        actual = forecast.apply_approved_adjustments(
            baseline,
            input_rows("planning_calendar_impacts.csv"),
            input_rows("planning_overrides.csv"),
        )
        self.assert_expected(
            actual,
            "planning_adjusted_forecast.csv",
            keys=("Date", "ActivityKey", "ChannelKey"),
            numeric=("BaselineForecast", "CalendarImpactPercent", "PostCalendarForecast", "FinalForecast"),
            nullable_numeric=("AbsoluteOverride",),
        )
        support_16 = next(row for row in actual if row["ActivityKey"] == "ACT_SUPPORT" and row["Date"] == "2026-01-16")
        self.assertEqual(support_16["PostCalendarForecast"], 132.25)
        self.assertEqual(support_16["FinalForecast"], 150.0)
        self.assertEqual(support_16["AdjustmentSource"], "ABSOLUTE_OVERRIDE")

    def test_adjustments_enforce_approval_boundaries(self) -> None:
        baseline = [{"Date": "2026-01-15", "ActivityKey": "ACT", "ChannelKey": "VOICE", "BaselineForecast": 100}]
        remove_all = [{"EventKey": "ZERO", "ActivityKey": "ACT", "ChannelKey": "VOICE", "StartDate": "2026-01-15", "EndDate": "2026-01-15", "ImpactPercent": -100, "ApprovedFlag": True}]
        adjusted = forecast.apply_approved_adjustments(baseline, remove_all, [])
        self.assertEqual(adjusted[0]["FinalForecast"], 0.0)
        invalid = [dict(remove_all[0], ImpactPercent=-100.1)]
        with self.assertRaisesRegex(ValueError, "at least -100"):
            forecast.apply_approved_adjustments(baseline, invalid, [])
        stacked_reductions = [
            dict(remove_all[0], EventKey="REDUCTION_A", ImpactPercent=-60),
            dict(remove_all[0], EventKey="REDUCTION_B", ImpactPercent=-50),
        ]
        with self.assertRaisesRegex(ValueError, "Combined calendar impact is below -100"):
            forecast.apply_approved_adjustments(baseline, stacked_reductions, [])
        duplicate_overrides = [
            {"OverrideKey": key, "ActivityKey": "ACT", "ChannelKey": "VOICE", "Date": "2026-01-15", "OverrideValue": value, "ApprovedFlag": True}
            for key, value in (("A", 90), ("B", 80))
        ]
        with self.assertRaisesRegex(ValueError, "More than one approved"):
            forecast.apply_approved_adjustments(baseline, [], duplicate_overrides)
        unmatched = [{"OverrideKey": "X", "ActivityKey": "OTHER", "ChannelKey": "VOICE", "Date": "2026-01-15", "OverrideValue": 10, "ApprovedFlag": True}]
        with self.assertRaisesRegex(ValueError, "matches no forecast grain"):
            forecast.apply_approved_adjustments(baseline, [], unmatched)

    def test_capacity_scenarios_match_expected(self) -> None:
        actual = []
        for scenario in input_rows("planning_capacity_scenarios.csv"):
            result = capacity.calculate_capacity_row(scenario)
            result["ScenarioKey"] = scenario["ScenarioKey"]
            actual.append(result)
        self.assert_expected(
            actual,
            "planning_capacity.csv",
            keys=("ScenarioKey",),
            numeric=("OfferedTrafficErlangs", "EffectiveTrafficErlangs", "ProductiveFTE", "PaidFTE", "RequiredHeads", "AchievedOccupancy"),
            nullable_numeric=("AchievedServiceLevel",),
        )

    def test_capacity_zero_demand_boundary(self) -> None:
        erlang = capacity.erlang_c_capacity(
            volume=0, aht_seconds=0, interval_minutes=30,
            target_service_level=0.8, answer_time_seconds=20,
            occupancy=1, concurrency=1, shrinkage=0, fte_per_head=1,
        )
        workload = capacity.workload_capacity(
            volume=0, aht_seconds=0, interval_minutes=30,
            occupancy=1, concurrency=1, shrinkage=0, fte_per_head=1,
        )
        self.assertEqual(erlang["RequiredHeads"], 0)
        self.assertEqual(erlang["AchievedServiceLevel"], 1.0)
        self.assertEqual(workload["RequiredHeads"], 0)
        self.assertIsNone(workload["AchievedServiceLevel"])

    def test_capacity_rejects_invalid_parameters(self) -> None:
        valid = dict(volume=10, aht_seconds=180, interval_minutes=30, occupancy=0.85, concurrency=1, shrinkage=0.2, fte_per_head=1)
        for field, value in (("volume", -1), ("occupancy", 0), ("occupancy", 1.01), ("concurrency", 0.99), ("shrinkage", 1), ("shrinkage", -0.01), ("fte_per_head", 0), ("fte_per_head", 1.01)):
            parameters = dict(valid)
            parameters[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    capacity.workload_capacity(**parameters)
        with self.assertRaisesRegex(ValueError, "aht_seconds must be greater"):
            capacity.workload_capacity(**dict(valid, aht_seconds=0))
        with self.assertRaisesRegex(ValueError, "target_service_level"):
            capacity.erlang_c_capacity(**valid, target_service_level=1, answer_time_seconds=20)
        with self.assertRaisesRegex(ValueError, "ERLANG_C or WORKLOAD"):
            capacity.calculate_capacity("VENDOR_METHOD", **valid)
        with self.assertRaisesRegex(ValueError, "No Erlang C solution"):
            capacity.erlang_c_capacity(**valid, target_service_level=0.99, answer_time_seconds=1, max_agents=1)

    def test_excel_forecast_adapter_honors_as_of_date(self) -> None:
        history = [
            {
                "Date": f"2026-01-0{day}",
                "ActivityKey": "ACT_SUPPORT",
                "ChannelKey": "VOICE",
                "Volume": day,
                "Handled": day,
                "HandleSeconds": day * 180,
            }
            for day in range(1, 9)
        ]
        history[-1]["Volume"] = 999
        policies = [{
            "Profile": "DEFAULT",
            "PolicyKey": "FC_BASE",
            "ActivityKey": "ACT_SUPPORT",
            "ChannelKey": "VOICE",
            "IntradayProfileKey": "STANDARD_30M",
            "Method": "SEASONAL_NAIVE",
            "Frequency": "DAILY",
            "HistoryPeriods": 7,
            "HorizonPeriods": 1,
            "SeasonLength": 7,
            "MinimumHistory": 7,
            "ValidFrom": "2026-01-01",
            "ValidTo": None,
            "Approved": True,
        }]
        actual = excel_adapter.run_forecast_excel(
            FakeFrame(history),
            FakeFrame(policies),
            FakeFrame([]),
            FakeFrame([]),
            profile="DEFAULT",
            as_of_date="2026-01-07",
        )
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]["Date"], "2026-01-08")
        self.assertEqual(actual[0]["ForecastVolume"], 1.0)
        self.assertEqual(actual[0]["ForecastAHTSeconds"], 180.0)

    def test_excel_parameter_lookup_is_exact_and_nonblank(self) -> None:
        parameters = FakeFrame([
            {"Parameter": "EnterpriseProfile", "Value": "DEFAULT"},
            {"Parameter": "AsOfDate", "Value": "2026-01-07"},
        ])
        self.assertEqual(
            excel_adapter.parameter_value_excel(parameters, "EnterpriseProfile"),
            "DEFAULT",
        )
        with self.assertRaisesRegex(ValueError, "one nonblank"):
            excel_adapter.parameter_value_excel(parameters, "Missing")

    def test_excel_capacity_adapter_requires_approved_interval_forecast(self) -> None:
        forecast_row = {
            "ApprovalStatus": "APPROVED",
            "ForecastVersionKey": "FC_20260108",
            "IntervalStart": "2026-01-08T09:00:00",
            "ActivityKey": "ACT_SUPPORT",
            "ChannelKey": "VOICE",
            "ForecastVolume": 10,
            "ForecastAHTSeconds": 180,
        }
        policy = {
            "Profile": "DEFAULT",
            "PolicyKey": "CAP_VOICE",
            "ActivityKey": "ACT_SUPPORT",
            "ChannelKey": "VOICE",
            "Method": "ERLANG_C",
            "IntervalMinutes": 30,
            "TargetServiceLevel": 0.8,
            "AnswerTimeSeconds": 20,
            "MaxOccupancy": 0.85,
            "ShrinkagePct": 0.2,
            "Concurrency": 1,
            "FTEPerHead": 1,
            "ValidFrom": "2026-01-01",
            "ValidTo": None,
            "Approved": True,
        }
        actual = excel_adapter.run_capacity_excel(
            FakeFrame([forecast_row]), FakeFrame([policy]), profile="DEFAULT"
        )
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]["ForecastVersionKey"], "FC_20260108")
        self.assertGreater(actual[0]["RequiredFTE"], 0)
        rejected = dict(forecast_row, ApprovalStatus="DRAFT")
        with self.assertRaisesRegex(ValueError, "approved interval forecast"):
            excel_adapter.run_capacity_excel(
                FakeFrame([rejected]), FakeFrame([policy]), profile="DEFAULT"
            )


if __name__ == "__main__":
    unittest.main()
