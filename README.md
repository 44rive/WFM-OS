# WFM OS

WFM OS is a portable, Excel-native workforce-management application.

The target product is one primary workbook, `WFM_OS.xlsm`, backed by external
source folders. Power Query handles ingestion and normalization, Power Pivot
holds the canonical model, DAX defines governed metrics, and Python in Excel
handles forecasting and simulation.

The model is vendor-neutral. Source products are adapters; the workbook operates
on canonical concepts such as contacts, work items, schedules, agent events,
people, forecasts, and quality results.

## Product boundary

```text
Source exports
    -> configurable Power Query adapters
    -> canonical WFM facts and dimensions
    -> one Power Pivot model
    -> DAX measures
    -> Excel operational pages and dashboards
    -> Python forecasting, backtesting, and scenarios
```

The workbook contains the application, configuration, model, decisions, and
presentation. Raw operational history stays outside the workbook in `03_Data/`
and is never committed to Git.

## Planned workbook modules

- Setup wizard and source mapping
- Data quality and refresh audit
- Strategic and demand planning
- Forecasting and forecast accuracy
- Capacity, hiring, and training-wave planning
- Schedule design, named roster, leave, swaps, and controlled publication
- Intraday/RTA and action logging
- Attendance, conformance, and adherence
- Agent/team performance and executive reporting
- Optional restricted bonus module

## Repository map

```text
00_Governance/      Architecture, contracts, design, roadmap, and decisions
01_Application/     Excel application and clean distribution template
02_Configuration/   Anonymized configuration schemas and templates
03_Data/            Numbered source landing zones; runtime data is ignored
04_Outputs/         Numbered publication areas; generated files are ignored
05_Backups/         Workbook snapshots; generated files are ignored
90_Source_Code/     Power Query, DAX, Python, and VBA source
91_Tests/           Anonymized fixtures and expected results
99_Archive/         Retired clean artifacts and migration references
tools/windows/      Fail-closed desktop Excel preflight and source installer
```

## Product and design standards

- [`AI_GUIDE.md`](AI_GUIDE.md) is the repository-only operating manual for any
  future AI or developer modifying the product.
- [`00_Governance/00-03_DESIGN_SYSTEM.md`](00_Governance/00-03_DESIGN_SYSTEM.md)
  defines the premium visual language and workbook component standard.
- [`02_Configuration/design_tokens.csv`](02_Configuration/design_tokens.csv) provides the same
  visual tokens in a machine-readable form.
- AI instructions and implementation notes do not appear in business-facing
  workbook sheets.

## Non-negotiable rules

1. No employee, customer, salary, contact, or production export data in Git.
2. No vendor name in canonical fact, dimension, or measure names.
3. Source-specific logic stops at the adapter layer.
4. Large facts load to the Data Model only, never to worksheets.
5. Every KPI is an explicit DAX measure with a documented business definition.
6. Unknown agents, queues, fields, and values are quarantined visibly.
7. Live and closed data use shared transformations and one semantic model.
8. A normal enterprise deployment changes configuration, not source code.

## Status

The repository currently contains the v0.6 architecture, a deterministic
premium `.xlsx` application shell, the contact-service slice, and the
schedule-led operational-control spine. It now also contains the governed
planning-to-supply engine:

`closed actuals -> daily candidate -> effective-dated intraday profile -> complete scenarios -> interval forecast approval -> capacity candidate -> requirement approval -> weekly paid-supply gap -> hiring/training waves -> hiring approval -> reconciled supply approval`.

Python candidates can never become facts merely because a cell calculated.
The daily baseline reconciles exactly to an approved 48-interval profile before
capacity is calculated. Hiring waves honor lead time, yield, FTE per head, and
training-seat limits; supply publication is blocked unless its planned-hire FTE
reconciles to approved waves. v0.5 added governed anonymous shift-pattern
fitting, independent Power Query interval coverage, schedule approval, and
interval leave-capacity approval. The deterministic `GREEDY_DEFICIT_V1` method
is transparent and reproducible; it is not a claim of global optimization.
v0.6 adds the separate named layer:

`approved BASE schedule -> stable unit occurrences -> eligibility + AND-of-OR skills + explicit availability + approved contract constraints -> deterministic named roster candidate -> roster approval -> full-request leave and bilateral whole-occurrence swap recommendations -> separate decisions -> controlled publication -> explicit schedule authority`.

The named assignment method is deterministic and bounded; it does not claim
global optimality. Contracts and policies are enterprise assertions, not proof
of compliance with law, collective agreements, or works-council requirements.
Medical/protected leave adjudication, payroll valuation, entitlement accounting,
partial leave, giveaways, open-shift markets, and multi-party swaps remain out
of scope. The shell remains explicitly
non-operational until its Power Query, Power Pivot, and controlled VBA engines
are installed and validated in desktop Excel:

`contact export -> Power Query -> Power Pivot -> DAX volume/SL/AHT -> live and historical views`.

`people/identity mappings + schedules + logins + states + requirements -> interval staffing + attendance + adherence + governed close day`.

The Windows installer can validate the committed artifact and install all
reviewed Power Query definitions on a staged copy. Query loads, 54
relationships, 80 DAX measures, 27 ordered Python cells, Date Table marking,
refresh, and release validation remain explicit desktop Excel gates; see
[`01_Application/01-02_DESKTOP_RELEASE_CHECKLIST.md`](01_Application/01-02_DESKTOP_RELEASE_CHECKLIST.md).
