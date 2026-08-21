from __future__ import annotations

import csv
import hashlib
import json
import re
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_ROOT = ROOT / "tools" / "windows"
CONTRACT_PATH = INSTALLER_ROOT / "installer-contract.json"
SCRIPT_PATH = INSTALLER_ROOT / "Install-WfmOsExcel.ps1"
NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def workbook_tables(path: Path) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if not member.startswith("xl/tables/table") or not member.endswith(".xml"):
                continue
            root = ElementTree.fromstring(archive.read(member))
            name = root.attrib["name"]
            columns = root.find("main:tableColumns", NS)
            if columns is None:
                raise AssertionError(f"No columns found for {name}")
            tables[name] = [column.attrib["name"] for column in columns]
    return tables


class ExcelInstallerContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_json(CONTRACT_PATH)

    def test_contract_files_and_artifact_provenance_exist(self) -> None:
        for key in (
            "inputArtifact",
            "buildProvenance",
            "queryManifest",
            "daxManifest",
            "relationshipManifest",
            "pythonManifest",
        ):
            self.assertTrue((ROOT / self.contract[key]).is_file(), key)
        for relative in self.contract["manualSourceFiles"] + self.contract["vbaModules"]:
            self.assertTrue((ROOT / relative).is_file(), relative)

        artifact = ROOT / self.contract["inputArtifact"]
        provenance = load_json(ROOT / self.contract["buildProvenance"])
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        self.assertEqual(digest, provenance["sha256"])
        self.assertEqual(self.contract["workbookRelease"], provenance["release"])

    def test_required_table_schemas_match_the_committed_workbook(self) -> None:
        actual = workbook_tables(ROOT / self.contract["inputArtifact"])
        for required in self.contract["requiredWorkbookTables"]:
            self.assertIn(required["name"], actual)
            self.assertEqual(required["columns"], actual[required["name"]])

    def test_query_manifest_has_exact_source_coverage(self) -> None:
        manifest_path = ROOT / self.contract["queryManifest"]
        with manifest_path.open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        self.assertGreater(len(rows), 40)
        self.assertEqual(
            [int(row["InstallOrder"]) for row in rows],
            sorted(int(row["InstallOrder"]) for row in rows),
        )
        listed = {(manifest_path.parent / row["SourceFile"]).resolve() for row in rows}
        actual = {path.resolve() for path in manifest_path.parent.rglob("*.pq")}
        self.assertEqual(listed, actual)

    def test_dax_manifest_has_exact_measure_coverage(self) -> None:
        manifest_path = ROOT / self.contract["daxManifest"]
        with manifest_path.open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        with (ROOT / self.contract["queryManifest"]).open(newline="", encoding="utf-8") as source:
            model_tables = {
                row["QueryName"] for row in csv.DictReader(source) if row["LoadDestination"] == "DataModel"
            }
        pattern = re.compile(r"^([^/\n][^\n]*?)\s*:=\s*$", re.MULTILINE)
        declared = {(row["SourceFile"], row["MeasureName"]) for row in rows}
        actual: set[tuple[str, str]] = set()
        for dax_path in manifest_path.parent.glob("*.dax"):
            for name in pattern.findall(dax_path.read_text(encoding="utf-8")):
                actual.add((dax_path.name, name.strip()))
        self.assertEqual(declared, actual)
        self.assertEqual(len(rows), len({row["InstallOrder"] for row in rows}))
        self.assertEqual(len(rows), 60)
        self.assertTrue(all(row["HomeTable"] in model_tables for row in rows))
        self.assertTrue(all(row["FormatString"] for row in rows))
        self.assertEqual({row["Required"] for row in rows}, {"TRUE"})

    def test_relationship_manifest_is_unambiguous_and_single_direction(self) -> None:
        manifest_path = ROOT / self.contract["relationshipManifest"]
        with manifest_path.open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        with (ROOT / self.contract["queryManifest"]).open(newline="", encoding="utf-8") as source:
            model_tables = {
                row["QueryName"] for row in csv.DictReader(source) if row["LoadDestination"] == "DataModel"
            }
        keys = {
            (row["ForeignTable"], row["ForeignColumn"], row["LookupTable"], row["LookupColumn"])
            for row in rows
        }
        self.assertEqual(len(rows), len(keys))
        self.assertEqual(len(rows), 44)
        self.assertTrue(all(row["ForeignTable"].startswith("fact_") for row in rows))
        self.assertTrue(all(row["LookupTable"].startswith("dim_") for row in rows))
        self.assertTrue(all(row["ForeignTable"] in model_tables for row in rows))
        self.assertTrue(all(row["LookupTable"] in model_tables for row in rows))
        self.assertEqual({row["Cardinality"] for row in rows}, {"ManyToOne"})
        self.assertEqual({row["CrossFilter"] for row in rows}, {"Single"})
        self.assertEqual({row["Active"] for row in rows}, {"TRUE"})
        self.assertEqual({row["Required"] for row in rows}, {"TRUE"})
        self.assertEqual(self.contract["dateTable"], {"table": "dim_Date", "column": "Date"})

    def test_python_manifest_has_exact_definition_source_coverage(self) -> None:
        manifest_path = ROOT / self.contract["pythonManifest"]
        with manifest_path.open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(len(rows), 15)
        self.assertEqual(
            [int(row["InstallOrder"]) for row in rows],
            sorted(int(row["InstallOrder"]) for row in rows),
        )
        self.assertEqual(
            len(rows),
            len({(row["Sheet"], row["AnchorCell"]) for row in rows}),
        )
        definitions = {
            (manifest_path.parent / row["SourceFile"]).resolve()
            for row in rows
            if row["Role"] == "DEFINITIONS"
        }
        actual = {path.resolve() for path in manifest_path.parent.glob("*.py")}
        self.assertEqual(definitions, actual)
        self.assertEqual({row["Required"] for row in rows}, {"TRUE"})

    def test_installer_is_fail_closed_and_never_claims_engine_completion(self) -> None:
        script = SCRIPT_PATH.read_text(encoding="utf-8")
        required_tokens = (
            "#requires -Version 5.1",
            "SupportsShouldProcess = $true",
            "$excel.AutomationSecurity = 3",
            "$workbook.Queries.Add",
            "Get-FileHash",
            "NOT OPERATIONAL",
            "MANUAL_REQUIRED",
            "INSTALLED_DEFINITIONS_MANUAL_REQUIRED",
            "Workbook.VBProject",
        )
        for token in required_tokens:
            self.assertIn(token, script)
        forbidden_tokens = (
            ".RefreshAll(",
            ".ModelMeasures.Add",
            ".ModelRelationships.Add",
            '"OPERATIONAL"',
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, script)

    def test_manual_gates_cover_every_unverified_engine_step(self) -> None:
        self.assertEqual(
            set(self.contract["manualRequiredCapabilities"]),
            {
                "QUERY_LOAD_DESTINATIONS",
                "DATA_MODEL_RELATIONSHIPS",
                "DAX_MEASURES",
                "PYTHON_IN_EXCEL_CELLS",
                "DATE_TABLE_MARKING",
                "DESKTOP_EXCEL_REFRESH_VALIDATION",
            },
        )


if __name__ == "__main__":
    unittest.main()
