# WFM OS

WFM OS is a portable, Excel-native workforce-management application.

The product is one primary workbook, `WFM_OS.xlsm`, backed by external source
folders. Power Query handles ingestion and normalization, Power Pivot holds the
canonical model, DAX defines governed metrics, and Python in Excel handles
forecasting and simulation.

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
- Schedule design, shift coverage, and leave planning
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

The repository currently contains the v0.1 architecture and implementation
scaffold. The first build milestone is a reconciled vertical slice:

`contact export -> Power Query -> Power Pivot -> DAX volume/SL/AHT -> live and historical views`.
