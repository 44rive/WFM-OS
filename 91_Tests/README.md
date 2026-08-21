# Tests

Tests use only fabricated identities and source records. The expected CSVs are
the transparent acceptance contract for the same transformations when they are
implemented in Power Query, Power Pivot, DAX, or controlled workbook logic.

Run every standard-library test from the repository root:

```bash
python3 -m unittest discover -s 91_Tests -p 'test_*.py' -v
```

## Covered vertical slices

`test_contact_fixture.py` covers daily contact volume, handled count, short
abandons, service level, AHT, unique contact IDs, and unknown-queue quarantine.

`test_workforce_cycle.py` covers:

- system-scoped, effective-dated operational-identity resolution;
- canonical schedule-segment grain and paid minutes;
- login-session identity and valid duration;
- agent-event identity, state mapping, and non-overlap;
- interval scheduled, present, productive, required, and net staffing;
- daily attendance, lateness, early leave, and attendance outcome;
- interval and daily conformance/adherence;
- visible quarantine of an unknown operational identity;
- replacement-based, duplicate-free, idempotent close day.

`test_excel_installer_contract.py` verifies the committed workbook hash and
table schemas, exact Power Query and DAX source coverage, relationship metadata,
and the fail-closed Windows installer boundary without pretending to execute
desktop Excel in Linux CI.

## Reference definitions

All fixture times are local, timezone-consistent ISO timestamps. Production
adapters remain responsible for normalizing source time zones before applying
these rules.

- Intervals are 30-minute, half-open windows: `[start, end)`.
- Scheduled heads are distinct agents with any paid scheduled overlap.
- Scheduled productive heads are distinct agents with productive scheduled
  overlap.
- Present heads are scheduled agents with any login overlap.
- Productive heads are productively scheduled agents with a productive event
  overlap.
- Net productive heads equal productive heads minus required FTE.
- Attendance minutes are login seconds intersecting paid schedule segments.
- Late and early-leave minutes compare the paid schedule envelope with first
  login and last logout.
- Conformance equals logged seconds inside paid schedule divided by scheduled
  paid seconds.
- Adherence equals correctly matched state seconds divided by scheduled paid
  seconds. `Available` and `Handling` match productive schedule; `Break`
  matches a scheduled break.
- Exception seconds equal scheduled paid seconds minus adherent seconds.
- Close day removes the selected business date from closed facts and inserts
  the complete finalized live snapshot at the stable interval/activity grain.
  Repeating the same close produces byte-equivalent row values and no duplicate
  grain keys.

Rates in expected outputs are rounded to six decimal places. Desktop Excel is
still the release authority for genuine Power Query, Power Pivot/DAX, Python in
Excel, and visual validation.
