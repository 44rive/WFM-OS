from __future__ import annotations

import csv
import unittest
from collections import defaultdict
from datetime import datetime
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parent
INPUT_PATH = TEST_ROOT / "anonymized-input" / "contacts_valid.csv"
EXPECTED_PATH = TEST_ROOT / "expected-output" / "contact_daily_metrics.csv"
UNMAPPED_PATH = TEST_ROOT / "anonymized-input" / "contacts_unmapped_queue.csv"


def calculate_daily_metrics(path: Path) -> dict[str, dict[str, float]]:
    totals: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "offered": 0,
            "handled": 0,
            "short_abandoned": 0,
            "sl_eligible_offered": 0,
            "answered_within_sl": 0,
            "handle_seconds": 0,
        }
    )

    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            date = datetime.fromisoformat(row["start_time"]).date().isoformat()
            if row["direction"] != "inbound":
                continue

            values = totals[date]
            wait = float(row["wait_seconds"])
            handled = row["outcome"] == "answered"
            short_abandon = row["outcome"] == "abandoned" and wait < 5

            values["offered"] += 1
            values["handled"] += int(handled)
            values["short_abandoned"] += int(short_abandon)
            values["sl_eligible_offered"] += int(not short_abandon)
            values["answered_within_sl"] += int(handled and wait <= 20)
            if handled:
                values["handle_seconds"] += sum(
                    float(row[column])
                    for column in ("talk_seconds", "hold_seconds", "acw_seconds")
                )

    result: dict[str, dict[str, float]] = {}
    for date, values in totals.items():
        result[date] = {
            **values,
            "service_level": values["answered_within_sl"]
            / values["sl_eligible_offered"],
            "aht_seconds": values["handle_seconds"] / values["handled"],
        }
    return result


class ContactFixtureTest(unittest.TestCase):
    def test_expected_daily_metrics(self) -> None:
        actual = calculate_daily_metrics(INPUT_PATH)

        with EXPECTED_PATH.open(newline="", encoding="utf-8") as expected_file:
            expected_rows = list(csv.DictReader(expected_file))

        self.assertEqual(set(actual), {row["business_date"] for row in expected_rows})
        for expected in expected_rows:
            day = actual[expected["business_date"]]
            for metric in (
                "offered",
                "handled",
                "short_abandoned",
                "sl_eligible_offered",
                "answered_within_sl",
                "service_level",
                "aht_seconds",
            ):
                self.assertAlmostEqual(day[metric], float(expected[metric]))

    def test_contact_ids_are_unique(self) -> None:
        with INPUT_PATH.open(newline="", encoding="utf-8") as source:
            identifiers = [row["interaction_id"] for row in csv.DictReader(source)]
        self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_unknown_queue_is_quarantined(self) -> None:
        known_queues = {"Q_EXAMPLE"}
        with UNMAPPED_PATH.open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        quarantined = [row for row in rows if row["queue_id"] not in known_queues]
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0]["queue_id"], "Q_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
