from __future__ import annotations

import csv
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PQ_ROOT = ROOT / "90_Source_Code" / "01_Power_Query"
MANIFEST = PQ_ROOT / "MANIFEST.csv"


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

    def test_dax_measure_names_are_unique(self) -> None:
        measure_pattern = re.compile(r"^([^/\n][^\n]*?)\s*:=\s*$", re.MULTILINE)
        names: list[str] = []
        for path in (ROOT / "90_Source_Code" / "02_DAX").glob("*.dax"):
            names.extend(name.strip() for name in measure_pattern.findall(path.read_text(encoding="utf-8")))
        self.assertGreaterEqual(len(names), 20)
        self.assertEqual(len(names), len(set(names)))

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
