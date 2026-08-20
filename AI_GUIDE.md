# AI modification guide

This file is the repository-only operating manual for any AI or developer that
modifies WFM OS. It must not be copied into a workbook sheet or distributed in a
business output.

## Product intent

WFM OS is a portable, vendor-neutral, premium Excel application covering the
workforce-management cycle. Its primary artifact is one Excel workbook. Power
Query ingests and normalizes data, Power Pivot stores the model, DAX defines
metrics, Python in Excel performs advanced analytics, and minimal VBA handles
controlled workbook actions.

A new enterprise should normally deploy WFM OS by configuring source systems,
field mappings, value mappings, activities, policies, and targets. It should not
need a fork of the calculation engine.

## Required reading order

Before making a change, read these files in order:

1. `AGENTS.md`
2. this file;
3. `docs/ARCHITECTURE.md`;
4. `docs/CANONICAL_CONTRACTS.md`;
5. `docs/DESIGN_SYSTEM.md`;
6. the relevant decision record under `docs/decisions/`;
7. the source files for the component being changed.

## Sources of truth

| Concern | Source of truth |
|---|---|
| Architecture | `docs/ARCHITECTURE.md` and accepted ADRs |
| Canonical fields | `docs/CANONICAL_CONTRACTS.md` |
| Visual system | `docs/DESIGN_SYSTEM.md` and `config/design_tokens.csv` |
| Power Query | `src/power-query/` |
| DAX | `src/dax/` |
| Python | `src/python/` |
| VBA | `src/vba/` |
| Released application | `workbooks/WFM_OS.xlsm` |

Text source in Git is canonical. A workbook release must contain the same source
and identify its repository commit on a technical `BUILD_INFO` sheet.

## Hard constraints

- Never commit production data, names, operational IDs, salaries, schedules,
  absences, contact records, or credentials.
- Never place AI instructions, prompts, design implementation notes, or source
  code dumps on business-facing workbook sheets.
- Never put a vendor name in a canonical fact, dimension, measure, or dashboard
  label. Vendor names belong only to adapter profiles and setup screens.
- Never silently filter an unmapped or invalid row. Quarantine it and expose the
  count and reason in Data Quality.
- Never load a large fact to a worksheet.
- Never create a second definition of an existing metric in formulas or Python.
- Never type decisions beside a refreshable query output. Store decisions in a
  separate keyed input table.
- Never treat hidden worksheets, protection, or obfuscation as data security.
- Never claim a query, relationship, measure, or Python workflow is wired unless
  it actually exists and executes in the released workbook.
- Never restyle a page locally when an existing component or token applies.

## Decide the smallest correct change

### Configuration-only change

Use configuration when adding or changing:

- an enterprise profile;
- a source path or file pattern;
- a source column mapping;
- a source status/value mapping;
- an activity, queue, skill, channel, site, team, or calendar event;
- a target, tolerance, threshold, contract, or shift rule;
- an effective date for an existing policy.

Configuration changes must not modify canonical query logic.

### Adapter change

Change or add an adapter when a new source format cannot be expressed through
field/value mappings alone. Adapter work stays under `src/power-query/staging/`
and must output an existing canonical contract.

Examples: a fixed-width schedule file, nested JSON contact export, unusual
duration encoding, or locale-specific date grammar.

### Canonical-model change

Change the canonical model only when the business introduces a genuinely new
concept that current contracts cannot represent. Before implementation:

1. write an ADR explaining the need and alternatives;
2. update the canonical contract;
3. define keys, grain, effective dating, and validation behavior;
4. define the migration impact on every adapter and measure;
5. add anonymized fixtures and expected results.

### Metric change

For a new or changed metric:

1. update the metric catalog and effective dates;
2. document numerator, denominator, exclusions, time grain, and source of truth;
3. implement one explicit DAX measure;
4. add boundary and blank/zero cases to the test harness;
5. reconcile it to an authoritative source;
6. update affected dashboard definitions without duplicating logic.

### Python change

Python is for forecasting, backtesting, simulation, optimization experiments,
anomaly analysis, and statistical visualization. It is not the ingestion layer,
identity resolver, core metric engine, or policy store.

Keep analytical functions pure where possible. The workbook wrapper may call
`xl()` to obtain Power Query data, but approved operational outputs must be
versioned in controlled Excel tables before downstream use.

### VBA change

VBA is limited to refresh sequencing, snapshot creation, backup, controlled
publication, and similar workbook actions. Business metric logic does not belong
in VBA. Export every embedded module to `src/vba/`.

### Design change

Use `docs/DESIGN_SYSTEM.md`. A new visual component requires:

1. a business reason;
2. a reusable component definition;
3. light-background and dark-header behavior;
4. number-format, empty-state, and error-state rules;
5. an update to the design-system version.

Do not add gradients, 3D charts, decorative gauges, random icons, excessive
borders, or additional accent colors.

## Common change recipes

### Add a new enterprise

1. Duplicate the blank deployment profile, not another customer's data.
2. Register source roles in `SOURCE_SYSTEMS`.
3. map fields to canonical contracts;
4. map external values to canonical values;
5. configure activities, queues, skills, calendars, targets, and policies;
6. refresh in validation mode;
7. resolve every required-field, unknown-value, duplicate-key, and unmatched-key
   issue;
8. reconcile a representative day and period;
9. activate the profile only after all blocking checks pass.

### Add a new source system

1. Identify its role, entity grains, keys, time zone, locale, refresh behavior,
   and whether extracts are cumulative or incremental.
2. Attempt deployment through the generic adapter and mappings.
3. If insufficient, create one source adapter that outputs canonical fields.
4. Add schema-drift, missing-file, duplicate, and mapping tests.
5. Do not change downstream facts or measures merely because a vendor labels a
   field differently.

### Add a business module

1. Define the business decision the page must support.
2. Identify required canonical facts, dimensions, measures, and controlled
   inputs.
3. extend the model only when required;
4. design the page with existing components;
5. provide empty, loading, warning, and blocking-error states;
6. add navigation, ownership, refresh timestamp, and drill-through behavior;
7. document the operating cadence and approval point.

## Workbook modification workflow

1. Create a feature branch and work on a copy of the released workbook.
2. Inspect actual workbook queries, connections, model tables, relationships,
   measures, names, validations, conditional formatting, PivotTables, charts,
   Python cells, and VBA before editing.
3. Update text source and tests first.
4. Install the exact source into desktop Excel.
5. Refresh using anonymized fixtures.
6. Run the technical and visual verification below.
7. Update `BUILD_INFO` with version, Git commit, contract version, design-system
   version, and build date.
8. Commit source and workbook together.

## Technical verification

- The workbook opens without repair warnings.
- Every required Power Query completes.
- Query load destinations match the architecture.
- Dimension lookup keys are unique and nonblank.
- Live and closed dates do not overlap.
- Relationships have a single intended filter path.
- Explicit measures return expected totals and blanks.
- Python cells calculate in the intended sheet/cell order.
- Refreshing twice produces the same finalized result.
- Source totals reconcile to canonical facts.
- Unknown and quarantined records remain visible.
- No production data or secrets are present in the Git diff.

## Visual verification

- The page follows the standard shell, spacing, and grid.
- Only documented design tokens are used.
- Inputs, selections, warnings, and disabled states are distinguishable without
  relying on color alone.
- Numbers have consistent units, precision, and empty states.
- Charts have a stated decision purpose and no unnecessary legend or decoration.
- The default viewport works at 100% zoom on a common laptop display.
- Print/export pages fit their defined page size.
- Navigation, slicers, refresh timestamp, and data-quality status are present.

## Definition of done

A change is complete only when the executable workbook, version-controlled
source, configuration schema, tests, documentation, and design remain aligned.
