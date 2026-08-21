from __future__ import annotations

import csv
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PQ_ROOT = ROOT / "90_Source_Code" / "01_Power_Query"
MANIFEST = PQ_ROOT / "MANIFEST.csv"
PYTHON_ROOT = ROOT / "90_Source_Code" / "03_Python"
PYTHON_MANIFEST = PYTHON_ROOT / "MANIFEST.csv"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def without_m_strings_and_comments(source: str) -> str:
    output: list[str] = []
    index = 0
    in_string = False
    while index < len(source):
        char = source[index]
        if in_string:
            if char == '"' and index + 1 < len(source) and source[index + 1] == '"':
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "/" and index + 1 < len(source) and source[index + 1] == "/":
            newline = source.find("\n", index)
            index = len(source) if newline == -1 else newline + 1
            output.append("\n")
            continue
        output.append(char)
        index += 1
    if in_string:
        raise AssertionError("Unterminated M string literal")
    return "".join(output)


class RepositoryContractTest(unittest.TestCase):
    def test_power_query_manifest_is_complete_and_ordered(self) -> None:
        manifest = rows(MANIFEST)
        orders = [int(row["InstallOrder"]) for row in manifest]
        names = [row["QueryName"] for row in manifest]
        self.assertEqual(len(orders), len(set(orders)))
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(orders, sorted(orders))

        listed: set[Path] = set()
        for row in manifest:
            source_path = PQ_ROOT / row["SourceFile"]
            self.assertTrue(source_path.is_file(), source_path)
            self.assertEqual(source_path.stem, row["QueryName"])
            listed.add(source_path.resolve())
        actual = {path.resolve() for path in PQ_ROOT.rglob("*.pq")}
        self.assertEqual(listed, actual)

    def test_power_query_delimiters_are_balanced(self) -> None:
        pairs = {"(": ")", "[": "]", "{": "}"}
        reverse = {value: key for key, value in pairs.items()}
        for path in PQ_ROOT.rglob("*.pq"):
            source = without_m_strings_and_comments(path.read_text(encoding="utf-8"))
            stack: list[str] = []
            for char in source:
                if char in pairs:
                    stack.append(char)
                elif char in reverse:
                    self.assertTrue(stack, f"Unexpected {char} in {path}")
                    self.assertEqual(stack.pop(), reverse[char], path)
            self.assertEqual(stack, [], path)

    def test_configuration_keys_are_unambiguous(self) -> None:
        field_mapping = rows(ROOT / "02_Configuration" / "field_mapping.csv")
        field_keys = [
            (row["Profile"], row["Adapter"], row["Entity"], row["SourceField"])
            for row in field_mapping
        ]
        self.assertEqual(len(field_keys), len(set(field_keys)))

        source_systems = rows(ROOT / "02_Configuration" / "source_systems.csv")
        source_keys = [(row["Profile"], row["SystemKey"]) for row in source_systems]
        self.assertEqual(len(source_keys), len(set(source_keys)))

        identities = rows(ROOT / "02_Configuration" / "identity_mapping.csv")
        identity_keys = [
            (row["Profile"], row["SystemKey"], row["ExternalAgentID"], row["ValidFrom"])
            for row in identities
        ]
        self.assertEqual(len(identity_keys), len(set(identity_keys)))

        parameters = rows(ROOT / "02_Configuration" / "parameters.csv")
        self.assertEqual(
            len(parameters),
            len({row["Parameter"] for row in parameters}),
        )

        profiles = rows(ROOT / "02_Configuration" / "intraday_profiles.csv")
        profile_grains = [
            (row["Profile"], row["ProfileKey"], row["DayType"], row["ValidFrom"], row["IntervalKey"])
            for row in profiles
        ]
        self.assertEqual(len(profile_grains), len(set(profile_grains)))

        hiring = rows(ROOT / "02_Configuration" / "hiring_policies.csv")
        hiring_keys = [(row["Profile"], row["PolicyKey"]) for row in hiring]
        self.assertEqual(len(hiring_keys), len(set(hiring_keys)))

        shift_rules = rows(ROOT / "02_Configuration" / "shift_rules.csv")
        shift_rule_keys = [(row["Profile"], row["RuleKey"]) for row in shift_rules]
        self.assertEqual(len(shift_rule_keys), len(set(shift_rule_keys)))

        shift_patterns = rows(ROOT / "02_Configuration" / "shift_patterns.csv")
        shift_pattern_grains = [
            (
                row["Profile"], row["PatternVersionKey"], row["PatternKey"],
                row["DayType"], row["SegmentKey"], row["ValidFrom"],
            )
            for row in shift_patterns
        ]
        self.assertEqual(len(shift_pattern_grains), len(set(shift_pattern_grains)))

        leave = rows(ROOT / "02_Configuration" / "leave_policies.csv")
        leave_keys = [(row["Profile"], row["PolicyKey"]) for row in leave]
        self.assertEqual(len(leave_keys), len(set(leave_keys)))

    def test_dax_measure_names_are_unique(self) -> None:
        measure_pattern = re.compile(r"^([^/\n][^\n]*?)\s*:=\s*$", re.MULTILINE)
        names: list[str] = []
        for path in (ROOT / "90_Source_Code" / "02_DAX").glob("*.dax"):
            names.extend(name.strip() for name in measure_pattern.findall(path.read_text(encoding="utf-8")))
        self.assertGreaterEqual(len(names), 20)
        self.assertEqual(len(names), len(set(names)))

    def test_python_manifest_is_complete_and_ordered(self) -> None:
        manifest = rows(PYTHON_MANIFEST)
        orders = [int(row["InstallOrder"]) for row in manifest]
        anchors = [(row["Sheet"], row["AnchorCell"]) for row in manifest]
        self.assertEqual(orders, sorted(orders))
        self.assertEqual(len(orders), len(set(orders)))
        self.assertEqual(len(anchors), len(set(anchors)))
        self.assertEqual({row["Required"] for row in manifest}, {"TRUE"})

        declared_definition_sources = {
            (PYTHON_ROOT / row["SourceFile"]).resolve()
            for row in manifest
            if row["Role"] == "DEFINITIONS"
        }
        actual_sources = {path.resolve() for path in PYTHON_ROOT.glob("*.py")}
        self.assertEqual(declared_definition_sources, actual_sources)
        self.assertEqual(
            {(row["Role"], row["Entrypoint"]) for row in manifest if row["Role"] != "DEFINITIONS"},
            {
                ("FORECAST_ENTRYPOINT", "run_forecast_excel"),
                ("INTERVAL_ENTRYPOINT", "run_intraday_excel"),
                ("CAPACITY_ENTRYPOINT", "run_capacity_excel"),
                ("SUPPLY_ENTRYPOINT", "run_supply_excel"),
                ("HIRING_OUTPUT", "hiring_candidates"),
                ("SCHEDULE_ENTRYPOINT", "run_schedule_excel"),
                ("SCHEDULE_COVERAGE_OUTPUT", "schedule_coverage_candidates"),
                ("LEAVE_ENTRYPOINT", "run_leave_excel"),
            },
        )

    def test_planning_queries_keep_approval_between_candidates_and_facts(self) -> None:
        forecast_source = (
            PQ_ROOT / "04_Facts" / "fact_Forecast.pq"
        ).read_text(encoding="utf-8")
        requirement_source = (
            PQ_ROOT / "02_Staging" / "stg_AllStaffingRequirements.pq"
        ).read_text(encoding="utf-8")
        requirement_approval_source = (
            PQ_ROOT / "02_Staging" / "stg_RequirementApprovals.pq"
        ).read_text(encoding="utf-8")
        dq_source = (
            PQ_ROOT / "05_Outputs" / "dq_PlanningApprovals.pq"
        ).read_text(encoding="utf-8")
        self.assertIn("stg_ForecastVersions", forecast_source)
        self.assertIn('[ApprovedFlag] and [ValidationStatus] = "VALID"', forecast_source)
        self.assertIn("stg_RequirementApprovals", requirement_source)
        self.assertIn("APPROVED", requirement_approval_source)
        self.assertIn("MappingStatus", requirement_approval_source)
        self.assertIn("BLOCKING", dq_source)

        forecast_staging = (
            PQ_ROOT / "02_Staging" / "stg_ForecastVersions.pq"
        ).read_text(encoding="utf-8")
        forecast_fact = (
            PQ_ROOT / "04_Facts" / "fact_Forecast.pq"
        ).read_text(encoding="utf-8")
        all_requirements = (
            PQ_ROOT / "02_Staging" / "stg_AllStaffingRequirements.pq"
        ).read_text(encoding="utf-8")
        supply_staging = (
            PQ_ROOT / "02_Staging" / "stg_SupplyPlanVersions.pq"
        ).read_text(encoding="utf-8")
        hiring_fact = (
            PQ_ROOT / "04_Facts" / "fact_HiringPlan.pq"
        ).read_text(encoding="utf-8")
        supply_fact = (
            PQ_ROOT / "04_Facts" / "fact_SupplyPlan.pq"
        ).read_text(encoding="utf-8")
        self.assertIn('{"Scenario", "BusinessDate", "IntervalKey", "ActivityKey", "ChannelKey"}', forecast_staging)
        self.assertIn('[Scenario] = "BASE"', forecast_fact)
        self.assertIn('[ScenarioKey] = "BASE"', all_requirements)
        self.assertIn("HIRING_RECONCILIATION_MISMATCH", supply_staging)
        self.assertIn("stg_HiringPlanVersions", hiring_fact)
        self.assertIn("stg_SupplyPlanVersions", supply_fact)

        schedule_staging = (
            PQ_ROOT / "02_Staging" / "stg_SchedulePlanVersions.pq"
        ).read_text(encoding="utf-8")
        schedule_fact = (
            PQ_ROOT / "04_Facts" / "fact_SchedulePlan.pq"
        ).read_text(encoding="utf-8")
        coverage_fact = (
            PQ_ROOT / "04_Facts" / "fact_ScheduleCoverage.pq"
        ).read_text(encoding="utf-8")
        leave_staging = (
            PQ_ROOT / "02_Staging" / "stg_LeavePlanVersions.pq"
        ).read_text(encoding="utf-8")
        leave_fact = (
            PQ_ROOT / "04_Facts" / "fact_LeavePlan.pq"
        ).read_text(encoding="utf-8")
        self.assertIn("PATTERN_COUNT_OUTSIDE_RULE", schedule_staging)
        self.assertIn("OVERLAPPING_PATTERN_SEGMENTS", schedule_staging)
        self.assertIn("stg_SchedulePlanVersions", schedule_fact)
        self.assertIn("tblShiftPatterns", coverage_fact)
        self.assertIn("out_ApprovedRequirementPlan", coverage_fact)
        self.assertIn("fact_ScheduleCoverage", leave_staging)
        self.assertIn("APPROVED_ALLOWANCE_OUT_OF_RANGE", leave_staging)
        self.assertIn("stg_LeavePlanVersions", leave_fact)
        self.assertIn("APPROVED_SCHEDULE_UNDERCOVERED", dq_source)

    def test_close_day_module_targets_governed_tables(self) -> None:
        source = (ROOT / "90_Source_Code" / "04_VBA" / "modCloseDay.bas").read_text(encoding="utf-8")
        for table_name in (
            "tblCloseDayInput",
            "tblCloseDayReady",
            "tblOperationalSnapshots",
            "tblDQChecks",
        ):
            self.assertIn(f'"{table_name}"', source)

    def test_canonical_source_is_vendor_neutral(self) -> None:
        forbidden = ("verint", "allianz", "nice cxone", "genesys")
        source_roots = (
            ROOT / "00_Governance",
            ROOT / "02_Configuration",
            ROOT / "90_Source_Code",
        )
        for source_root in source_roots:
            for path in source_root.rglob("*"):
                if path.is_file():
                    content = path.read_text(encoding="utf-8", errors="ignore").lower()
                    for term in forbidden:
                        self.assertNotIn(term, content, f"{term} found in {path}")


if __name__ == "__main__":
    unittest.main()
