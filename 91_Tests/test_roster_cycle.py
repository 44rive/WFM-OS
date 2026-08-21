from __future__ import annotations

import csv
import importlib.util
import unittest
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TEST_ROOT.parent
INPUT_ROOT = TEST_ROOT / "anonymized-input"


def load_module(name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs(name: str) -> list[dict[str, str]]:
    with (INPUT_ROOT / name).open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


scheduling = load_module("wfm_scheduling_v06", "90_Source_Code/03_Python/scheduling.py")
roster = load_module("wfm_roster_v06", "90_Source_Code/03_Python/roster.py")
leave_requests = load_module("wfm_leave_requests_v06", "90_Source_Code/03_Python/leave_requests.py")
swaps = load_module("wfm_swaps_v06", "90_Source_Code/03_Python/swaps.py")
excel_adapter = load_module("wfm_excel_adapter_v06", "90_Source_Code/03_Python/excel_adapter.py")
roster.expand_pattern_occurrences = scheduling.expand_pattern_occurrences
swaps.validate_named_roster = roster.validate_named_roster
excel_adapter.expand_pattern_occurrences = scheduling.expand_pattern_occurrences
excel_adapter.assign_named_roster = roster.assign_named_roster
excel_adapter._roster_flat_segments = roster._roster_flat_segments
excel_adapter.evaluate_leave_requests = leave_requests.evaluate_leave_requests
excel_adapter.evaluate_swap_requests = swaps.evaluate_swap_requests
excel_adapter.validate_named_roster = roster.validate_named_roster


class FakeFrame:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records

    def to_dict(self, orientation: str) -> list[dict[str, object]]:
        if orientation != "records":
            raise ValueError("FakeFrame only supports records orientation")
        return self.records


class RosterCycleTest(unittest.TestCase):
    def source(self):
        people = [row for row in inputs("people.csv") if row["AgentKey"] in {"AGENT_001", "AGENT_002"}]
        return {
            "plan": inputs("named_roster_plan_v06.csv"),
            "patterns": inputs("shift_patterns_v05.csv"),
            "coverage": [{"IntervalStart": "2026-02-02T00:00:00", "ActivityKey": "ACT_SUPPORT", "CoverageStatus": "COMPLETE", "UncoveredFTE": "0"}],
            "people": people,
            "policies": inputs("roster_policies_v06.csv"),
            "contracts": inputs("agent_contracts_v06.csv"),
            "eligibility": inputs("activity_eligibility_v06.csv"),
            "skills": inputs("agent_skills_v06.csv"),
            "requirements": inputs("activity_skill_requirements_v06.csv"),
            "availability": inputs("agent_availability_v06.csv"),
            "preferences": inputs("agent_preferences_v06.csv"),
        }

    def assigned(self):
        source = self.source()
        result = roster.assign_named_roster(
            source["plan"], source["patterns"], source["coverage"], source["people"],
            source["policies"], source["contracts"], source["eligibility"],
            source["skills"], source["requirements"], source["availability"],
            source["preferences"],
        )
        return source, result

    def test_occurrence_keys_and_assignment_are_deterministic(self) -> None:
        source, (assignments, segments, diagnostics, periods) = self.assigned()
        self.assertEqual(
            [(row["PatternKey"], row["AgentKey"]) for row in assignments],
            [("P_EARLY", "AGENT_001"), ("P_LATE", "AGENT_002")],
        )
        self.assertEqual(
            assignments[0]["OccurrenceKey"],
            "SCH_V06|BASE|2026-02-02|ACT_SUPPORT|PV1|P_EARLY|0001",
        )
        self.assertEqual(assignments[0]["AssignmentKey"], assignments[0]["OccurrenceKey"])
        self.assertNotIn(assignments[0]["AgentKey"], assignments[0]["AssignmentKey"])
        self.assertEqual(len(segments), 16)
        self.assertEqual(len({row["SegmentKey"] for row in segments}), 16)
        self.assertFalse(any(row["Severity"] == "BLOCKING" for row in diagnostics))
        self.assertEqual({row["AssignedPaidHours"] for row in periods}, {roster.Decimal("4")})

        second = roster.assign_named_roster(
            source["plan"], source["patterns"], source["coverage"], source["people"],
            source["policies"], source["contracts"], source["eligibility"],
            source["skills"], source["requirements"], source["availability"],
            source["preferences"],
        )[0]
        self.assertEqual(
            [(row["OccurrenceKey"], row["AgentKey"]) for row in assignments],
            [(row["OccurrenceKey"], row["AgentKey"]) for row in second],
        )

    def test_infeasible_occurrence_remains_visible(self) -> None:
        source = self.source()
        assignments, _, diagnostics, _ = roster.assign_named_roster(
            source["plan"], source["patterns"], source["coverage"], source["people"],
            source["policies"], source["contracts"], source["eligibility"],
            source["skills"], source["requirements"], source["availability"][:1],
            source["preferences"],
        )
        self.assertEqual(len(assignments), 1)
        blocking = [row for row in diagnostics if row["ReasonCode"] == "NO_FEASIBLE_AGENT"]
        self.assertEqual(len(blocking), 1)
        self.assertIn("OUTSIDE_APPROVED_AVAILABILITY", blocking[0]["Detail"])

    def test_leave_queue_is_full_request_and_capacity_governed(self) -> None:
        _, (assignments, segments, _, _) = self.assigned()
        approved_assignments = [{**row, "RosterVersionKey": "ROSTER_V06", "ApprovalStatus": "APPROVED"} for row in assignments]
        leave_plan_by_grain = {
            (row["IntervalStart"], row["ActivityKey"]): {
                "LeavePlanVersionKey": "LEAVE_PLAN_V06",
                "ApprovalStatus": "APPROVED",
                "IntervalStart": row["IntervalStart"],
                "ActivityKey": row["ActivityKey"],
                "ApprovedAllowanceHours": "0.5",
            }
            for row in segments
            if row["ProductiveFlag"]
        }
        leave_plan = list(leave_plan_by_grain.values())
        decisions, consumption = leave_requests.evaluate_leave_requests(
            approved_assignments,
            segments,
            leave_plan,
            inputs("leave_requests_v06.csv"),
            inputs("leave_type_policies_v06.csv"),
            inputs("entitlement_snapshots_v06.csv"),
        )
        by_key = {row["LeaveRequestKey"]: row for row in decisions}
        self.assertEqual(by_key["LR_001"]["RecommendationStatus"], "APPROVE")
        self.assertEqual(by_key["LR_001"]["ApprovedHours"], leave_requests.Decimal("4"))
        self.assertEqual(by_key["LR_002"]["RecommendationStatus"], "DECLINE")
        self.assertEqual(by_key["LR_002"]["DecisionReason"], "OVERLAPS_EXISTING_APPROVED_LEAVE")
        self.assertEqual(by_key["LR_003"]["RecommendationStatus"], "REVIEW_REQUIRED")
        self.assertEqual(len(consumption), 8)

    def test_bilateral_swap_revalidates_the_complete_roster(self) -> None:
        source, (assignments, _, _, _) = self.assigned()
        approved = [{**row, "RosterVersionKey": "ROSTER_V06", "ApprovalStatus": "APPROVED"} for row in assignments]
        decisions, proposals, diagnostics = swaps.evaluate_swap_requests(
            approved,
            inputs("swap_requests_v06.csv"),
            source["people"], source["policies"], source["contracts"],
            source["eligibility"], source["skills"], source["requirements"],
            source["availability"],
        )
        self.assertEqual(decisions[0]["RecommendationStatus"], "APPROVE")
        self.assertEqual(
            {(row["PatternKey"], row["AgentKey"]) for row in proposals},
            {("P_EARLY", "AGENT_002"), ("P_LATE", "AGENT_001")},
        )
        self.assertEqual(diagnostics, [])

    def test_excel_roster_adapter_is_profile_scoped_and_pseudonymous(self) -> None:
        source = self.source()
        plan = [{**row, "Profile": "ENTERPRISE_A", "ApprovalStatus": "APPROVED"} for row in source["plan"]]
        patterns = [
            {
                **{key: value for key, value in row.items() if key != "ApprovedFlag"},
                "Profile": "ENTERPRISE_A",
                "Approved": row["ApprovedFlag"],
            }
            for row in source["patterns"]
        ]
        coverage = [{**row, "Profile": "ENTERPRISE_A", "ApprovalStatus": "APPROVED"} for row in source["coverage"]]
        people = [{**row, "Profile": "ENTERPRISE_A", "Enabled": "TRUE"} for row in source["people"]]
        candidates = excel_adapter.run_roster_excel(
            FakeFrame(plan), FakeFrame(patterns), FakeFrame(coverage), FakeFrame(people),
            FakeFrame(source["policies"]), FakeFrame(source["contracts"]),
            FakeFrame(source["eligibility"]), FakeFrame(source["skills"]),
            FakeFrame(source["requirements"]), FakeFrame(source["availability"]),
            FakeFrame(source["preferences"]), profile="ENTERPRISE_A",
        )
        self.assertEqual(len(candidates), 2)
        self.assertEqual({row["Profile"] for row in candidates}, {"ENTERPRISE_A"})
        self.assertFalse(any("DisplayName" in row or "EmployeeBusinessID" in row for row in candidates))
        self.assertEqual(len(excel_adapter.roster_segment_candidates), 16)
        self.assertFalse(any(row["Severity"] == "BLOCKING" for row in excel_adapter.roster_diagnostic_candidates))


if __name__ == "__main__":
    unittest.main()
